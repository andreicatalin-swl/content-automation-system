import json
import subprocess
import uuid
from collections.abc import Callable
from pathlib import Path
from re import compile as re_compile
from tempfile import TemporaryDirectory
from typing import Final

import imageio_ffmpeg  # type: ignore
import openai_codex
from pydantic import BaseModel, ConfigDict

from content_automation_pipeline.artifacts.artifact import Artifact, Kind
from content_automation_pipeline.artifacts.artifact_manager import ArtifactManager
from content_automation_pipeline.content_agent.models.evaluation import Evaluation
from content_automation_pipeline.content_agent.models.media_files import (
    MediaFile,
    MediaFiles,
)
from content_automation_pipeline.content_agent.models.media_links import MediaLinks
from content_automation_pipeline.content_agent.tools.youtube_downloader import (
    YoutubeDownloader,
)
from content_automation_pipeline.shared.node import Node, Strategy
from content_automation_pipeline.shared.rate_limited_node import RateLimitedNode
from content_automation_pipeline.utilities.logger import create_logger

_logger = create_logger(__name__)

class MediaDownloadInput(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)

    media_links: MediaLinks

class MediaDownloadOutput(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)

    media_files: MediaFiles

class MediaDownloadStrategy(Strategy[MediaDownloadInput, MediaDownloadOutput]):
    def __init__(
        self,
        artifact_manager: ArtifactManager,
        category: str,
        kind: Kind,
    ) -> None:
        self._artifact_manager = artifact_manager
        self._category = category
        self._kind = kind
        self._downloader = YoutubeDownloader(artifact_manager, category)

    def execute(self, input: MediaDownloadInput) -> MediaDownloadOutput:
        entries = [
            MediaFile(
                audio=self._download_file(entry.audio_link, self._downloader.download_mp3),
                video=self._download_file(entry.video_link, self._downloader.download_mp4),
            )
            for entry in input.media_links.entries
        ]

        return MediaDownloadOutput(media_files=MediaFiles(entries=entries))

    # TODO: Implement proper _download_file method
    def _download_file(self, url: str, download: Callable[[str], Artifact]) -> Artifact:
        _WINDOW_SECONDS: Final[float] = 10.0
        _DURATION_PATTERN = re_compile(r'Duration: (\d+):(\d+):(\d+\.\d+)')

        raw = download(url)
        raw_path = self._artifact_manager.path(raw)

        ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
        result = subprocess.run([ffmpeg, '-i', str(raw_path)], capture_output=True, text=True, check=False)
        match = _DURATION_PATTERN.search(result.stderr)
        if match is None:
            message = f'could not determine duration of {raw_path}'
            _logger.error(message)
            raise ValueError(message)

        hours, minutes, seconds = match.groups()
        duration = int(hours) * 3600 + int(minutes) * 60 + float(seconds)
        start = duration / 2
        end = min(duration, start + _WINDOW_SECONDS)

        # Use a temporary directory to store the cropped file before publishing it as an artifact
        with TemporaryDirectory() as tmp_dir:
            cropped_path = Path(tmp_dir) / f'{uuid.uuid4().hex}{raw_path.suffix}'
            subprocess.run(
                [ffmpeg, '-y', '-i', str(raw_path), '-ss', str(start), '-to', str(end), '-c', 'copy', str(cropped_path)],
                check=True,
                capture_output=True,
            )

            cropped = Artifact(kind=self._kind, category=self._category, name=cropped_path.name)
            self._artifact_manager.publish(cropped, cropped_path, move=True)

        self._artifact_manager.delete(raw)

        return cropped

class DownloadMedia(RateLimitedNode[MediaDownloadInput, MediaDownloadOutput]):
    def __init__(
        self,
        strategy: Strategy[MediaDownloadInput, MediaDownloadOutput],
        max_calls: int = RateLimitedNode._DEFAULT_MAX_CALLS,
    ) -> None:
        super().__init__(strategy, max_calls)

class DownloadedMediaEvaluationInput(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)

    # Input for the DownloadMedia node
    media_download_input: MediaDownloadInput
    # Output from the DownloadMedia node
    media_download_output: MediaDownloadOutput
    # Instructions for evaluating output given the input
    evaluation_instructions: str

class DownloadedMediaEvaluationOutput(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)

    evaluation: Evaluation

class DownloadedMediaEvaluationStrategy(Strategy[DownloadedMediaEvaluationInput, DownloadedMediaEvaluationOutput]):
    # Hardcoded values that cannot be overridden by the user
    _INSTRUCTION_TEMPLATE: Final[str] = (
        'Evaluate the output of a node given its input, the required output schema, and the evaluation '
        'instructions.\n\n'
        'Assign the grade pass when the output is successful in the evaluation, and the grade fail otherwise. '
        'Give feedback that supports the grade.\n\n'
        'Input: {input}\n\n'
        'Output: {output}\n\n'
        'Output schema: {output_schema}\n\n'
        'Evaluation instructions: {evaluation_instructions}'
    )

    def execute(self, input: DownloadedMediaEvaluationInput) -> DownloadedMediaEvaluationOutput:
        instruction = self._INSTRUCTION_TEMPLATE.format(
            input=input.media_download_input.model_dump_json(),
            output=input.media_download_output.model_dump_json(),
            output_schema=json.dumps(MediaDownloadOutput.model_json_schema()),
            evaluation_instructions=input.evaluation_instructions,
        )

        # Use Codex to grade and give feedback on the media files
        with openai_codex.Codex() as codex:
            thread = codex.thread_start(sandbox=openai_codex.Sandbox.read_only)
            result = thread.run(instruction, output_schema=Evaluation.model_json_schema())

        final_response = result.final_response

        # Narrow to str
        if final_response is None:
            message = 'did not return a response'
            _logger.error(message)
            raise RuntimeError(message)

        return DownloadedMediaEvaluationOutput(evaluation=Evaluation.model_validate_json(final_response))

class EvaluateDownloadedMedia(Node[DownloadedMediaEvaluationInput, DownloadedMediaEvaluationOutput]):
    def __init__(
        self,
        strategy: Strategy[DownloadedMediaEvaluationInput, DownloadedMediaEvaluationOutput],
    ) -> None:
        super().__init__(strategy)

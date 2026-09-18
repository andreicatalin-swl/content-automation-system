import subprocess
import uuid
from collections.abc import Callable
from pathlib import Path
from re import compile as re_compile
from tempfile import TemporaryDirectory
from typing import Final

import imageio_ffmpeg  # type: ignore

from content_automation_pipeline.artifacts.artifact import Artifact, Kind
from content_automation_pipeline.artifacts.artifact_manager import ArtifactManager
from content_automation_pipeline.content_agent.models.media_files import (
    MediaFile,
    MediaFiles,
)
from content_automation_pipeline.content_agent.models.media_links import (
    MediaLink,
    MediaLinks,
)
from content_automation_pipeline.content_agent.tools.youtube_downloader import (
    YoutubeDownloader,
)
from content_automation_pipeline.shared.node import Strategy
from content_automation_pipeline.shared.rate_limited_node import RateLimitedNode
from content_automation_pipeline.utilities.logger import create_logger

_logger = create_logger(__name__)

class _Strategy(Strategy[MediaLinks, MediaFiles]):
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

    def execute(self, input: MediaLinks) -> MediaFiles:
        entries = [self._download_entry(entry) for entry in input.entries]

        return MediaFiles(entries=entries)

    def _download_entry(self, entry: MediaLink) -> MediaFile:
        video = self._download(entry.video_link, self._downloader.download_mp4)
        audio = self._download(entry.audio_link, self._downloader.download_mp3)

        return MediaFile(audio=audio, video=video)

    # TODO: Implement proper download method
    def _download(self, url: str, download: Callable[[str], Artifact]) -> Artifact:
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

class DownloadMedia(RateLimitedNode[MediaLinks, MediaFiles]):
    def __init__(
        self,
        artifact_manager: ArtifactManager,
        category: str,
        kind: Kind,
        max_calls: int = RateLimitedNode._DEFAULT_MAX_CALLS,
    ) -> None:
        super().__init__(_Strategy(artifact_manager, category, kind), max_calls)

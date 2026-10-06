from typing import Final

from pydantic import BaseModel, ConfigDict

from content_automation_system.artifacts.artifact import Kind
from content_automation_system.artifacts.artifact_manager import ArtifactManager
from content_automation_system.countdown_agent.models.evaluation import (
    Evaluation,
    Grade,
)
from content_automation_system.countdown_agent.models.media_files import (
    MediaFile,
    MediaFiles,
)
from content_automation_system.countdown_agent.models.media_links import MediaLinks
from content_automation_system.countdown_agent.tools.youtube_downloader import (
    YoutubeDownloader,
)
from content_automation_system.shared.abstract_node import AbstractNode
from content_automation_system.utilities.logger import create_logger

_logger = create_logger(__name__)

class MediaDownloadInput(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)

    media_links: MediaLinks

    def __repr__(self) -> str:
        return repr(self.media_links)

class MediaDownloadOutput(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)

    media_files: MediaFiles

    def __repr__(self) -> str:
        return repr(self.media_files)

class DownloadMedia(AbstractNode[MediaDownloadInput, MediaDownloadOutput]):
    def __init__(
        self,
        artifact_manager: ArtifactManager,
        category: str,
        kind: Kind,
    ) -> None:
        self._downloader = YoutubeDownloader(artifact_manager, category, kind)

    def execute(self, input: MediaDownloadInput) -> MediaDownloadOutput:
        entries = [
            MediaFile(
                audio=self._downloader.download_mp3(
                    entry.audio_link,
                    entry.audio_start_timestamp,
                    entry.audio_duration,
                ),
                video=self._downloader.download_mp4(
                    entry.video_link,
                    entry.video_start_timestamp,
                    entry.video_duration,
                ),
            )
            for entry in input.media_links.entries
        ]

        return MediaDownloadOutput(media_files=MediaFiles(entries=entries))

class DownloadedMediaEvaluationInput(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)

    # Input for the DownloadMedia node
    media_download_input: MediaDownloadInput
    # Output from the DownloadMedia node
    media_download_output: MediaDownloadOutput
    # Instructions for evaluating output given the input
    evaluation_instructions: str

    def __repr__(self) -> str:
        return f'{self.media_download_output!r} against {self.evaluation_instructions}'

class DownloadedMediaEvaluationOutput(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)

    evaluation: Evaluation

    def __repr__(self) -> str:
        return repr(self.evaluation)

# TODO: Implement proper execute(...) method
class EvaluateDownloadedMedia(AbstractNode[DownloadedMediaEvaluationInput, DownloadedMediaEvaluationOutput]):
    # Hardcoded values that cannot be overridden by the user
    _NO_FEEDBACK: Final[str] = 'there is no feedback.'

    def execute(self, input: DownloadedMediaEvaluationInput) -> DownloadedMediaEvaluationOutput:
        return DownloadedMediaEvaluationOutput(evaluation=Evaluation(grade=Grade.PASS, feedback=self._NO_FEEDBACK))

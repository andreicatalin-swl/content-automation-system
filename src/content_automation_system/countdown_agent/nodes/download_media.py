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
from content_automation_system.countdown_agent.nodes.abstract_evaluate import (
    AbstractEvaluate,
    EvaluationInput,
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

# TODO: Implement proper evaluate(...) method
class EvaluateDownloadedMedia(AbstractEvaluate[MediaDownloadInput, MediaDownloadOutput]):
    # Hardcoded values that cannot be overridden by the user
    _NO_FEEDBACK: Final[str] = 'there is no feedback.'

    def evaluate(self, input: EvaluationInput[MediaDownloadInput, MediaDownloadOutput]) -> Evaluation:
        return Evaluation(grade=Grade.PASS, feedback=self._NO_FEEDBACK)

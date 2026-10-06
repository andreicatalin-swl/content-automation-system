from pydantic import BaseModel, ConfigDict

from content_automation_system.artifacts.artifact import Artifact
from content_automation_system.utilities.logger import create_logger

_logger = create_logger(__name__)

class MediaFile(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)

    audio: Artifact
    video: Artifact

    def __repr__(self) -> str:
        return f'video {self.video.name}, audio {self.audio.name}'

class MediaFiles(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)

    entries: list[MediaFile]

    def __repr__(self) -> str:
        return f'{len(self.entries)} media files'

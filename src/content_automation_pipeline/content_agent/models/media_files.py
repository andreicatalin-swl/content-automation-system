from pydantic import BaseModel, ConfigDict

from content_automation_pipeline.artifacts.artifact import Artifact
from content_automation_pipeline.utilities.logger import create_logger

_logger = create_logger(__name__)

class MediaFile(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)

    audio: Artifact
    video: Artifact

class MediaFiles(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)

    entries: list[MediaFile]

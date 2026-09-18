from pydantic import BaseModel, ConfigDict

from content_automation_pipeline.utilities.logger import create_logger

_logger = create_logger(__name__)

class MediaLink(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)

    video_link: str
    audio_link: str

class MediaLinks(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)

    entries: list[MediaLink]

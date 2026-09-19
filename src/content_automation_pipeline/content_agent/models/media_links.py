from pydantic import BaseModel, ConfigDict

from content_automation_pipeline.utilities.logger import create_logger

_logger = create_logger(__name__)

class MediaLink(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)

    video_link: str
    video_start_timestamp: float
    video_duration: float
    audio_link: str
    audio_start_timestamp: float
    audio_duration: float

    def __str__(self) -> str:
        return (
            f'video {self.video_link} from {self.video_start_timestamp}s for {self.video_duration}s, '
            f'audio {self.audio_link} from {self.audio_start_timestamp}s for {self.audio_duration}s'
        )

class MediaLinks(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)

    entries: list[MediaLink]

    def __str__(self) -> str:
        return f'{len(self.entries)} media links'

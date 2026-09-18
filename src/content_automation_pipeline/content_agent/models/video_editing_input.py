from pydantic import BaseModel, ConfigDict

from content_automation_pipeline.content_agent.models.media_files import MediaFiles
from content_automation_pipeline.content_agent.models.script import Script
from content_automation_pipeline.utilities.logger import create_logger

_logger = create_logger(__name__)

class VideoEditingInput(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)

    script: Script
    media_files: MediaFiles

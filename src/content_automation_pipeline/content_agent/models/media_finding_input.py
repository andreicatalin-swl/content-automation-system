from pydantic import BaseModel, ConfigDict

from content_automation_pipeline.content_agent.models.script import Script
from content_automation_pipeline.utilities.logger import create_logger

_logger = create_logger(__name__)

class MediaFindingInput(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)

    script: Script
    instructions: str

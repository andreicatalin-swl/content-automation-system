from pydantic import BaseModel, ConfigDict

from content_automation_pipeline.content_agent.models.entry import Entry
from content_automation_pipeline.utilities.logger import create_logger

_logger = create_logger(__name__)

class Script(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)

    username: str
    title1: str
    title2: str
    subheading: str
    entries: list[Entry]

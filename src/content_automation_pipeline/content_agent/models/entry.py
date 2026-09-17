from pydantic import BaseModel, ConfigDict

from content_automation_pipeline.utilities.logger import create_logger

_logger = create_logger(__name__)

class Entry(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)

    line: str

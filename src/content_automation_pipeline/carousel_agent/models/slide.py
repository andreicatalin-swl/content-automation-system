from pydantic import BaseModel

from content_automation_pipeline.utilities.logger import create_logger

_logger = create_logger(__name__)

class Slide(BaseModel):
    prompt: str
    caption: str

from pydantic import BaseModel

from content_automation_pipeline.carousel_agent.models.content import Content
from content_automation_pipeline.utilities.logger import create_logger

_logger = create_logger(__name__)

class State(BaseModel):
    content: Content
    context: str

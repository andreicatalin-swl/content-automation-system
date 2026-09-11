from pydantic import BaseModel

from content_automation_pipeline.carousel_agent.models.slide import Slide
from content_automation_pipeline.utilities.logger import create_logger

_logger = create_logger(__name__)

class State(BaseModel):
    context: str
    number_slides: int
    slides: list[Slide] = []

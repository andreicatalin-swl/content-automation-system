from pydantic import BaseModel

from content_automation_pipeline.carousel_agent.models.slide import Slide
from content_automation_pipeline.shared.utilities.logger import create_logger

_logger = create_logger(__name__)

class Content(BaseModel):
    slides: list[Slide]

from pydantic import BaseModel

from content_automation_pipeline.utilities.logger import create_logger
from content_automation_pipeline.video_agent.models.element import Element

_logger = create_logger(__name__)

class Script(BaseModel):
    elements: list[Element]

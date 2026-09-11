from pydantic import BaseModel

from content_automation_pipeline.t2i_agent.models.grade import Grade
from content_automation_pipeline.utilities.logger import create_logger

_logger = create_logger(__name__)

class Evaluation(BaseModel):
    grade: Grade
    feedback: str

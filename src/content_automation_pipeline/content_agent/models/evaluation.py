from pydantic import BaseModel, ConfigDict

from content_automation_pipeline.content_agent.models.grade import Grade
from content_automation_pipeline.utilities.logger import create_logger

_logger = create_logger(__name__)

class Evaluation(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)

    grade: Grade
    feedback: str

from pydantic import BaseModel, ConfigDict

from content_automation_pipeline.t2i_agent.models.grade import Grade
from content_automation_pipeline.utilities.logger import create_logger

_logger = create_logger(__name__)

class Evaluation(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True, validate_assignment=True)

    grade: Grade
    feedback: str

from pydantic import BaseModel

from content_automation_pipeline.artifacts.artifact import Artifact
from content_automation_pipeline.t2i_agent.models.evaluation import Evaluation
from content_automation_pipeline.utilities.logger import create_logger

_logger = create_logger(__name__)

class State(BaseModel):
    prompt: str
    artifact: Artifact | None = None
    evaluation: Evaluation | None = None
    generation_attempts: int = 0
    evaluation_attempts: int = 0

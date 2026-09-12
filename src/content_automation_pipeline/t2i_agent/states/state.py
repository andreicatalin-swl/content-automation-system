from pydantic import BaseModel, ConfigDict, Field

from content_automation_pipeline.artifacts.artifact import Artifact
from content_automation_pipeline.t2i_agent.models.evaluation import Evaluation
from content_automation_pipeline.utilities.logger import create_logger

_logger = create_logger(__name__)

class State(BaseModel):
    # Forbid extra fields so no node can write a field the state does not declare,
    # reject values of the wrong type instead of coercing them, and validate every assignment
    model_config = ConfigDict(extra='forbid', strict=True, validate_assignment=True)

    prompt: str
    artifact: Artifact | None = None
    evaluation: Evaluation | None = None
    generation_attempts: int = Field(default=0)
    evaluation_attempts: int = Field(default=0)

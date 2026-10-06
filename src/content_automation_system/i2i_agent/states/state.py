from pydantic import BaseModel, ConfigDict

from content_automation_system.artifacts.artifact import Artifact
from content_automation_system.i2i_agent.models.evaluation import Evaluation
from content_automation_system.utilities.logger import create_logger

_logger = create_logger(__name__)

class State(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True, validate_assignment=True)

    images: list[Artifact]
    generation_instructions: str
    evaluation_instructions: str
    feedback: list[str]
    image: Artifact | None
    evaluation: Evaluation | None

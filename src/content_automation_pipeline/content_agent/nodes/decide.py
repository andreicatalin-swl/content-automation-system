from pydantic import BaseModel, ConfigDict

from content_automation_pipeline.content_agent.models.evaluation import (
    Evaluation,
    Grade,
)
from content_automation_pipeline.shared.abstract_node import AbstractNode
from content_automation_pipeline.utilities.logger import create_logger

_logger = create_logger(__name__)

class DecisionInput(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)

    evaluation: Evaluation

class DecisionOutput(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)

    destination: str

class Decide(AbstractNode[DecisionInput, DecisionOutput]):
    def __init__(
        self,
        pass_node: str,
        fail_node: str,
    ) -> None:
        self._pass_node = pass_node
        self._fail_node = fail_node

    def execute(self, input: DecisionInput) -> DecisionOutput:
        destination = self._pass_node if input.evaluation.grade is Grade.PASS else self._fail_node

        return DecisionOutput(destination=destination)

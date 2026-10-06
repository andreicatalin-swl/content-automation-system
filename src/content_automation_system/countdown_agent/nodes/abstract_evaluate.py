from abc import abstractmethod
from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict

from content_automation_system.countdown_agent.models.evaluation import Evaluation
from content_automation_system.shared.abstract_node import AbstractNode

T = TypeVar('T', bound=BaseModel)
U = TypeVar('U', bound=BaseModel)

class EvaluationInput(BaseModel, Generic[T, U]):
    model_config = ConfigDict(extra='forbid', strict=True)

    node_input: T
    node_output: U
    evaluation_instructions: str

    def __repr__(self) -> str:
        return f'{self.node_output!r} against {self.evaluation_instructions}'

class EvaluationOutput(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)

    evaluation: Evaluation

    def __repr__(self) -> str:
        return repr(self.evaluation)

class AbstractEvaluate(AbstractNode[EvaluationInput[T, U], EvaluationOutput], Generic[T, U]):
    def execute(self, input: EvaluationInput[T, U]) -> EvaluationOutput:
        return EvaluationOutput(evaluation=self.evaluate(input))

    @abstractmethod
    def evaluate(self, input: EvaluationInput[T, U]) -> Evaluation:
        ...

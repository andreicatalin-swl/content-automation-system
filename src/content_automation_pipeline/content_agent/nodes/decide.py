from content_automation_pipeline.content_agent.models.evaluation import (
    Evaluation,
    Grade,
)
from content_automation_pipeline.shared.node import Node, Strategy
from content_automation_pipeline.utilities.logger import create_logger

_logger = create_logger(__name__)

class _Strategy(Strategy[Evaluation, str]):
    def __init__(
        self,
        pass_node: str,
        fail_node: str,
    ) -> None:
        self._pass_node = pass_node
        self._fail_node = fail_node

    def execute(self, input: Evaluation) -> str:
        return self._pass_node if input.grade is Grade.PASS else self._fail_node

class Decide(Node[Evaluation, str]):
    def __init__(
        self,
        pass_node: str,
        fail_node: str,
    ) -> None:
        super().__init__(_Strategy(pass_node, fail_node))

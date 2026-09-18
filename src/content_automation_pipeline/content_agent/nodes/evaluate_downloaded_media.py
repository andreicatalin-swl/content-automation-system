from typing import Final

from content_automation_pipeline.content_agent.models.downloaded_media_evaluation_input import (
    DownloadedMediaEvaluationInput,
)
from content_automation_pipeline.content_agent.models.evaluation import (
    Evaluation,
    Grade,
)
from content_automation_pipeline.shared.node import Strategy
from content_automation_pipeline.shared.rate_limited_node import RateLimitedNode
from content_automation_pipeline.utilities.logger import create_logger

_logger = create_logger(__name__)

class _Strategy(Strategy[DownloadedMediaEvaluationInput, Evaluation]):
    # Hardcoded values that cannot be overridden by the user
    _NO_FEEDBACK: Final[str] = 'there is no feedback.'

    def execute(self, input: DownloadedMediaEvaluationInput) -> Evaluation:
        # TODO: Implement evaluation logic for downloaded media
        return Evaluation(grade=Grade.PASS, feedback=self._NO_FEEDBACK)

class EvaluateDownloadedMedia(RateLimitedNode[DownloadedMediaEvaluationInput, Evaluation]):
    def __init__(
        self,
        max_calls: int = RateLimitedNode._DEFAULT_MAX_CALLS,
    ) -> None:
        super().__init__(_Strategy(), max_calls)

from typing import Final

import openai_codex
from pydantic import BaseModel, ConfigDict

from content_automation_pipeline.content_agent.models.evaluation import (
    Evaluation,
    Grade,
)
from content_automation_pipeline.content_agent.models.media_links import (
    MediaLink,
    MediaLinks,
)
from content_automation_pipeline.content_agent.models.script import Script
from content_automation_pipeline.content_agent.tools.youtube_downloader import (
    YoutubeDownloader,
)
from content_automation_pipeline.shared.node import Node, Strategy
from content_automation_pipeline.shared.rate_limited_node import RateLimitedNode
from content_automation_pipeline.utilities.logger import create_logger

_logger = create_logger(__name__)

class FindMedia(RateLimitedNode[MediaFindingInput, MediaFindingOutput]):
    def __init__(
        self,
        strategy: Strategy[MediaFindingInput, MediaFindingOutput],
        max_calls: int = RateLimitedNode._DEFAULT_MAX_CALLS,
    ) -> None:
        super().__init__(strategy, max_calls)

class FoundMediaEvaluationInput(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)

    # Input for the FindMedia node
    media_finding_input: MediaFindingInput
    # Output from the FindMedia node
    media_finding_output: MediaFindingOutput
    # Instructions for evaluating output given the input
    evaluation_instructions: str

class FoundMediaEvaluationOutput(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)

    evaluation: Evaluation

# TODO: Implement proper execute(...) method
class FoundMediaEvaluationStrategy(Strategy[FoundMediaEvaluationInput, FoundMediaEvaluationOutput]):
    # Hardcoded values that cannot be overridden by the user
    _NO_FEEDBACK: Final[str] = 'there is no feedback.'

    def execute(self, input: FoundMediaEvaluationInput) -> FoundMediaEvaluationOutput:
        return FoundMediaEvaluationOutput(evaluation=Evaluation(grade=Grade.PASS, feedback=self._NO_FEEDBACK))

class EvaluateFoundMedia(Node[FoundMediaEvaluationInput, FoundMediaEvaluationOutput]):
    def __init__(
        self,
        strategy: Strategy[FoundMediaEvaluationInput, FoundMediaEvaluationOutput],
    ) -> None:
        super().__init__(strategy)

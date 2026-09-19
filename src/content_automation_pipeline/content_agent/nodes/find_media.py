from typing import Final

import openai_codex
from pydantic import BaseModel, ConfigDict

from content_automation_pipeline.content_agent.models.evaluation import (
    Evaluation,
    Grade,
)
from content_automation_pipeline.content_agent.models.media_links import MediaLinks
from content_automation_pipeline.content_agent.models.script import Script
from content_automation_pipeline.shared.node import Node, Strategy
from content_automation_pipeline.shared.rate_limited_node import RateLimitedNode
from content_automation_pipeline.utilities.logger import create_logger

_logger = create_logger(__name__)

class MediaFindingInput(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)

    script: Script
    instructions: str

class MediaFindingOutput(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)

    media_links: MediaLinks

class MediaFindingStrategy(Strategy[MediaFindingInput, MediaFindingOutput]):
    # Hardcoded values that cannot be overridden by the user
    _INSTRUCTION_TEMPLATE: Final[str] = (
        'Search YouTube for the video and the audio that fit every entry of the script, and give each one '
        'the timestamp it should start at and how long it should run, following the instructions.\n\n'
        'Script: {script}\n\n'
        'Instructions: {instructions}'
    )

    def execute(self, input: MediaFindingInput) -> MediaFindingOutput:
        instruction = self._INSTRUCTION_TEMPLATE.format(
            script=input.script.model_dump_json(),
            instructions=input.instructions,
        )

        with openai_codex.Codex() as codex:
            thread = codex.thread_start(sandbox=openai_codex.Sandbox.read_only)
            result = thread.run(instruction, output_schema=MediaLinks.model_json_schema())

        final_response = result.final_response

        # Narrow to str
        if final_response is None:
            message = 'did not return a response'
            _logger.error(message)
            raise RuntimeError(message)

        return MediaFindingOutput(media_links=MediaLinks.model_validate_json(final_response))

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

from typing import Final

import openai_codex
from pydantic import BaseModel, ConfigDict

from content_automation_pipeline.content_agent.models.evaluation import (
    Evaluation,
    Grade,
)
from content_automation_pipeline.content_agent.models.media_links import MediaLinks
from content_automation_pipeline.content_agent.models.script import Script
from content_automation_pipeline.shared.abstract_node import AbstractNode
from content_automation_pipeline.utilities.logger import create_logger

_logger = create_logger(__name__)

class MediaFindingInput(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)

    script: Script
    instructions: str

    def __repr__(self) -> str:
        return f'{self.script!r} with {self.instructions}'

class MediaFindingOutput(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)

    media_links: MediaLinks

    def __repr__(self) -> str:
        return repr(self.media_links)

class FindMedia(AbstractNode[MediaFindingInput, MediaFindingOutput]):
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

class FoundMediaEvaluationInput(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)

    # Input for the FindMedia node
    media_finding_input: MediaFindingInput
    # Output from the FindMedia node
    media_finding_output: MediaFindingOutput
    # Instructions for evaluating output given the input
    evaluation_instructions: str

    def __repr__(self) -> str:
        return f'{self.media_finding_output!r} against {self.evaluation_instructions}'

class FoundMediaEvaluationOutput(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)

    evaluation: Evaluation

    def __repr__(self) -> str:
        return repr(self.evaluation)

# TODO: Implement proper execute(...) method
class EvaluateFoundMedia(AbstractNode[FoundMediaEvaluationInput, FoundMediaEvaluationOutput]):
    # Hardcoded values that cannot be overridden by the user
    _NO_FEEDBACK: Final[str] = 'there is no feedback.'

    def execute(self, input: FoundMediaEvaluationInput) -> FoundMediaEvaluationOutput:
        return FoundMediaEvaluationOutput(evaluation=Evaluation(grade=Grade.PASS, feedback=self._NO_FEEDBACK))

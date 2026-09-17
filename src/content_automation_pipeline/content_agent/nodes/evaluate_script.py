from typing import Final

import openai_codex

from content_automation_pipeline.content_agent.models.evaluation import Evaluation
from content_automation_pipeline.content_agent.models.evaluation_input import (
    EvaluationInput,
)
from content_automation_pipeline.shared.node import Strategy
from content_automation_pipeline.shared.rate_limited_node import RateLimitedNode
from content_automation_pipeline.utilities.logger import create_logger

_logger = create_logger(__name__)

class _Strategy(Strategy[EvaluationInput, Evaluation]):
    # Hardcoded values that cannot be overridden by the user
    _INSTRUCTION_TEMPLATE: Final[str] = (
        'Evaluate the script according to the instructions.\n\n'
        'Instructions: {instructions}\n\n'
        'Script: {script}'
    )

    def execute(self, input: EvaluationInput) -> Evaluation:
        instruction = self._INSTRUCTION_TEMPLATE.format(
            instructions=input.instructions,
            script=input.script.model_dump_json(),
        )

        # Use Codex to grade and give feedback on the script
        with openai_codex.Codex() as codex:
            thread = codex.thread_start(sandbox=openai_codex.Sandbox.read_only)
            result = thread.run(instruction, output_schema=Evaluation.model_json_schema())

        final_response = result.final_response

        # Narrow to str
        if final_response is None:
            message = 'did not return a response'
            _logger.error(message)
            raise RuntimeError(message)

        return Evaluation.model_validate_json(final_response)

class Evaluate(RateLimitedNode[EvaluationInput, Evaluation]):
    def __init__(
        self,
        max_calls: int = RateLimitedNode._DEFAULT_MAX_CALLS,
    ) -> None:
        super().__init__(_Strategy(), max_calls)

from typing import Final

import openai_codex

from content_automation_pipeline.content_agent.models.evaluation import Evaluation
from content_automation_pipeline.content_agent.models.script_evaluation_input import (
    ScriptEvaluationInput,
)
from content_automation_pipeline.shared.node import Strategy
from content_automation_pipeline.shared.rate_limited_node import RateLimitedNode
from content_automation_pipeline.utilities.logger import create_logger

_logger = create_logger(__name__)

class _Strategy(Strategy[ScriptEvaluationInput, Evaluation]):
    # Hardcoded values that cannot be overridden by the user
    _INSTRUCTION_TEMPLATE: Final[str] = (
        'Evaluate the script according to the evaluation instructions.\n\n'
        'Generation instructions (for context only): {generation_instructions}\n\n'
        'Script: {script}\n\n'
        'Evaluation instructions: {evaluation_instructions}'
    )

    def execute(self, input: ScriptEvaluationInput) -> Evaluation:
        instruction = self._INSTRUCTION_TEMPLATE.format(
            generation_instructions=input.generation_instructions,
            script=input.script.model_dump_json(),
            evaluation_instructions=input.evaluation_instructions,
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

class EvaluateScript(RateLimitedNode[ScriptEvaluationInput, Evaluation]):
    def __init__(
        self,
        max_calls: int = RateLimitedNode._DEFAULT_MAX_CALLS,
    ) -> None:
        super().__init__(_Strategy(), max_calls)

from typing import Final

import openai_codex

from content_automation_pipeline.content_agent.models.script import Script
from content_automation_pipeline.shared.node import Strategy
from content_automation_pipeline.shared.rate_limited_node import RateLimitedNode
from content_automation_pipeline.utilities.logger import create_logger

_logger = create_logger(__name__)

class _Strategy(Strategy[str, Script]):
    # Hardcoded values that cannot be overridden by the user
    _INSTRUCTION_TEMPLATE: Final[str] = (
        'Generate the requested script according to the instructions.\n\n'
        'Instructions: {instructions}'
    )

    def execute(self, input: str) -> Script:
        instruction = self._INSTRUCTION_TEMPLATE.format(instructions=input)

        # Use Codex to generate script
        with openai_codex.Codex() as codex:
            thread = codex.thread_start(sandbox=openai_codex.Sandbox.read_only)
            result = thread.run(instruction, output_schema=Script.model_json_schema())

        final_response = result.final_response

        # Narrow to str
        if final_response is None:
            message = 'did not return a response'
            _logger.error(message)
            raise RuntimeError(message)

        return Script.model_validate_json(final_response)

class GenerateScript(RateLimitedNode[str, Script]):
    def __init__(
        self,
        max_calls: int = RateLimitedNode._DEFAULT_MAX_CALLS,
    ) -> None:
        super().__init__(_Strategy(), max_calls)

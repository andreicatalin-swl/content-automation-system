import json
from typing import Final

import openai_codex
from pydantic import BaseModel, ConfigDict

from content_automation_system.agents.countdown.models.evaluation import Evaluation
from content_automation_system.agents.countdown.models.script import Script
from content_automation_system.agents.countdown.nodes.abstract_evaluate import (
    AbstractEvaluate,
    EvaluationInput,
)
from content_automation_system.shared.abstract_node import AbstractNode
from content_automation_system.utilities.logger import create_logger

_logger = create_logger(__name__)

class ScriptGenerationInput(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)

    instructions: str

    def __repr__(self) -> str:
        return self.instructions

class ScriptGenerationOutput(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)

    script: Script

    def __repr__(self) -> str:
        return repr(self.script)

class GenerateScript(AbstractNode[ScriptGenerationInput, ScriptGenerationOutput]):
    # Hardcoded values that cannot be overridden by the user
    _INSTRUCTION_TEMPLATE: Final[str] = (
        'Generate the requested script according to the instructions.\n\n'
        'Instructions: {instructions}'
    )

    def execute(self, input: ScriptGenerationInput) -> ScriptGenerationOutput:
        instruction = self._INSTRUCTION_TEMPLATE.format(instructions=input.instructions)

        # Use Codex to generate the script
        with openai_codex.Codex() as codex:
            thread = codex.thread_start(sandbox=openai_codex.Sandbox.read_only)
            result = thread.run(instruction, output_schema=Script.model_json_schema())

        final_response = result.final_response

        # Narrow to str
        if final_response is None:
            message = 'did not return a response'
            _logger.error(message)
            raise RuntimeError(message)

        return ScriptGenerationOutput(script=Script.model_validate_json(final_response))

class EvaluateGeneratedScript(AbstractEvaluate[ScriptGenerationInput, ScriptGenerationOutput]):
    # Hardcoded values that cannot be overridden by the user
    _INSTRUCTION_TEMPLATE: Final[str] = (
        'Evaluate the output of a node given its input, the required output schema, and the evaluation instructions.\n\n'
        'Assign the grade pass when the output is successful in the evaluation, and the grade fail otherwise. '
        'Give feedback that supports the grade.\n\n'
        'Input: {input}\n\n'
        'Output: {output}\n\n'
        'Output schema: {output_schema}\n\n'
        'Evaluation instructions: {evaluation_instructions}'
    )

    def evaluate(self, input: EvaluationInput[ScriptGenerationInput, ScriptGenerationOutput]) -> Evaluation:
        instruction = self._INSTRUCTION_TEMPLATE.format(
            input=input.node_input.model_dump_json(),
            output=input.node_output.model_dump_json(),
            output_schema=json.dumps(ScriptGenerationOutput.model_json_schema()),
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

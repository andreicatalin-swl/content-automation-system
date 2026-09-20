import json
from typing import Final

import openai_codex
from pydantic import BaseModel, ConfigDict

from content_automation_pipeline.countdown_agent.models.evaluation import Evaluation
from content_automation_pipeline.countdown_agent.models.script import Script
from content_automation_pipeline.shared.abstract_node import AbstractNode
from content_automation_pipeline.utilities.logger import create_logger

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

class GeneratedScriptEvaluationInput(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)

    # Input for the GenerateScript node
    script_generation_input: ScriptGenerationInput
    # Output from the GenerateScript node
    script_generation_output: ScriptGenerationOutput
    # Instructions for evaluating output given the input
    evaluation_instructions: str

    def __repr__(self) -> str:
        return f'{self.script_generation_output!r} against {self.evaluation_instructions}'

class GeneratedScriptEvaluationOutput(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)

    evaluation: Evaluation

    def __repr__(self) -> str:
        return repr(self.evaluation)

class EvaluateGeneratedScript(AbstractNode[GeneratedScriptEvaluationInput, GeneratedScriptEvaluationOutput]):
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

    def execute(self, input: GeneratedScriptEvaluationInput) -> GeneratedScriptEvaluationOutput:
        instruction = self._INSTRUCTION_TEMPLATE.format(
            input=input.script_generation_input.model_dump_json(),
            output=input.script_generation_output.model_dump_json(),
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

        return GeneratedScriptEvaluationOutput(evaluation=Evaluation.model_validate_json(final_response))

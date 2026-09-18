from typing import Final

import openai_codex
from pydantic import BaseModel, ConfigDict

from content_automation_pipeline.content_agent.models.evaluation import Evaluation
from content_automation_pipeline.content_agent.models.script import Script
from content_automation_pipeline.shared.node import Node, Strategy
from content_automation_pipeline.shared.rate_limited_node import RateLimitedNode
from content_automation_pipeline.utilities.logger import create_logger

_logger = create_logger(__name__)

class ScriptGenerationInput(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)

    instructions: str

class ScriptGenerationOutput(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)

    script: Script

class ScriptGenerationStrategy(Strategy[ScriptGenerationInput, ScriptGenerationOutput]):
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

class GenerateScript(RateLimitedNode[ScriptGenerationInput, ScriptGenerationOutput]):
    def __init__(
        self,
        strategy: Strategy[ScriptGenerationInput, ScriptGenerationOutput],
        max_calls: int = RateLimitedNode._DEFAULT_MAX_CALLS,
    ) -> None:
        super().__init__(strategy, max_calls)

class GeneratedScriptEvaluationInput(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)

    # Input for the GenerateScript node
    script_generation_input: ScriptGenerationInput
    # Output from the GenerateScript node
    script_generation_output: ScriptGenerationOutput
    # Instructions for evaluating output given the input
    evaluation_instructions: str

class GeneratedScriptEvaluationOutput(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)

    evaluation: Evaluation

class GeneratedScriptEvaluationStrategy(Strategy[GeneratedScriptEvaluationInput, GeneratedScriptEvaluationOutput]):
    # Hardcoded values that cannot be overridden by the user
    _INSTRUCTION_TEMPLATE: Final[str] = (
        'Evaluate the output of a node given the input to that node, following the evaluation instructions.\n\n'
        'Assign the grade pass when the output is successful in the evaluation, and the grade fail otherwise. '
        'Give feedback that supports the grade.\n\n'
        'Input: {input}\n\n'
        'Output: {output}\n\n'
        'Evaluation instructions: {evaluation_instructions}'
    )

    def execute(self, input: GeneratedScriptEvaluationInput) -> GeneratedScriptEvaluationOutput:
        instruction = self._INSTRUCTION_TEMPLATE.format(
            input=input.script_generation_input.model_dump_json(),
            output=input.script_generation_output.model_dump_json(),
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

class EvaluateGeneratedScript(Node[GeneratedScriptEvaluationInput, GeneratedScriptEvaluationOutput]):
    def __init__(
        self,
        strategy: Strategy[GeneratedScriptEvaluationInput, GeneratedScriptEvaluationOutput],
    ) -> None:
        super().__init__(strategy)

import uuid
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Final

import openai_codex
from pydantic import BaseModel, ConfigDict

from content_automation_system.artifacts.artifact import Artifact, Kind
from content_automation_system.artifacts.artifact_manager import ArtifactManager
from content_automation_system.agents.i2i.models.evaluation import Evaluation
from content_automation_system.agents.i2i.nodes.abstract_evaluate import (
    AbstractEvaluate,
    EvaluationInput,
    EvaluationOutput,
)
from content_automation_system.shared.abstract_node import AbstractNode
from content_automation_system.utilities.logger import create_logger

_logger = create_logger(__name__)

class GenerationInput(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)

    images: list[Artifact]
    instructions: str
    feedback: list[str]

    def __repr__(self) -> str:
        return self.instructions

class GenerationOutput(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)

    image: Artifact

    def __repr__(self) -> str:
        return self.image.name

class Generate(AbstractNode[GenerationInput, GenerationOutput]):
    # Hardcoded values that cannot be overridden by the user
    _PROMPT_TEMPLATE: Final[str] = (
        'Generate an image based on the provided images, instructions, and feedback.\n\n'
        'Instructions: {instructions}\n\n'
        'Feedback from the previous generations: {feedback}\n\n'
        'Save the image as a PNG file at the following path: {output_path}'
    )

    def __init__(
        self,
        artifact_manager: ArtifactManager,
        category: str,
        kind: Kind,
    ) -> None:
        self._artifact_manager = artifact_manager
        self._category = category
        self._kind = kind

    def execute(self, input: GenerationInput) -> GenerationOutput:
        with TemporaryDirectory() as directory:
            output_path = Path(directory) / f'{uuid.uuid4().hex}.png'

            # Build the prompt for the generation
            prompt = self._PROMPT_TEMPLATE.format(
                instructions=input.instructions,
                feedback='\n'.join(input.feedback),
                output_path=output_path,
            )

            # Use OpenAI Codex for the generation
            with openai_codex.Codex() as codex:
                thread = codex.thread_start(cwd=directory, sandbox=openai_codex.Sandbox.workspace_write)
                thread.run([
                    openai_codex.TextInput(prompt),
                    *(
                        openai_codex.LocalImageInput(str(self._artifact_manager.path(image)))
                        for image in input.images
                    ),
                ])

            # Create an artifact for the generated image and publish it to the artifact manager
            artifact = Artifact(kind=self._kind, category=self._category, name=output_path.name)
            self._artifact_manager.publish(artifact, output_path, move=True)

        return GenerationOutput(image=artifact)

class Evaluate(AbstractEvaluate[GenerationInput, GenerationOutput]):
    # Hardcoded values that cannot be overridden by the user
    _PROMPT_TEMPLATE: Final[str] = (
        'Check the generated image against the provided images, generation instructions, and feedback, then '
        'evaluate it according to the evaluation instructions. The first image is the generated image; the rest are '
        'the input images.\n\n'
        'Assign the grade pass when the image is successful in the evaluation, and the grade fail otherwise. '
        'Give feedback that supports the grade.\n\n'
        'Generation instructions: {generation_instructions}\n\n'
        'Generation feedback from the previous attempts: {generation_feedback}\n\n'
        'Evaluation instructions: {evaluation_instructions}'
    )

    def __init__(
        self,
        artifact_manager: ArtifactManager,
    ) -> None:
        self._artifact_manager = artifact_manager

    def execute(self, input: EvaluationInput[GenerationInput, GenerationOutput]) -> EvaluationOutput:
        # Build the prompt for the evaluation
        prompt = self._PROMPT_TEMPLATE.format(
            generation_instructions=input.node_input.instructions,
            generation_feedback='\n'.join(input.node_input.feedback),
            evaluation_instructions=input.evaluation_instructions,
        )

        # Use OpenAI Codex for the evaluation
        with openai_codex.Codex() as codex:
            thread = codex.thread_start(sandbox=openai_codex.Sandbox.read_only)
            result = thread.run(
                [
                    openai_codex.TextInput(prompt),
                    openai_codex.LocalImageInput(
                        str(self._artifact_manager.path(input.node_output.image)),
                    ),
                    *(
                        openai_codex.LocalImageInput(str(self._artifact_manager.path(image)))
                        for image in input.node_input.images
                    ),
                ],
                output_schema=Evaluation.model_json_schema(),
            )

        final_response = result.final_response

        # Narrow from str | None to str
        if final_response is None:
            message = 'did not return a response'
            _logger.error(message)
            raise RuntimeError(message)

        return EvaluationOutput(evaluation=Evaluation.model_validate_json(final_response))

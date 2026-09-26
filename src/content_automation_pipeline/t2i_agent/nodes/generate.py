import uuid
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Final

import openai_codex
from pydantic import BaseModel, ConfigDict

from content_automation_pipeline.artifacts.artifact import Artifact, Kind
from content_automation_pipeline.artifacts.artifact_manager import ArtifactManager
from content_automation_pipeline.shared.abstract_node import AbstractNode
from content_automation_pipeline.t2i_agent.models.evaluation import Evaluation
from content_automation_pipeline.utilities.logger import create_logger

_logger = create_logger(__name__)

class GenerationInput(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)

    instructions: str
    feedback: list[str]
    reference_images: list[Artifact]

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
        'Generate an image using your built-in image generation tool, respecting the instructions, reference '
        'images, and feedback from previous generations.\n\n'
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
                        openai_codex.LocalImageInput(str(self._artifact_manager.path(artifact)))
                        for artifact in input.reference_images
                    ),
                ])

            # Create an artifact for the generated image and publish it to the artifact manager
            artifact = Artifact(kind=self._kind, category=self._category, name=output_path.name)
            self._artifact_manager.publish(artifact, output_path, move=True)

        return GenerationOutput(image=artifact)

class EvaluationInput(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)

    generation_input: GenerationInput
    generation_output: GenerationOutput
    instructions: str

    def __repr__(self) -> str:
        return f'{self.generation_output!r} against {self.instructions}'

class EvaluationOutput(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)

    evaluation: Evaluation

    def __repr__(self) -> str:
        return repr(self.evaluation)

class Evaluate(AbstractNode[EvaluationInput, EvaluationOutput]):
    # Hardcoded values that cannot be overridden by the user
    _PROMPT_TEMPLATE: Final[str] = (
        'Check the first attached image against the generation instructions, reference images, and generation '
        'feedback, then evaluate it according to the instructions. Any remaining images are references.\n\n'
        'Assign the grade pass when the image is successful in the evaluation, and the grade fail otherwise. '
        'Give feedback that supports the grade.\n\n'
        'Generation instructions: {generation_instructions}\n\n'
        'Generation feedback from the previous attempts: {generation_feedback}\n\n'
        'Instructions: {instructions}'
    )

    def __init__(
        self,
        artifact_manager: ArtifactManager,
    ) -> None:
        self._artifact_manager = artifact_manager

    def execute(self, input: EvaluationInput) -> EvaluationOutput:
        # Build the prompt for the evaluation
        prompt = self._PROMPT_TEMPLATE.format(
            generation_instructions=input.generation_input.instructions,
            generation_feedback='\n'.join(input.generation_input.feedback),
            instructions=input.instructions,
        )

        # Use OpenAI Codex for the evaluation
        with openai_codex.Codex() as codex:
            thread = codex.thread_start(sandbox=openai_codex.Sandbox.read_only)
            result = thread.run(
                [
                    openai_codex.TextInput(prompt),
                    openai_codex.LocalImageInput(
                        str(self._artifact_manager.path(input.generation_output.image)),
                    ),
                    *(
                        openai_codex.LocalImageInput(str(self._artifact_manager.path(artifact)))
                        for artifact in input.generation_input.reference_images
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

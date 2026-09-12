import uuid
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Final

import openai_codex

from content_automation_pipeline.artifacts.artifact import Artifact, Kind
from content_automation_pipeline.artifacts.artifact_manager import ArtifactManager
from content_automation_pipeline.t2i_agent.states.state import State
from content_automation_pipeline.utilities.logger import create_logger

_logger = create_logger(__name__)

class Generate:
    # Hardcoded values that cannot be overridden by the user
    _IMAGE_EXTENSION: Final[str] = '.png'
    _PNG_SIGNATURE: Final[bytes] = b'\x89PNG\r\n\x1a\n'
    _NO_FEEDBACK: Final[str] = 'there is no feedback.'
    _INSTRUCTION_TEMPLATE: Final[str] = (
        'Generate an image using your built-in image generation tool.\n\n'
        'Description: {prompt}\n\n'
        'Feedback from the previous generation: {feedback}\n\n'
        'Save the image as a PNG file at the following path: {output_path}'
    )

    def __init__(
        self,
        artifact_manager: ArtifactManager,
        category: str,
        kind: Kind,
        max_attempts: int,
    ) -> None:
        self._artifact_manager = artifact_manager
        self._category = category
        self._kind = kind
        self._max_attempts = max_attempts

    def __call__(self, state: State) -> State:
        # Check if the maximum number of attempts has been reached
        if state.generation_attempts >= self._max_attempts:
            message = f'reached the maximum of {self._max_attempts} attempt(s) for prompt={state.prompt}'
            _logger.error(message)
            raise RuntimeError(message)

        message = f'generating image for prompt={state.prompt}'
        _logger.info(message)

        # Use a temporary directory to store the generated image before publishing it as an artifact
        with TemporaryDirectory() as tmp_dir:
            # Construct the instruction for Codex
            output_path = Path(tmp_dir) / f'{uuid.uuid4().hex}{self._IMAGE_EXTENSION}'
            feedback = state.evaluation.feedback if state.evaluation else self._NO_FEEDBACK
            instruction = self._INSTRUCTION_TEMPLATE.format(feedback=feedback, output_path=output_path, prompt=state.prompt)

            # Use Codex to generate the image based on the instruction
            with openai_codex.Codex() as codex:
                thread = codex.thread_start(cwd=tmp_dir, sandbox=openai_codex.Sandbox.workspace_write)
                thread.run(instruction)

            state.generation_attempts += 1

            # Retry if the generated output is not a valid image
            if not self._is_valid_image(output_path):
                message = f'attempt {state.generation_attempts}/{self._max_attempts} did not produce a valid image at {output_path}'
                _logger.warning(message)
                return self(state)

            # Publish the valid image as an artifact
            artifact = Artifact(self._kind, self._category, output_path.name)
            self._artifact_manager.publish(artifact, output_path, move=True)
            state.artifact = artifact

        message = f'finished generating image for prompt={state.prompt} as artifact {artifact.name}'
        _logger.info(message)

        return state

    @classmethod
    def _is_valid_image(cls, path: Path) -> bool:
        # Check if the file exists and has the correct extension
        if not path.is_file() or path.suffix != cls._IMAGE_EXTENSION:
            return False

        # Check if the file has the correct PNG signature
        with path.open('rb') as file:
            if file.read(len(cls._PNG_SIGNATURE)) != cls._PNG_SIGNATURE:
                return False

        # Conclude that the file is a valid PNG image
        return True

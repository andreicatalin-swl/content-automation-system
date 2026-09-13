import uuid
from abc import ABC, abstractmethod
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Final

import openai_codex

from content_automation_pipeline.artifacts.artifact import Artifact, Kind
from content_automation_pipeline.artifacts.artifact_manager import ArtifactManager
from content_automation_pipeline.t2i_agent.states.state import State
from content_automation_pipeline.utilities.logger import create_logger

_logger = create_logger(__name__)

class GenerationStrategy(ABC):
    @abstractmethod
    def generate(self, prompt: str) -> Artifact:
        ...

class CodexGenerationStrategy(GenerationStrategy):
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
    ) -> None:
        self._artifact_manager = artifact_manager
        self._category = category
        self._kind = kind

    def generate(self, prompt: str) -> Artifact:
        message = f'generating image for prompt={prompt}'
        _logger.info(message)

        # Use a temporary directory to store the generated image before publishing it as an artifact
        with TemporaryDirectory() as tmp_dir:
            # Construct the instruction for Codex
            output_path = Path(tmp_dir) / f'{uuid.uuid4().hex}{self._IMAGE_EXTENSION}'
            instruction = self._INSTRUCTION_TEMPLATE.format(feedback=self._NO_FEEDBACK, output_path=output_path, prompt=prompt)

            # Use Codex to generate the image based on the instruction
            with openai_codex.Codex() as codex:
                thread = codex.thread_start(cwd=tmp_dir, sandbox=openai_codex.Sandbox.workspace_write)
                thread.run(instruction)

            # Fail if the generated output is not a valid image
            if not self._is_valid_image(output_path):
                message = f'did not produce a valid image at {output_path}'
                _logger.warning(message)
                raise RuntimeError(message)

            # Publish the valid image as an artifact
            artifact = Artifact(self._kind, self._category, output_path.name)
            self._artifact_manager.publish(artifact, output_path, move=True)

        message = f'finished generating image for prompt={prompt} as artifact {artifact.name}'
        _logger.info(message)

        return artifact

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

class Generate:
    _DEFAULT_MAX_ATTEMPTS: Final[int] = 1

    def __init__(
        self,
        strategy: GenerationStrategy,
        max_attempts: int = _DEFAULT_MAX_ATTEMPTS,
    ) -> None:
        self._strategy = strategy
        self._max_attempts = max_attempts

    def __call__(self, state: State) -> State:
        # Check if the maximum number of attempts has been reached
        if state.generation_attempts >= self._max_attempts:
            message = f'reached the maximum of {self._max_attempts} attempt(s) for prompt={state.prompt}'
            _logger.error(message)
            raise RuntimeError(message)

        state.generation_attempts += 1

        # Retry with another generation if the strategy fails to produce an artifact
        try:
            state.artifact = self._strategy.generate(state.prompt)
        except Exception:
            message = f'attempt {state.generation_attempts}/{self._max_attempts} failed to generate an image for prompt={state.prompt}'
            _logger.warning(message, exc_info=True)
            return self(state)

        return state

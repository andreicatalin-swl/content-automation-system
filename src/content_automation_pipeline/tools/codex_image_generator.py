import uuid
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Final

import openai_codex
from langchain_core.tools import BaseTool, tool

from content_automation_pipeline.artifacts.artifact import Artifact, Kind
from content_automation_pipeline.artifacts.artifact_manager import ArtifactManager
from content_automation_pipeline.utilities.logger import create_logger

_logger = create_logger(__name__)

class CodexImageGenerator:
    # Hardcoded values that cannot be overridden by the user
    _IMAGE_EXTENSION: Final[str] = '.png'
    _INSTRUCTION_TEMPLATE: Final[str] = (
        'Generate an image using your built-in image generation tool.\n\n'
        "Description: '{prompt}'\n\n"
        'Save the image as a PNG file at the following path: {output_path}'
    )

    def __init__(self, artifact_manager: ArtifactManager, category: str) -> None:
        self._artifact_manager = artifact_manager
        self._category = category
        self._codex = openai_codex.Codex()

    def generate(self, prompt: str) -> Artifact:
        message = f'generating image for prompt={prompt!r}'
        _logger.info(message)

        with TemporaryDirectory() as tmp_dir:
            output_path = Path(tmp_dir) / f'{uuid.uuid4().hex}{self._IMAGE_EXTENSION}'
            instruction = self._INSTRUCTION_TEMPLATE.format(output_path=output_path, prompt=prompt)

            thread = self._codex.thread_start()
            thread.run(instruction)

            if not output_path.exists():
                message = f'codex did not produce an image at {output_path}'
                _logger.error(message)
                raise RuntimeError(message)

            artifact = Artifact(Kind.TEMPORARY, self._category, output_path.name)
            self._artifact_manager.publish(artifact, output_path, move=True)

        message = f'finished generating image for prompt={prompt!r}'
        _logger.info(message)

        return artifact

def create_generate_tool(codex_image_generator: CodexImageGenerator) -> BaseTool:
    @tool
    def generate(prompt: str) -> str:
        """Generate an image from a text prompt, save it as an artifact, and return a string summary of the result."""
        artifact = codex_image_generator.generate(prompt)
        return (
            f'Generated an image for {prompt!r} and saved it as artifact {artifact.name!r} '
            f'(kind={artifact.kind}, category={artifact.category!r}).'
        )

    return generate
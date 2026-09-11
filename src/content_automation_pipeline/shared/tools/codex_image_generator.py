import uuid
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Final

import openai_codex

from content_automation_pipeline.shared.artifacts.artifact import Artifact, Kind
from content_automation_pipeline.shared.artifacts.artifact_manager import (
    ArtifactManager,
)
from content_automation_pipeline.shared.utilities.logger import create_logger

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

    def generate(self, prompt: str) -> Artifact:
        message = f'generating image for prompt={prompt!r}'
        _logger.info(message)

        with TemporaryDirectory() as tmp_dir:
            output_path = Path(tmp_dir) / f'{uuid.uuid4().hex}{self._IMAGE_EXTENSION}'
            instruction = self._INSTRUCTION_TEMPLATE.format(output_path=output_path, prompt=prompt)

            try:
                with openai_codex.Codex() as codex:
                    thread = codex.thread_start()
                    thread.run(instruction)
            except openai_codex.CodexError as error:
                message = f'codex failed to generate an image for prompt={prompt!r}: {error}'
                _logger.error(message)
                raise

            artifact = Artifact(Kind.TEMPORARY, self._category, output_path.name)
            self._artifact_manager.publish(artifact, output_path, move=True)

        message = f'finished generating image for prompt={prompt!r}'
        _logger.info(message)

        return artifact

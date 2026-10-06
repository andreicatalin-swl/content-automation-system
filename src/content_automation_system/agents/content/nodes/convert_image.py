import uuid
from collections.abc import Callable, Generator
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Final

import imageio_ffmpeg  # type: ignore
import numpy as np
from numpy.typing import NDArray
from PIL import Image
from pydantic import BaseModel, ConfigDict

from content_automation_system.artifacts.artifact import Artifact, Kind
from content_automation_system.artifacts.artifact_manager import ArtifactManager
from content_automation_system.agents.content.models.evaluation import (
    Evaluation,
    Grade,
)
from content_automation_system.agents.content.nodes.abstract_evaluate import (
    AbstractEvaluate,
    EvaluationInput,
    EvaluationOutput,
)
from content_automation_system.shared.abstract_node import AbstractNode
from content_automation_system.utilities.logger import create_logger

_logger = create_logger(__name__)

class ImageConversionInput(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)

    image: Artifact
    duration: float
    fps: int

    def __repr__(self) -> str:
        return f'{self.image!r} for {self.duration}s at {self.fps}fps'

class ImageConversionOutput(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)

    video: Artifact

    def __repr__(self) -> str:
        return self.video.name

# TODO: Implement proper execute(...) -> ... method
class ConvertImage(AbstractNode[ImageConversionInput, ImageConversionOutput]):
    _WriteFrames = Callable[..., Generator[None, bytes | None, None]]

    def __init__(
        self,
        artifact_manager: ArtifactManager,
        category: str,
        kind: Kind,
    ) -> None:
        self._artifact_manager = artifact_manager
        self._category = category
        self._kind = kind

    def execute(self, input: ImageConversionInput) -> ImageConversionOutput:
        # Load the image and crop it to even sides
        with Image.open(self._artifact_manager.path(input.image)) as file:
            image: NDArray[np.uint8] = np.asarray(file.convert('RGB'), dtype=np.uint8)

        height = image.shape[0] - image.shape[0] % 2
        width = image.shape[1] - image.shape[1] % 2
        frame = image[:height, :width].tobytes()
        frames = max(round(input.duration * input.fps), 1)

        with TemporaryDirectory() as directory:
            output_path = Path(directory) / f'{uuid.uuid4().hex}.mp4'
            write_frames: ConvertImage._WriteFrames = imageio_ffmpeg.write_frames  # type: ignore
            writer = write_frames(
                str(output_path),
                (width, height),
                fps=input.fps,
                macro_block_size=1,
            )
            writer.send(None)

            # Write the image once per frame
            for _ in range(frames):
                writer.send(frame)

            writer.close()

            # Publish the video as an artifact
            artifact = Artifact(kind=self._kind, category=self._category, name=output_path.name)
            self._artifact_manager.publish(artifact, output_path, move=True)

        return ImageConversionOutput(video=artifact)

# TODO: Implement proper execute(...) method
class EvaluateConvertedImage(AbstractEvaluate[ImageConversionInput, ImageConversionOutput]):
    # Hardcoded values that cannot be overridden by the user
    _NO_FEEDBACK: Final[str] = 'there is no feedback.'

    def execute(self, input: EvaluationInput[ImageConversionInput, ImageConversionOutput]) -> EvaluationOutput:
        return EvaluationOutput(evaluation=Evaluation(grade=Grade.PASS, feedback=self._NO_FEEDBACK))

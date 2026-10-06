import uuid
from collections.abc import Callable, Generator, Iterator
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Final

import imageio_ffmpeg  # type: ignore
import numpy as np
from numpy.typing import NDArray
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

class FadeAnimationInput(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)

    video: Artifact
    fade_in: float
    fade_out: float
    color: tuple[int, int, int]

    def __repr__(self) -> str:
        return f'{self.video!r} fading in over {self.fade_in}s and out over {self.fade_out}s from {self.color}'

class FadeAnimationOutput(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)

    video: Artifact

    def __repr__(self) -> str:
        return self.video.name

# TODO: Implement proper execute(...) -> ... method
class AnimateFade(AbstractNode[FadeAnimationInput, FadeAnimationOutput]):
    _ReadFrames = Callable[..., Iterator[Any]]
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

    def execute(self, input: FadeAnimationInput) -> FadeAnimationOutput:
        # Open the video and take its size, frame rate and length
        read_frames: AnimateFade._ReadFrames = imageio_ffmpeg.read_frames  # type: ignore
        reader = read_frames(str(self._artifact_manager.path(input.video)))
        meta: dict[str, Any] = next(reader)
        size: tuple[int, int] = meta['size']
        fps: float = meta['fps']
        duration: float = meta['duration']
        width, height = size
        frames = max(round(duration * fps), 1)

        entering = round(input.fade_in * fps)
        leaving = round(input.fade_out * fps)
        color = np.asarray(input.color, dtype=np.float32)

        with TemporaryDirectory() as directory:
            output_path = Path(directory) / f'{uuid.uuid4().hex}.mp4'
            write_frames: AnimateFade._WriteFrames = imageio_ffmpeg.write_frames  # type: ignore
            writer = write_frames(
                str(output_path),
                (width, height),
                fps=fps,
                macro_block_size=1,
            )
            writer.send(None)

            for index, data in enumerate(reader):
                image: NDArray[np.float32] = np.frombuffer(data, dtype=np.uint8).reshape(
                    height,
                    width,
                    3,
                ).astype(np.float32)

                # Carry the frame from the colour at the start and back to it at the end
                towards_image = 1.0

                if entering and index < entering:
                    towards_image = index / entering
                elif leaving and index >= frames - leaving:
                    towards_image = max(frames - 1 - index, 0) / leaving

                faded = image * towards_image + color * (1.0 - towards_image)
                writer.send(faded.astype(np.uint8).tobytes())

            writer.close()

            # Publish the video as an artifact
            artifact = Artifact(kind=self._kind, category=self._category, name=output_path.name)
            self._artifact_manager.publish(artifact, output_path, move=True)

        return FadeAnimationOutput(video=artifact)

# TODO: Implement proper execute(...) method
class EvaluateAnimatedFade(AbstractEvaluate[FadeAnimationInput, FadeAnimationOutput]):
    # Hardcoded values that cannot be overridden by the user
    _NO_FEEDBACK: Final[str] = 'there is no feedback.'

    def execute(self, input: EvaluationInput[FadeAnimationInput, FadeAnimationOutput]) -> EvaluationOutput:
        return EvaluationOutput(evaluation=Evaluation(grade=Grade.PASS, feedback=self._NO_FEEDBACK))

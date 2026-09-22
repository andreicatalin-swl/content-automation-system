import math
import uuid
from collections.abc import Callable, Generator, Iterator
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Final

import imageio_ffmpeg  # type: ignore
import numpy as np
import torch
from numpy.typing import NDArray
from PIL import Image
from pydantic import BaseModel, ConfigDict
from transformers import pipeline

from content_automation_pipeline.artifacts.artifact import Artifact, Kind
from content_automation_pipeline.artifacts.artifact_manager import ArtifactManager
from content_automation_pipeline.content_agent.models.evaluation import (
    Evaluation,
    Grade,
)
from content_automation_pipeline.shared.abstract_node import AbstractNode
from content_automation_pipeline.utilities.logger import create_logger

_logger = create_logger(__name__)

_ReadFrames = Callable[..., Iterator[Any]]
_WriteFrames = Callable[..., Generator[None, bytes | None, None]]
_Estimate = Callable[..., dict[str, Any]]

class ParallaxAnimationInput(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)

    video: Artifact
    strength: float
    speed: float

    def __repr__(self) -> str:
        return f'{self.video!r} displaced by {self.strength} at {self.speed}'

class ParallaxAnimationOutput(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)

    video: Artifact

    def __repr__(self) -> str:
        return self.video.name

# TODO: Implement proper execute(...) -> ... method
class AnimateParallax(AbstractNode[ParallaxAnimationInput, ParallaxAnimationOutput]):
    # Default values that can be overridden by the user
    _MODEL: Final[str] = 'depth-anything/Depth-Anything-V2-Small-hf'
    _SMOOTHING: Final[float] = 0.2

    def __init__(
        self,
        artifact_manager: ArtifactManager,
        category: str,
        kind: Kind,
        model: str = _MODEL,
        smoothing: float = _SMOOTHING,
    ) -> None:
        self._artifact_manager = artifact_manager
        self._category = category
        self._kind = kind
        self._model = model
        self._smoothing = smoothing

    def execute(self, input: ParallaxAnimationInput) -> ParallaxAnimationOutput:
        # Open the video and take its size and frame rate
        read_frames: _ReadFrames = imageio_ffmpeg.read_frames  # type: ignore
        reader = read_frames(str(self._artifact_manager.path(input.video)))
        meta: dict[str, Any] = next(reader)
        size: tuple[int, int] = meta['size']
        fps: float = meta['fps']
        width, height = size

        # Load the depth model onto the graphics card when there is one
        device = 0 if torch.cuda.is_available() else -1
        message = f'loading {self._model} onto device {device}'
        _logger.info(message)

        estimate: _Estimate = pipeline('depth-estimation', model=self._model, device=device)

        # Place every pixel of the frame against the middle of the video
        horizontal = np.arange(width, dtype=np.float32)
        vertical = np.arange(height, dtype=np.float32)[:, None]
        smoothed: NDArray[np.float32] | None = None

        with TemporaryDirectory() as directory:
            output_path = Path(directory) / f'{uuid.uuid4().hex}.mp4'
            write_frames: _WriteFrames = imageio_ffmpeg.write_frames  # type: ignore
            writer = write_frames(
                str(output_path),
                (width, height),
                fps=fps,
                macro_block_size=1,
            )
            writer.send(None)

            for index, data in enumerate(reader):
                frame: NDArray[np.uint8] = np.frombuffer(data, dtype=np.uint8).reshape(height, width, 3)

                # Estimate the depth of the frame and carry it towards the depth of the frame before
                depth: NDArray[np.float32] = (
                    np.asarray(estimate(Image.fromarray(frame))['depth'], dtype=np.float32) / 255.0
                )

                if smoothed is None:
                    smoothed = depth
                else:
                    carried = smoothed * (1.0 - self._smoothing) + depth * self._smoothing
                    smoothed = carried.astype(np.float32, copy=False)

                # Orbit the camera around the middle of the video
                elapsed = index / fps * input.speed * 2.0 * math.pi
                towards_side = math.sin(elapsed) * input.strength * width
                towards_top = math.cos(elapsed) * input.strength * height

                # Hold the middle depth of the frame still and displace everything else around it
                relief = smoothed - float(np.median(smoothed))
                sampled_x = np.clip(horizontal + relief * towards_side, 0.0, width - 1.0)
                sampled_y = np.clip(vertical + relief * towards_top, 0.0, height - 1.0)

                # Sample the frame, one bilinear step per axis
                left = sampled_x.astype(np.int32)
                top = sampled_y.astype(np.int32)
                right = np.minimum(left + 1, width - 1)
                bottom = np.minimum(top + 1, height - 1)
                towards_right = (sampled_x - left)[:, :, None]
                towards_bottom = (sampled_y - top)[:, :, None]

                image = frame.astype(np.float32)
                above = image[top, left] * (1.0 - towards_right) + image[top, right] * towards_right
                below = image[bottom, left] * (1.0 - towards_right) + image[bottom, right] * towards_right
                moved = above * (1.0 - towards_bottom) + below * towards_bottom

                writer.send(moved.astype(np.uint8).tobytes())

            writer.close()

            # Publish the video as an artifact
            artifact = Artifact(kind=self._kind, category=self._category, name=output_path.name)
            self._artifact_manager.publish(artifact, output_path, move=True)

        return ParallaxAnimationOutput(video=artifact)

class AnimatedParallaxEvaluationInput(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)

    parallax_animation_input: ParallaxAnimationInput
    parallax_animation_output: ParallaxAnimationOutput
    instructions: str

    def __repr__(self) -> str:
        return f'{self.parallax_animation_output!r} against {self.instructions}'

class AnimatedParallaxEvaluationOutput(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)

    evaluation: Evaluation

    def __repr__(self) -> str:
        return repr(self.evaluation)

# TODO: Implement proper execute(...) -> ... method
class EvaluateAnimatedParallax(AbstractNode[AnimatedParallaxEvaluationInput, AnimatedParallaxEvaluationOutput]):
    # Hardcoded values that cannot be overridden by the user
    _NO_FEEDBACK: Final[str] = 'there is no feedback.'

    def execute(self, input: AnimatedParallaxEvaluationInput) -> AnimatedParallaxEvaluationOutput:
        return AnimatedParallaxEvaluationOutput(evaluation=Evaluation(grade=Grade.PASS, feedback=self._NO_FEEDBACK))

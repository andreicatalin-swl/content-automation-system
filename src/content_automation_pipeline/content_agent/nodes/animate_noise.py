import uuid
from collections.abc import Callable, Generator, Iterator
from enum import StrEnum
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

import imageio_ffmpeg  # type: ignore
import numpy as np
from numpy.typing import NDArray
from pydantic import BaseModel, ConfigDict

from content_automation_pipeline.artifacts.artifact import Artifact, Kind
from content_automation_pipeline.artifacts.artifact_manager import ArtifactManager
from content_automation_pipeline.shared.abstract_node import AbstractNode
from content_automation_pipeline.utilities.logger import create_logger

_logger = create_logger(__name__)

_ReadFrames = Callable[..., Iterator[Any]]
_WriteFrames = Callable[..., Generator[None, bytes | None, None]]

class MaskMode(StrEnum):
    BRIGHTNESS = 'brightness'

class NoiseAnimationInput(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)

    video: Artifact
    strength: float
    speed: float
    scale: float
    mask_threshold: float
    mask_softness: float
    mask_mode: MaskMode

    def __repr__(self) -> str:
        return f'{self.video!r} with {self.mask_mode} noise at strength {self.strength}'

class NoiseAnimationOutput(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)

    video: Artifact

    def __repr__(self) -> str:
        return self.video.name

class AnimateNoise(AbstractNode[NoiseAnimationInput, NoiseAnimationOutput]):
    def __init__(
        self,
        artifact_manager: ArtifactManager,
        category: str,
        kind: Kind,
    ) -> None:
        self._artifact_manager = artifact_manager
        self._category = category
        self._kind = kind

    def execute(self, input: NoiseAnimationInput) -> NoiseAnimationOutput:
        # Open the video and take its size and frame rate
        read_frames: _ReadFrames = imageio_ffmpeg.read_frames  # type: ignore
        reader = read_frames(str(self._artifact_manager.path(input.video)))
        meta: dict[str, Any] = next(reader)
        size: tuple[int, int] = meta['size']
        fps: float = meta['fps']
        width, height = size

        # Create the procedural noise as a lattice of random values
        columns = max(round(width / input.scale), 1)
        rows = max(round(height / input.scale), 1)
        generator = np.random.default_rng()
        previous = generator.random((rows + 1, columns + 1), dtype=np.float32)
        following = generator.random((rows + 1, columns + 1), dtype=np.float32)
        drawn = 0

        # Smoothstep the distance to the lattice
        horizontal = np.linspace(0.0, columns, width, endpoint=False, dtype=np.float32)
        vertical = np.linspace(0.0, rows, height, endpoint=False, dtype=np.float32)
        left = horizontal.astype(np.int32)
        top = vertical.astype(np.int32)
        towards_right = horizontal - left
        towards_bottom = (vertical - top)[:, None]
        towards_right = towards_right * towards_right * (3.0 - 2.0 * towards_right)
        towards_bottom = towards_bottom * towards_bottom * (3.0 - 2.0 * towards_bottom)

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
                image: NDArray[np.float32] = (
                    np.frombuffer(data, dtype=np.uint8).reshape(height, width, 3).astype(np.float32) / 255.0
                )

                # Identify where the effect should appear
                match input.mask_mode:
                    case MaskMode.BRIGHTNESS:
                        mask = self._brightness_mask(image, input.mask_threshold, input.mask_softness)
                    case _:
                        message = f'does not know the mask mode {input.mask_mode}'
                        _logger.error(message)
                        raise RuntimeError(message)

                # Animate the noise at the given speed
                elapsed = index / fps * input.speed

                while drawn < int(elapsed):
                    previous = following
                    following = generator.random((rows + 1, columns + 1), dtype=np.float32)
                    drawn += 1

                towards_following = elapsed - drawn
                towards_following = towards_following * towards_following * (3.0 - 2.0 * towards_following)
                layer = previous * (1.0 - towards_following) + following * towards_following

                # Stretch the layer over the frame, one bilinear step per axis
                above = layer[top][:, left] * (1.0 - towards_right) + layer[top][:, left + 1] * towards_right
                below = (
                    layer[top + 1][:, left] * (1.0 - towards_right)
                    + layer[top + 1][:, left + 1] * towards_right
                )
                noise = above * (1.0 - towards_bottom) + below * towards_bottom

                # Combine the noise with the mask and blend the result with the frame
                effect = 1.0 + input.strength * mask * (noise * 2.0 - 1.0)
                blended = np.clip(image * effect[:, :, None], 0.0, 1.0) * 255.0
                writer.send(blended.astype(np.uint8).tobytes())

            writer.close()

            # Publish the video as an artifact
            artifact = Artifact(kind=self._kind, category=self._category, name=output_path.name)
            self._artifact_manager.publish(artifact, output_path, move=True)

        return NoiseAnimationOutput(video=artifact)

    @staticmethod
    def _brightness_mask(
        image: NDArray[np.float32],
        threshold: float,
        softness: float,
    ) -> NDArray[np.float32]:
        brightness = image[:, :, 0] * 0.2126 + image[:, :, 1] * 0.7152 + image[:, :, 2] * 0.0722
        mask = np.clip((brightness - threshold) / max(softness, 1e-6), 0.0, 1.0)
        smoothed = mask * mask * (3.0 - 2.0 * mask)

        return smoothed.astype(np.float32, copy=False)

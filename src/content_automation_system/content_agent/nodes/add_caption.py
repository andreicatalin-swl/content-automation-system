import uuid
from collections.abc import Callable, Generator, Iterator
from enum import StrEnum
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Annotated, Any, Final

import imageio_ffmpeg  # type: ignore
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from pydantic import BaseModel, ConfigDict, Field

from content_automation_system.artifacts.artifact import Artifact, Kind
from content_automation_system.artifacts.artifact_manager import ArtifactManager
from content_automation_system.content_agent.models.evaluation import (
    Evaluation,
    Grade,
)
from content_automation_system.shared.abstract_node import AbstractNode


class CaptionPosition(StrEnum):
    UPPER_CENTER = 'upper_center'
    CENTER = 'center'
    LOWER_CENTER = 'lower_center'


class CaptionAdditionInput(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)

    video: Artifact
    caption: Annotated[str, Field(min_length=1)]
    position: CaptionPosition
    font_path: Path
    font_size: Annotated[int, Field(gt=0)]
    overlay_opacity: Annotated[float, Field(ge=0.0, le=1.0, allow_inf_nan=False)]
    horizontal_padding: Annotated[int, Field(ge=0)]
    vertical_padding: Annotated[int, Field(ge=0)]
    maximum_width: Annotated[float, Field(gt=0.0, le=1.0, allow_inf_nan=False)]

    def __repr__(self) -> str:
        return f'{self.caption!r} added to {self.video!r} at {self.position}'


class CaptionAdditionOutput(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)

    video: Artifact

    def __repr__(self) -> str:
        return self.video.name


# TODO: Implement proper execute(...) -> ... method
class AddCaption(AbstractNode[CaptionAdditionInput, CaptionAdditionOutput]):
    _ReadFrames = Callable[..., Iterator[Any]]
    _WriteFrames = Callable[..., Generator[None, bytes | None, None]]

    # Hardcoded values that cannot be overridden by the user
    _POSITION_HEIGHTS: Final[dict[CaptionPosition, float]] = {
        CaptionPosition.UPPER_CENTER: 0.25,
        CaptionPosition.CENTER: 0.5,
        CaptionPosition.LOWER_CENTER: 0.75,
    }

    def __init__(
        self,
        artifact_manager: ArtifactManager,
        category: str,
        kind: Kind,
    ) -> None:
        self._artifact_manager = artifact_manager
        self._category = category
        self._kind = kind

    def execute(self, input: CaptionAdditionInput) -> CaptionAdditionOutput:
        read_frames: AddCaption._ReadFrames = imageio_ffmpeg.read_frames  # type: ignore
        reader = read_frames(str(self._artifact_manager.path(input.video)))
        meta: dict[str, Any] = next(reader)
        width, height = meta['size']
        fps: float = meta['fps']
        font = ImageFont.truetype(input.font_path, input.font_size)

        with TemporaryDirectory() as directory:
            output_path = Path(directory) / f'{uuid.uuid4().hex}.mp4'
            write_frames: AddCaption._WriteFrames = imageio_ffmpeg.write_frames  # type: ignore
            writer = write_frames(
                str(output_path),
                (width, height),
                fps=fps,
                macro_block_size=1,
            )
            writer.send(None)

            for data in reader:
                frame = Image.fromarray(
                    np.frombuffer(data, dtype=np.uint8).reshape(height, width, 3),
                    mode='RGB',
                )
                self._draw_caption(frame, input, font)
                writer.send(np.asarray(frame, dtype=np.uint8).tobytes())

            writer.close()

            artifact = Artifact(kind=self._kind, category=self._category, name=output_path.name)
            self._artifact_manager.publish(artifact, output_path, move=True)

        return CaptionAdditionOutput(video=artifact)

    @classmethod
    def _draw_caption(
        cls,
        frame: Image.Image,
        input: CaptionAdditionInput,
        font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
    ) -> None:
        draw = ImageDraw.Draw(frame, 'RGBA')
        maximum_text_width = frame.width * input.maximum_width - input.horizontal_padding * 2
        caption = cls._wrap_text(draw, input.caption, font, maximum_text_width)
        spacing = max(round(input.font_size * 0.2), 1)
        left, top, right, bottom = draw.multiline_textbbox(
            (0, 0),
            caption,
            font=font,
            align='center',
            spacing=spacing,
        )
        text_width = right - left
        text_height = bottom - top
        center_x = frame.width / 2
        center_y = frame.height * cls._POSITION_HEIGHTS[input.position]
        rectangle = (
            round(center_x - text_width / 2 - input.horizontal_padding),
            round(center_y - text_height / 2 - input.vertical_padding),
            round(center_x + text_width / 2 + input.horizontal_padding),
            round(center_y + text_height / 2 + input.vertical_padding),
        )
        draw.rectangle(rectangle, fill=(0, 0, 0, round(input.overlay_opacity * 255)))
        draw.multiline_text(
            (center_x - (left + right) / 2, center_y - (top + bottom) / 2),
            caption,
            font=font,
            fill=(255, 255, 255, 255),
            align='center',
            spacing=spacing,
        )

    @staticmethod
    def _wrap_text(
        draw: ImageDraw.ImageDraw,
        caption: str,
        font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
        maximum_width: float,
    ) -> str:
        lines: list[str] = []

        for paragraph in caption.splitlines() or ['']:
            current = ''
            for word in paragraph.split():
                candidate = f'{current} {word}'.strip()
                if not current or draw.textlength(candidate, font=font) <= maximum_width:
                    current = candidate
                else:
                    lines.append(current)
                    current = word
            lines.append(current)

        return '\n'.join(lines)


class AddedCaptionEvaluationInput(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)

    caption_addition_input: CaptionAdditionInput
    caption_addition_output: CaptionAdditionOutput
    instructions: str

    def __repr__(self) -> str:
        return f'{self.caption_addition_output!r} against {self.instructions}'


class AddedCaptionEvaluationOutput(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)

    evaluation: Evaluation

    def __repr__(self) -> str:
        return repr(self.evaluation)


# TODO: Implement proper execute(...) -> ... method
class EvaluateAddedCaption(
    AbstractNode[AddedCaptionEvaluationInput, AddedCaptionEvaluationOutput],
):
    # Hardcoded values that cannot be overridden by the user
    _NO_FEEDBACK: Final[str] = 'there is no feedback.'

    def execute(self, input: AddedCaptionEvaluationInput) -> AddedCaptionEvaluationOutput:
        return AddedCaptionEvaluationOutput(
            evaluation=Evaluation(grade=Grade.PASS, feedback=self._NO_FEEDBACK),
        )

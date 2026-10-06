import math
import uuid
from collections.abc import Callable, Generator
from contextlib import closing
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Final

import imageio_ffmpeg  # type: ignore
from pydantic import BaseModel, ConfigDict, Field

from content_automation_system.artifacts.artifact import Artifact, Kind
from content_automation_system.artifacts.artifact_manager import ArtifactManager
from content_automation_system.content_agent.models.evaluation import (
    Evaluation,
    Grade,
)
from content_automation_system.content_agent.nodes.abstract_evaluate import (
    AbstractEvaluate,
    EvaluationInput,
)
from content_automation_system.shared.abstract_node import AbstractNode
from content_automation_system.utilities.logger import create_logger

_logger = create_logger(__name__)

class VideoJoiningInput(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)

    videos: list[Artifact] = Field(min_length=1)

    def __repr__(self) -> str:
        return ', '.join(repr(video) for video in self.videos)

class VideoJoiningOutput(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)

    video: Artifact

    def __repr__(self) -> str:
        return self.video.name

# TODO: Implement proper execute(...) -> ... method
class JoinVideos(AbstractNode[VideoJoiningInput, VideoJoiningOutput]):
    _ReadFrames = Callable[..., Generator[Any, None, None]]
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

    def execute(self, input: VideoJoiningInput) -> VideoJoiningOutput:
        paths = [self._artifact_manager.path(video) for video in input.videos]
        for path in paths:
            if not path.is_file():
                raise FileNotFoundError(f'video does not exist: {path}')

        # Use the first clip's canvas and frame rate for the whole timeline.
        read_frames: JoinVideos._ReadFrames = imageio_ffmpeg.read_frames  # type: ignore
        with closing(read_frames(str(paths[0]))) as first:
            meta: dict[str, Any] = next(first)
        size: tuple[int, int] = meta['size']
        fps: float = meta['fps']
        if not math.isfinite(fps) or fps <= 0:
            raise ValueError(f'cannot join videos with invalid frame rate: {fps}')
        width, height = size
        if width <= 0 or height <= 0 or width % 2 or height % 2:
            raise ValueError(f'joining videos requires positive, even canvas dimensions: {size}')

        # Raw video carries no frame boundaries. Feeding differently sized frames
        # to one writer shifts pixel rows and can combine pixels from two clips.
        # Fit each clip into the canvas without cropping or stretching its content.
        # Resample timestamps as well, so different source rates retain their timing.
        # Do this before scaling: some FFmpeg builds drop the last frame's duration
        # during scaling, which would make the fps filter discard that frame.
        filters = (
            f'setpts=PTS-STARTPTS,fps={fps},'
            f'scale={width}:{height}:force_original_aspect_ratio=decrease,'
            f'pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,setsar=1'
        )
        frame_bytes = width * height * 3

        with TemporaryDirectory() as directory:
            output_path = Path(directory) / f'{uuid.uuid4().hex}.mp4'
            write_frames: JoinVideos._WriteFrames = imageio_ffmpeg.write_frames  # type: ignore
            with closing(write_frames(
                str(output_path),
                size,
                fps=fps,
                macro_block_size=1,
                pix_fmt_in='rgb24',
            )) as writer:
                writer.send(None)

                # Keep only one decoder open, and close both processes on failure.
                for video, path in zip(input.videos, paths):
                    with closing(read_frames(
                        str(path),
                        pix_fmt='rgb24',
                        output_params=['-vf', filters],
                    )) as reader:
                        clip_meta = next(reader)
                        if clip_meta['size'] != size:
                            raise ValueError(f'video {video.name} did not normalize to {size}')
                        frames = 0
                        for data in reader:
                            if len(data) != frame_bytes:
                                raise ValueError(
                                    f'invalid frame in {video.name}: expected {frame_bytes} bytes, '
                                    f'got {len(data)}',
                                )
                            writer.send(data)
                            frames += 1
                        if frames == 0:
                            raise ValueError(f'video {video.name} contains no frames after normalization')
                        _logger.info('joined %s: %s frames at %s fps on %s', video.name, frames, fps, size)

            # Publish the video as an artifact
            artifact = Artifact(kind=self._kind, category=self._category, name=output_path.name)
            self._artifact_manager.publish(artifact, output_path, move=True)

        return VideoJoiningOutput(video=artifact)

# TODO: Implement proper evaluate(...) method
class EvaluateJoinedVideos(AbstractEvaluate[VideoJoiningInput, VideoJoiningOutput]):
    # Hardcoded values that cannot be overridden by the user
    _NO_FEEDBACK: Final[str] = 'there is no feedback.'

    def evaluate(self, input: EvaluationInput[VideoJoiningInput, VideoJoiningOutput]) -> Evaluation:
        return Evaluation(grade=Grade.PASS, feedback=self._NO_FEEDBACK)

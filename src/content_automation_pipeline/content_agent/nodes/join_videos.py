import uuid
from collections.abc import Callable, Generator, Iterator
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Final

import imageio_ffmpeg  # type: ignore
from pydantic import BaseModel, ConfigDict

from content_automation_pipeline.artifacts.artifact import Artifact, Kind
from content_automation_pipeline.artifacts.artifact_manager import ArtifactManager
from content_automation_pipeline.content_agent.models.evaluation import (
    Evaluation,
    Grade,
)
from content_automation_pipeline.shared.abstract_node import AbstractNode
from content_automation_pipeline.utilities.logger import create_logger

_logger = create_logger(__name__)

class VideoJoiningInput(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)

    videos: list[Artifact]

    def __repr__(self) -> str:
        return ', '.join(repr(video) for video in self.videos)

class VideoJoiningOutput(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)

    video: Artifact

    def __repr__(self) -> str:
        return self.video.name

# TODO: Implement proper execute(...) -> ... method
class JoinVideos(AbstractNode[VideoJoiningInput, VideoJoiningOutput]):
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

    def execute(self, input: VideoJoiningInput) -> VideoJoiningOutput:
        # Take the size and the frame rate of the first video
        read_frames: JoinVideos._ReadFrames = imageio_ffmpeg.read_frames  # type: ignore
        first = read_frames(str(self._artifact_manager.path(input.videos[0])))
        meta: dict[str, Any] = next(first)
        size: tuple[int, int] = meta['size']
        fps: float = meta['fps']
        del first

        with TemporaryDirectory() as directory:
            output_path = Path(directory) / f'{uuid.uuid4().hex}.mp4'
            write_frames: JoinVideos._WriteFrames = imageio_ffmpeg.write_frames  # type: ignore
            writer = write_frames(
                str(output_path),
                size,
                fps=fps,
                macro_block_size=1,
            )
            writer.send(None)

            # Write every frame of every video, in the order they were given
            for video in input.videos:
                reader = read_frames(str(self._artifact_manager.path(video)))
                next(reader)

                for data in reader:
                    writer.send(data)

            writer.close()

            # Publish the video as an artifact
            artifact = Artifact(kind=self._kind, category=self._category, name=output_path.name)
            self._artifact_manager.publish(artifact, output_path, move=True)

        return VideoJoiningOutput(video=artifact)

class JoinedVideosEvaluationInput(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)

    video_joining_input: VideoJoiningInput
    video_joining_output: VideoJoiningOutput
    instructions: str

    def __repr__(self) -> str:
        return f'{self.video_joining_output!r} against {self.instructions}'

class JoinedVideosEvaluationOutput(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)

    evaluation: Evaluation

    def __repr__(self) -> str:
        return repr(self.evaluation)

# TODO: Implement proper execute(...) -> ... method
class EvaluateJoinedVideos(AbstractNode[JoinedVideosEvaluationInput, JoinedVideosEvaluationOutput]):
    # Hardcoded values that cannot be overridden by the user
    _NO_FEEDBACK: Final[str] = 'there is no feedback.'

    def execute(self, input: JoinedVideosEvaluationInput) -> JoinedVideosEvaluationOutput:
        return JoinedVideosEvaluationOutput(evaluation=Evaluation(grade=Grade.PASS, feedback=self._NO_FEEDBACK))

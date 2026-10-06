import subprocess
import uuid
from collections.abc import Callable, Generator
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Final

import imageio_ffmpeg  # type: ignore
from pydantic import BaseModel, ConfigDict

from content_automation_system.artifacts.artifact import Artifact, Kind
from content_automation_system.artifacts.artifact_manager import ArtifactManager
from content_automation_system.content_agent.models.evaluation import (
    Evaluation,
    Grade,
)
from content_automation_system.shared.abstract_node import AbstractNode
from content_automation_system.utilities.logger import create_logger

_logger = create_logger(__name__)

class AudioAdditionInput(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)

    video: Artifact
    audio: Artifact

    def __repr__(self) -> str:
        return f'{self.audio!r} added to {self.video!r}'

class AudioAdditionOutput(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)

    video: Artifact

    def __repr__(self) -> str:
        return self.video.name

# TODO: Implement proper execute(...) -> ... method
class AddAudio(AbstractNode[AudioAdditionInput, AudioAdditionOutput]):
    _ReadFrames = Callable[..., Generator[Any, None, None]]

    def __init__(
        self,
        artifact_manager: ArtifactManager,
        category: str,
        kind: Kind,
    ) -> None:
        self._artifact_manager = artifact_manager
        self._category = category
        self._kind = kind

    def execute(self, input: AudioAdditionInput) -> AudioAdditionOutput:
        video_path = self._artifact_manager.path(input.video)
        read_frames: AddAudio._ReadFrames = imageio_ffmpeg.read_frames  # type: ignore
        reader = read_frames(str(video_path))
        meta: dict[str, Any] = next(reader)
        duration: float = meta['duration']
        reader.close()

        with TemporaryDirectory() as directory:
            output_path = Path(directory) / f'{uuid.uuid4().hex}.mp4'
            subprocess.run(
                [
                    imageio_ffmpeg.get_ffmpeg_exe(),
                    '-i',
                    str(video_path),
                    '-i',
                    str(self._artifact_manager.path(input.audio)),
                    '-map',
                    '0:v:0',
                    '-map',
                    '1:a:0',
                    '-c:v',
                    'copy',
                    '-c:a',
                    'aac',
                    '-af',
                    'apad',
                    '-t',
                    str(duration),
                    str(output_path),
                ],
                check=True,
                capture_output=True,
            )

            artifact = Artifact(kind=self._kind, category=self._category, name=output_path.name)
            self._artifact_manager.publish(artifact, output_path, move=True)

        return AudioAdditionOutput(video=artifact)

class AddedAudioEvaluationInput(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)

    audio_addition_input: AudioAdditionInput
    audio_addition_output: AudioAdditionOutput
    instructions: str

    def __repr__(self) -> str:
        return f'{self.audio_addition_output!r} against {self.instructions}'

class AddedAudioEvaluationOutput(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)

    evaluation: Evaluation

    def __repr__(self) -> str:
        return repr(self.evaluation)

# TODO: Implement proper execute(...) -> ... method
class EvaluateAddedAudio(AbstractNode[AddedAudioEvaluationInput, AddedAudioEvaluationOutput]):
    # Hardcoded values that cannot be overridden by the user
    _NO_FEEDBACK: Final[str] = 'there is no feedback.'

    def execute(self, input: AddedAudioEvaluationInput) -> AddedAudioEvaluationOutput:
        return AddedAudioEvaluationOutput(evaluation=Evaluation(grade=Grade.PASS, feedback=self._NO_FEEDBACK))

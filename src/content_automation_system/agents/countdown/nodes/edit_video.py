import json
import subprocess
from pathlib import Path
from typing import Any, Final

from pydantic import BaseModel, ConfigDict

from content_automation_system.artifacts.artifact import Artifact, Kind
from content_automation_system.artifacts.artifact_manager import ArtifactManager
from content_automation_system.agents.countdown.models.evaluation import (
    Evaluation,
    Grade,
)
from content_automation_system.agents.countdown.models.media_files import MediaFiles
from content_automation_system.agents.countdown.models.script import Script
from content_automation_system.agents.countdown.nodes.abstract_evaluate import (
    AbstractEvaluate,
    EvaluationInput,
    EvaluationOutput,
)
from content_automation_system.shared.abstract_node import AbstractNode
from content_automation_system.utilities.logger import create_logger

_logger = create_logger(__name__)

class VideoEditingInput(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)

    script: Script
    media_files: MediaFiles

    def __repr__(self) -> str:
        return f'{self.script!r} with {self.media_files!r}'

class VideoEditingOutput(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)

    video: Artifact

    def __repr__(self) -> str:
        return self.video.name

class EditVideo(AbstractNode[VideoEditingInput, VideoEditingOutput]):
    def __init__(
        self,
        artifact_manager: ArtifactManager,
        category: str,
        kind: Kind,
        script: Artifact,
    ) -> None:
        self._artifact_manager = artifact_manager
        self._category = category
        self._kind = kind
        self._script = script

    def execute(self, input: VideoEditingInput) -> VideoEditingOutput:
        # Build the payload with the script and audio/video media file paths
        payload: dict[str, Any] = {
            'script': input.script.model_dump(),
            'media_files': [
                {
                    'audio': str(self._artifact_manager.path(entry.audio)),
                    'video': str(self._artifact_manager.path(entry.video)),
                }
                for entry in input.media_files.entries
            ],
        }

        # Run the script with the payload
        result = subprocess.run(
            ['node', self._artifact_manager.path(self._script)],
            input=json.dumps(payload),
            check=True,
            stdout=subprocess.PIPE,
            encoding='utf-8',
        )

        # Capture the exported video path
        video_path = Path(result.stdout.strip())

        # Publish the exported video as an artifact
        artifact = Artifact(kind=self._kind, category=self._category, name=video_path.name)
        self._artifact_manager.publish(artifact, video_path, move=True)

        return VideoEditingOutput(video=artifact)

# TODO: Implement proper execute(...) method
class EvaluateEditedVideo(AbstractEvaluate[VideoEditingInput, VideoEditingOutput]):
    # Hardcoded values that cannot be overridden by the user
    _NO_FEEDBACK: Final[str] = 'there is no feedback.'

    def execute(self, input: EvaluationInput[VideoEditingInput, VideoEditingOutput]) -> EvaluationOutput:
        return EvaluationOutput(evaluation=Evaluation(grade=Grade.PASS, feedback=self._NO_FEEDBACK))

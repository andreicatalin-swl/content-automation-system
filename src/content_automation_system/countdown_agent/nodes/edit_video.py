import json
import subprocess
import uuid
from pathlib import Path
from tempfile import mkdtemp
from typing import Any, Final

from pydantic import BaseModel, ConfigDict

from content_automation_system.artifacts.artifact import Artifact, Kind
from content_automation_system.artifacts.artifact_manager import ArtifactManager
from content_automation_system.countdown_agent.models.evaluation import (
    Evaluation,
    Grade,
)
from content_automation_system.countdown_agent.models.media_files import MediaFiles
from content_automation_system.countdown_agent.models.script import Script
from content_automation_system.countdown_agent.nodes.abstract_evaluate import (
    AbstractEvaluate,
    EvaluationInput,
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

# TODO: Implement proper _run_script(...) method
class EditVideo(AbstractNode[VideoEditingInput, VideoEditingOutput]):
    def __init__(
        self,
        artifact_manager: ArtifactManager,
        category: str,
        kind: Kind,
    ) -> None:
        self._artifact_manager = artifact_manager
        self._category = category
        self._kind = kind

    def execute(self, input: VideoEditingInput) -> VideoEditingOutput:
        video_path = self._run_script(input)

        # Publish the exported video as an artifact
        artifact = Artifact(kind=self._kind, category=self._category, name=video_path.name)
        self._artifact_manager.publish(artifact, video_path, move=True)

        return VideoEditingOutput(video=artifact)

    def _run_script(self, input: VideoEditingInput) -> Path:
        script_path = Path(__file__).parent.parent / 'scripts' / 'countdown_10.js'
        video_path = Path(mkdtemp()) / f'{uuid.uuid4().hex}.mp4'

        # Premiere relinks and exports through native paths, so a posix path silently fails there
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

        result = subprocess.run(
            ['node', str(script_path), json.dumps(payload), str(video_path)],
            check=False,
            capture_output=True,
            text=True,
        )

        if result.returncode:
            message = (
                f'the editing script exited with code {result.returncode}\n'
                f'{result.stderr.strip()}'
            )
            _logger.error(message)
            raise RuntimeError(message)

        return video_path

# TODO: Implement proper evaluate(...) method
class EvaluateEditedVideo(AbstractEvaluate[VideoEditingInput, VideoEditingOutput]):
    # Hardcoded values that cannot be overridden by the user
    _NO_FEEDBACK: Final[str] = 'there is no feedback.'

    def evaluate(self, input: EvaluationInput[VideoEditingInput, VideoEditingOutput]) -> Evaluation:
        return Evaluation(grade=Grade.PASS, feedback=self._NO_FEEDBACK)

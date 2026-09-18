import json
import subprocess
import uuid
from pathlib import Path
from tempfile import mkdtemp
from typing import Any, Final

from pydantic import BaseModel, ConfigDict

from content_automation_pipeline.artifacts.artifact import Artifact, Kind
from content_automation_pipeline.artifacts.artifact_manager import ArtifactManager
from content_automation_pipeline.content_agent.models.evaluation import (
    Evaluation,
    Grade,
)
from content_automation_pipeline.content_agent.models.media_files import MediaFiles
from content_automation_pipeline.content_agent.models.script import Script
from content_automation_pipeline.shared.node import Node, Strategy
from content_automation_pipeline.utilities.logger import create_logger

_logger = create_logger(__name__)

class VideoEditingInput(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)

    script: Script
    media_files: MediaFiles

class VideoEditingOutput(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)

    video: Artifact

# TODO: Implement proper _run_script(...) method
class VideoEditingStrategy(Strategy[VideoEditingInput, VideoEditingOutput]):
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

        # The script only understands real file paths, so resolve every artifact before handing it over
        payload: dict[str, Any] = {
            'script': input.script.model_dump(),
            'media_files': [
                {
                    'audio': self._artifact_manager.path(entry.audio).as_posix(),
                    'video': self._artifact_manager.path(entry.video).as_posix(),
                }
                for entry in input.media_files.entries
            ],
        }

        subprocess.run(
            ['node', str(script_path), json.dumps(payload), video_path.as_posix()],
            check=True,
            capture_output=True,
        )

        return video_path

class EditVideo(Node[VideoEditingInput, VideoEditingOutput]):
    def __init__(
        self,
        strategy: Strategy[VideoEditingInput, VideoEditingOutput],
    ) -> None:
        super().__init__(strategy)

class EditedVideoEvaluationInput(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)

    # Input for the EditVideo node
    video_editing_input: VideoEditingInput
    # Output from the EditVideo node
    video_editing_output: VideoEditingOutput
    # Instructions for evaluating output given the input
    evaluation_instructions: str

class EditedVideoEvaluationOutput(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)

    evaluation: Evaluation

# TODO: Implement proper execute(...) method
class EditedVideoEvaluationStrategy(Strategy[EditedVideoEvaluationInput, EditedVideoEvaluationOutput]):
    # Hardcoded values that cannot be overridden by the user
    _NO_FEEDBACK: Final[str] = 'there is no feedback.'

    def execute(self, input: EditedVideoEvaluationInput) -> EditedVideoEvaluationOutput:
        return EditedVideoEvaluationOutput(evaluation=Evaluation(grade=Grade.PASS, feedback=self._NO_FEEDBACK))

class EvaluateEditedVideo(Node[EditedVideoEvaluationInput, EditedVideoEvaluationOutput]):
    def __init__(
        self,
        strategy: Strategy[EditedVideoEvaluationInput, EditedVideoEvaluationOutput],
    ) -> None:
        super().__init__(strategy)

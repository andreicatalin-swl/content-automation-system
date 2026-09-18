import json
import subprocess
import uuid
from pathlib import Path
from tempfile import mkdtemp
from typing import Any

from content_automation_pipeline.artifacts.artifact import Artifact, Kind
from content_automation_pipeline.artifacts.artifact_manager import ArtifactManager
from content_automation_pipeline.content_agent.models.video_editing_input import (
    VideoEditingInput,
)
from content_automation_pipeline.shared.node import Node, Strategy
from content_automation_pipeline.utilities.logger import create_logger

_logger = create_logger(__name__)

class _Strategy(Strategy[VideoEditingInput, Artifact]):
    def __init__(
        self,
        artifact_manager: ArtifactManager,
        category: str,
        kind: Kind,
    ) -> None:
        self._artifact_manager = artifact_manager
        self._category = category
        self._kind = kind

    def execute(self, input: VideoEditingInput) -> Artifact:
        video_path = self._run_script(input)

        # Publish the exported video as an artifact
        artifact = Artifact(kind=self._kind, category=self._category, name=video_path.name)
        self._artifact_manager.publish(artifact, video_path, move=True)

        return artifact

    # TODO: Replace with the real script invocation
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

class EditVideo(Node[VideoEditingInput, Artifact]):
    def __init__(
        self,
        artifact_manager: ArtifactManager,
        category: str,
        kind: Kind,
    ) -> None:
        super().__init__(_Strategy(artifact_manager, category, kind))

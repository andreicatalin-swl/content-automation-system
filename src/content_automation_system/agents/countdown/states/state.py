from pydantic import BaseModel, ConfigDict

from content_automation_system.agents.countdown.models.evaluation import Evaluation
from content_automation_system.agents.countdown.models.media_files import MediaFiles
from content_automation_system.agents.countdown.models.media_links import MediaLinks
from content_automation_system.agents.countdown.models.script import Script
from content_automation_system.artifacts.artifact import Artifact
from content_automation_system.utilities.logger import create_logger

_logger = create_logger(__name__)

class State(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True, validate_assignment=True)

    generation_instructions: str
    script_evaluation_instructions: str
    media_finding_instructions: str
    found_media_evaluation_instructions: str
    downloaded_media_evaluation_instructions: str
    edited_video_evaluation_instructions: str
    script: Script | None = None
    media_links: MediaLinks | None = None
    media_files: MediaFiles | None = None
    video: Artifact | None = None
    evaluation: Evaluation | None = None

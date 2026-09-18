from pydantic import BaseModel, ConfigDict

from content_automation_pipeline.content_agent.models.media_files import MediaFiles
from content_automation_pipeline.content_agent.models.media_links import MediaLinks
from content_automation_pipeline.utilities.logger import create_logger

_logger = create_logger(__name__)

class DownloadedMediaEvaluationInput(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)

    media_links: MediaLinks
    media_files: MediaFiles
    evaluation_instructions: str

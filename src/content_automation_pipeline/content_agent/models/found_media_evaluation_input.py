from pydantic import BaseModel, ConfigDict

from content_automation_pipeline.content_agent.models.media_finding_input import (
    MediaFindingInput,
)
from content_automation_pipeline.content_agent.models.media_links import MediaLinks
from content_automation_pipeline.utilities.logger import create_logger

_logger = create_logger(__name__)

class FoundMediaEvaluationInput(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)

    media_finding_input: MediaFindingInput
    media_links: MediaLinks
    evaluation_instructions: str

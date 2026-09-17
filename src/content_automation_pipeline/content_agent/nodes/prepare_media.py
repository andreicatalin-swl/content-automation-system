from pydantic import BaseModel, ConfigDict

from content_automation_pipeline.artifacts.artifact import Kind
from content_automation_pipeline.artifacts.artifact_manager import ArtifactManager
from content_automation_pipeline.content_agent.models.media import Media
from content_automation_pipeline.content_agent.models.script import Script
from content_automation_pipeline.shared.node import Strategy
from content_automation_pipeline.shared.rate_limited_node import RateLimitedNode
from content_automation_pipeline.utilities.logger import create_logger

_logger = create_logger(__name__)

class MediaPreparationInput(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)

    script: Script
    instructions: str

class _Strategy(Strategy[MediaPreparationInput, Media]):
    def __init__(
        self,
        artifact_manager: ArtifactManager,
        category: str,
        kind: Kind,
    ) -> None:
        self._artifact_manager = artifact_manager
        self._category = category
        self._kind = kind

    def execute(self, input: MediaPreparationInput) -> Media:
        ...

class PrepareMedia(RateLimitedNode[MediaPreparationInput, Media]):
    def __init__(
        self,
        artifact_manager: ArtifactManager,
        category: str,
        kind: Kind,
        max_calls: int = RateLimitedNode._DEFAULT_MAX_CALLS,
    ) -> None:
        super().__init__(_Strategy(artifact_manager, category, kind), max_calls)

from enum import StrEnum

from pydantic import BaseModel, ConfigDict

from content_automation_pipeline.utilities.logger import create_logger

_logger = create_logger(__name__)

class Kind(StrEnum):
    TEMPORARY = 'temporary'
    PERSISTENT = 'persistent'

class Artifact(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True, frozen=True)

    kind: Kind
    category: str
    name: str

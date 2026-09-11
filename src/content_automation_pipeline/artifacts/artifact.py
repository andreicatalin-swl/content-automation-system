from dataclasses import dataclass
from enum import StrEnum

from content_automation_pipeline.utilities.logger import create_logger

_logger = create_logger(__name__)

class Kind(StrEnum):
    TEMPORARY = 'temporary'
    PERSISTENT = 'persistent'

@dataclass(frozen=True, slots=True)
class Artifact:
    kind: Kind
    category: str
    name: str

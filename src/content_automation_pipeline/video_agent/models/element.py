from dataclasses import dataclass

from content_automation_pipeline.utilities.logger import create_logger

_logger = create_logger(__name__)

@dataclass(frozen=True, slots=True)
class Element:
    pass

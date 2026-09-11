from enum import StrEnum

from content_automation_pipeline.shared.utilities.logger import create_logger

_logger = create_logger(__name__)

class Grade(StrEnum):
    PASS = 'pass'
    FAIL = 'fail'

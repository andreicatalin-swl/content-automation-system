from enum import StrEnum

from pydantic import BaseModel, ConfigDict

from content_automation_pipeline.utilities.logger import create_logger

_logger = create_logger(__name__)

class Grade(StrEnum):
    PASS = 'pass'
    FAIL = 'fail'

class Evaluation(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)

    grade: Grade
    feedback: str

    def __str__(self) -> str:
        return f'{self.grade} - {self.feedback}'

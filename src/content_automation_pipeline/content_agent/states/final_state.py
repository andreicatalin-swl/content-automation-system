from typing import Generic, TypedDict, TypeVar

from pydantic import BaseModel

from content_automation_pipeline.utilities.logger import create_logger

_logger = create_logger(__name__)

T = TypeVar('T', bound=BaseModel)

class FinalState(TypedDict, Generic[T]):
    content: T

from abc import abstractmethod
from typing import Protocol, TypeVar

from content_automation_pipeline.utilities.logger import create_logger

_logger = create_logger(__name__)

T = TypeVar('T', contravariant=True)
U = TypeVar('U', covariant=True)

class Executable(Protocol[T, U]):
    @abstractmethod
    def __call__(self, input: T) -> U:
        ...

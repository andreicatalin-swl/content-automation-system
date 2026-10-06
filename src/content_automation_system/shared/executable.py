from abc import abstractmethod
from typing import Protocol, TypeVar

from content_automation_system.utilities.logger import create_logger

_logger = create_logger(__name__)

T_contra = TypeVar('T_contra', contravariant=True)
U_co = TypeVar('U_co', covariant=True)

class Executable(Protocol[T_contra, U_co]):
    @abstractmethod
    def __call__(self, input: T_contra) -> U_co:
        ...

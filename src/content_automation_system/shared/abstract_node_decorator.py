from typing import TypeVar

from content_automation_system.shared.executable import Executable
from content_automation_system.utilities.logger import create_logger

_logger = create_logger(__name__)

T = TypeVar('T')
U = TypeVar('U')

class AbstractNodeDecorator(Executable[T, U]):
    def __init__(
        self,
        executable: Executable[T, U],
    ) -> None:
        self._executable = executable

    def __call__(self, input: T) -> U:
        return self._executable(input)

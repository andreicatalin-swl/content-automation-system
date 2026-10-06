from typing import Final, TypeVar

from content_automation_system.shared.abstract_node_decorator import (
    AbstractNodeDecorator,
)
from content_automation_system.shared.executable import Executable
from content_automation_system.utilities.logger import create_logger

_logger = create_logger(__name__)

T = TypeVar('T')
U = TypeVar('U')

class RateLimitingNodeDecorator(AbstractNodeDecorator[T, U]):
    _DEFAULT_MAX_CALLS: Final[int] = 1

    def __init__(
        self,
        executable: Executable[T, U],
        max_calls: int = _DEFAULT_MAX_CALLS,
    ) -> None:
        super().__init__(executable)
        self._max_calls = max_calls
        self._calls = 0

    def __call__(self, input: T) -> U:
        if self._calls >= self._max_calls:
            message = f'reached the maximum of {self._max_calls} call(s)'
            _logger.error(message)
            raise RuntimeError(message)

        self._calls += 1

        return super().__call__(input)

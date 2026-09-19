from abc import abstractmethod
from typing import TypeVar

from content_automation_pipeline.shared.executable import Executable
from content_automation_pipeline.utilities.logger import create_logger

_logger = create_logger(__name__)

T = TypeVar('T')
U = TypeVar('U')

class AbstractNode(Executable[T, U]):
    def __call__(self, input: T) -> U:
        message = f'executing node for input={input!r}'
        _logger.info(message)

        result = self.execute(input)

        message = f'finished executing node for input={input!r}'
        _logger.info(message)

        return result

    @abstractmethod
    def execute(self, input: T) -> U:
        ...

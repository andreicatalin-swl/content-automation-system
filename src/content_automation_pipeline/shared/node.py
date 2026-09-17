from abc import ABC, abstractmethod
from typing import Generic, TypeVar

from content_automation_pipeline.utilities.logger import create_logger

_logger = create_logger(__name__)

T = TypeVar('T')
U = TypeVar('U')

class Strategy(ABC, Generic[T, U]):
    @abstractmethod
    def execute(self, input: T) -> U:
        ...

class Node(Generic[T, U]):
    def __init__(
        self,
        strategy: Strategy[T, U],
    ) -> None:
        self._strategy = strategy

    def __call__(self, input: T) -> U:
        message = f'executing node for input={input}'
        _logger.info(message)

        result = self._strategy.execute(input)

        message = f'finished executing node for input={input}'
        _logger.info(message)

        return result

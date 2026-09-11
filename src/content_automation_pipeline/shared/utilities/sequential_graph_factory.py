from collections.abc import Callable
from typing import Generic, Self, TypeVar

from langgraph.graph import END, START, StateGraph  # type: ignore
from langgraph.graph.state import CompiledStateGraph  # type: ignore
from pydantic import BaseModel

from content_automation_pipeline.shared.utilities.logger import create_logger

_logger = create_logger(__name__)

T = TypeVar('T', bound=BaseModel)

class SequentialGraphFactory(Generic[T]):
    def __init__(self, state_type: type[T]) -> None:
        self._nodes: list[tuple[str, Callable[[T], T]]] = []
        self._graph = StateGraph(state_type)

    def add_node(self, name: str, node: Callable[[T], T]) -> Self:
        self._nodes.append((name, node))
        return self

    def compile(self) -> CompiledStateGraph:  # type: ignore
        message = f'compiling sequential graph with {len(self._nodes)} node(s)'
        _logger.info(message)

        # Add nodes to the graph sequentially
        previous = START
        for name, node in self._nodes:
            self._graph.add_node(name, node)  # type: ignore
            self._graph.add_edge(previous, name)
            previous = name
        self._graph.add_edge(previous, END)

        compiled: CompiledStateGraph = self._graph.compile()  # type: ignore

        message = f'finished compiling sequential graph with {len(self._nodes)} node(s)'
        _logger.info(message)

        return compiled  # type: ignore

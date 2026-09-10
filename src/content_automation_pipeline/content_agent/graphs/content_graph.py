from typing import Final, Generic, TypeVar

from langgraph.graph import END, START, StateGraph  # type: ignore
from pydantic import BaseModel

from content_automation_pipeline.content_agent.nodes.content_generator import (
    ContentGenerator,
)
from content_automation_pipeline.content_agent.states.final_state import FinalState
from content_automation_pipeline.content_agent.states.initial_state import InitialState
from content_automation_pipeline.content_agent.states.state import State
from content_automation_pipeline.utilities.logger import create_logger

_logger = create_logger(__name__)

T = TypeVar('T', bound=BaseModel)

class ContentGraph(Generic[T]):
    # Hardcoded values that cannot be overridden by the user
    _CONTENT_GENERATOR_NODE: Final[str] = 'content_generator'

    def __init__(self) -> None:
        graph = StateGraph(State, input_schema=InitialState, output_schema=FinalState)  # type: ignore
        graph.add_node(self._CONTENT_GENERATOR_NODE, ContentGenerator[T]())  # type: ignore
        graph.add_edge(START, self._CONTENT_GENERATOR_NODE)
        graph.add_edge(self._CONTENT_GENERATOR_NODE, END)

        self._graph = graph.compile()  # type: ignore

    def invoke(self, initial_state: InitialState[T]) -> FinalState[T]:
        message = 'invoking content graph'
        _logger.info(message)

        final_state: FinalState[T] = self._graph.invoke(initial_state)  # type: ignore

        message = 'finished invoking content graph'
        _logger.info(message)

        return final_state

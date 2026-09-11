from typing import Final

from langgraph.graph import END, START, StateGraph  # type: ignore
from langgraph.graph.state import CompiledStateGraph  # type: ignore

from content_automation_pipeline.shared.artifacts.artifact import Kind
from content_automation_pipeline.shared.artifacts.artifact_manager import (
    ArtifactManager,
)
from content_automation_pipeline.shared.t2i_agent.nodes.decide import Decide
from content_automation_pipeline.shared.t2i_agent.nodes.evaluate import Evaluate
from content_automation_pipeline.shared.t2i_agent.nodes.generate import Generate
from content_automation_pipeline.shared.t2i_agent.states.state import State
from content_automation_pipeline.shared.utilities.logger import create_logger

_logger = create_logger(__name__)

class Graph:
    # Default values that can be overridden by the user
    _KIND: Final[Kind] = Kind.TEMPORARY
    _MAX_GENERATION_ATTEMPTS: Final[int] = 1
    _MAX_EVALUATION_ATTEMPTS: Final[int] = 1

    # Hardcoded values that cannot be overridden by the user
    _GENERATE_NODE: Final[str] = 'generate'
    _EVALUATE_NODE: Final[str] = 'evaluate'

    def __init__(
        self,
        artifact_manager: ArtifactManager,
        category: str,
        kind: Kind = _KIND,
        max_generation_attempts: int = _MAX_GENERATION_ATTEMPTS,
        max_evaluation_attempts: int = _MAX_EVALUATION_ATTEMPTS,
    ) -> None:
        message = 'building the T2I graph'
        _logger.info(message)

        generate = Generate(artifact_manager, category, kind, max_generation_attempts)
        evaluate = Evaluate(artifact_manager, max_evaluation_attempts)

        graph = StateGraph(State)
        graph.add_node(self._GENERATE_NODE, generate)  # type: ignore
        graph.add_node(self._EVALUATE_NODE, evaluate)  # type: ignore

        # Generate an image and evaluate it, repeating the generation until it passes
        graph.add_edge(START, self._GENERATE_NODE)
        graph.add_edge(self._GENERATE_NODE, self._EVALUATE_NODE)
        graph.add_conditional_edges(self._EVALUATE_NODE, Decide(self._GENERATE_NODE), [self._GENERATE_NODE, END])

        self._compiled_state_graph: CompiledStateGraph[State, None, State, State] = graph.compile()  # type: ignore

        message = 'finished building the T2I graph'
        _logger.info(message)

    def get_compiled_state_graph(self) -> CompiledStateGraph[State, None, State, State]:
        return self._compiled_state_graph

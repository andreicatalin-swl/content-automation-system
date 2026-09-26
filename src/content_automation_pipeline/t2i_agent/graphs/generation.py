from typing import Any, Final

from langgraph.graph import END, START, StateGraph  # type: ignore
from langgraph.graph.state import CompiledStateGraph  # type: ignore

from content_automation_pipeline.artifacts.artifact import Kind
from content_automation_pipeline.artifacts.artifact_manager import ArtifactManager
from content_automation_pipeline.shared.rate_limiting_node_decorator import (
    RateLimitingNodeDecorator,
)
from content_automation_pipeline.t2i_agent.nodes.generate import (
    Generate,
    GenerationInput,
)
from content_automation_pipeline.t2i_agent.states.generation import GenerationState
from content_automation_pipeline.utilities.logger import create_logger

_logger = create_logger(__name__)


class Generation:
    # Default values that can be overridden by the user
    _GENERATE_KIND: Final[Kind] = Kind.TEMPORARY
    _GENERATE_MAX_CALLS: Final[int] = 1

    # Hardcoded values that cannot be overridden by the user
    _GENERATE_NODE: Final[str] = 'generate'

    def __init__(
        self,
        generate_artifact_manager: ArtifactManager,
        generate_category: str,
        generate_kind: Kind = _GENERATE_KIND,
        generate_max_calls: int = _GENERATE_MAX_CALLS,
    ) -> None:
        _logger.info('building the t2i generation graph')

        self._generate = RateLimitingNodeDecorator(
            Generate(generate_artifact_manager, generate_category, generate_kind),
            generate_max_calls,
        )

        graph = StateGraph(GenerationState)
        graph.add_node(self._GENERATE_NODE, self._run_generate)  # type: ignore
        graph.add_edge(START, self._GENERATE_NODE)
        graph.add_edge(self._GENERATE_NODE, END)

        self._compiled_state_graph: CompiledStateGraph[
            GenerationState,
            None,
            GenerationState,
            GenerationState,
        ] = graph.compile()  # type: ignore

        _logger.info('finished building the t2i generation graph')

    def get_compiled_state_graph(
        self,
    ) -> CompiledStateGraph[GenerationState, None, GenerationState, GenerationState]:
        return self._compiled_state_graph

    def _run_generate(self, state: GenerationState) -> dict[str, Any]:
        output = self._generate(
            GenerationInput(
                instructions=state.generation_instructions,
                feedback=state.feedback,
                reference_images=state.reference_images,
            ),
        )

        return {'image': output.image}

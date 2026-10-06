from typing import Any, Final, TypeVar

from langgraph.graph import END, START, StateGraph  # type: ignore
from langgraph.graph.state import CompiledStateGraph  # type: ignore

from content_automation_system.agents.i2i.nodes.abstract_evaluate import EvaluationInput
from content_automation_system.agents.i2i.nodes.decide import (
    Decide,
    DecisionInput,
)
from content_automation_system.agents.i2i.nodes.generate import (
    Evaluate,
    Generate,
    GenerationInput,
    GenerationOutput,
)
from content_automation_system.agents.i2i.states.state import State
from content_automation_system.artifacts.artifact import Kind
from content_automation_system.artifacts.artifact_manager import ArtifactManager
from content_automation_system.shared.rate_limiting_node_decorator import (
    RateLimitingNodeDecorator,
)
from content_automation_system.utilities.logger import create_logger

_logger = create_logger(__name__)

T = TypeVar('T')

class Graph:
    # Default values that can be overridden by the user
    _GENERATE_KIND: Final[Kind] = Kind.TEMPORARY
    _GENERATE_MAX_CALLS: Final[int] = 1

    # Hardcoded values that cannot be overridden by the user
    _GENERATE_NODE: Final[str] = 'generate'
    _EVALUATE_NODE: Final[str] = 'evaluate'

    def __init__(
        self,
        generate_artifact_manager: ArtifactManager,
        generate_category: str,
        generate_kind: Kind = _GENERATE_KIND,
        generate_max_calls: int = _GENERATE_MAX_CALLS,
        *,
        evaluate_artifact_manager: ArtifactManager,
    ) -> None:
        message = 'building the i2i graph'
        _logger.info(message)

        self._generate = RateLimitingNodeDecorator(
            Generate(generate_artifact_manager, generate_category, generate_kind),
            generate_max_calls,
        )
        self._evaluate = Evaluate(evaluate_artifact_manager)
        self._decide = Decide(END, self._GENERATE_NODE)

        graph = StateGraph(State)
        graph.add_node(self._GENERATE_NODE, self._run_generate)  # type: ignore
        graph.add_node(self._EVALUATE_NODE, self._run_evaluate)  # type: ignore

        graph.add_edge(START, self._GENERATE_NODE)
        graph.add_edge(self._GENERATE_NODE, self._EVALUATE_NODE)
        graph.add_conditional_edges(
            self._EVALUATE_NODE,
            self._run_decide,
            [END, self._GENERATE_NODE],
        )

        self._compiled_state_graph: CompiledStateGraph[State, None, State, State] = graph.compile()  # type: ignore

        message = 'finished building the i2i graph'
        _logger.info(message)

    def get_compiled_state_graph(self) -> CompiledStateGraph[State, None, State, State]:
        return self._compiled_state_graph

    def _run_generate(self, state: State) -> dict[str, Any]:
        output = self._generate(
            GenerationInput(
                images=state.images,
                instructions=state.generation_instructions,
                feedback=state.feedback,
            ),
        )

        return {'image': output.image}

    def _run_evaluate(self, state: State) -> dict[str, Any]:
        output = self._evaluate(
            EvaluationInput[GenerationInput, GenerationOutput](
                node_input=GenerationInput(
                    images=state.images,
                    instructions=state.generation_instructions,
                    feedback=state.feedback,
                ),
                node_output=GenerationOutput(image=self._require(state.image, 'image')),
                evaluation_instructions=state.evaluation_instructions,
            ),
        )

        return {
            'evaluation': output.evaluation,
            'feedback': [*state.feedback, output.evaluation.feedback],
        }

    def _run_decide(self, state: State) -> str:
        output = self._decide(DecisionInput(evaluation=self._require(state.evaluation, 'evaluation')))

        return output.destination

    @staticmethod
    def _require(value: T | None, name: str) -> T:
        if value is None:
            message = f'the state has no {name}'
            _logger.error(message)
            raise RuntimeError(message)

        return value

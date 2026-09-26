from typing import Any, Final, TypeVar

from langgraph.graph import END, START, StateGraph  # type: ignore
from langgraph.graph.state import CompiledStateGraph  # type: ignore
from pydantic import ConfigDict

from content_automation_pipeline.artifacts.artifact import Kind
from content_automation_pipeline.artifacts.artifact_manager import ArtifactManager
from content_automation_pipeline.t2i_agent.graphs.generation import (
    Generation,
    GenerationState,
)
from content_automation_pipeline.t2i_agent.models.evaluation import Evaluation
from content_automation_pipeline.t2i_agent.nodes.decide import (
    Decide,
    DecisionInput,
)
from content_automation_pipeline.t2i_agent.nodes.generate import (
    Evaluate,
    EvaluationInput,
    GenerationInput,
    GenerationOutput,
)
from content_automation_pipeline.utilities.logger import create_logger

_logger = create_logger(__name__)

T = TypeVar('T')


class GenerationEvaluationState(GenerationState):
    model_config = ConfigDict(extra='forbid', strict=True, validate_assignment=True)

    evaluation_instructions: str
    evaluation: Evaluation | None


class GenerationEvaluation:
    # Default values that can be overridden by the user
    _GENERATE_KIND: Final[Kind] = Kind.TEMPORARY
    _GENERATE_MAX_CALLS: Final[int] = 1

    # Hardcoded values that cannot be overridden by the user
    _GENERATION_AGENT_NODE: Final[str] = 'generation_agent'
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
        message = 'building the t2i generation-evaluation graph'
        _logger.info(message)

        self._generation_agent = Generation(
            generate_artifact_manager,
            generate_category,
            generate_kind,
            generate_max_calls,
        ).get_compiled_state_graph()
        self._evaluate = Evaluate(evaluate_artifact_manager)
        self._decide = Decide(END, self._GENERATION_AGENT_NODE)

        graph = StateGraph(GenerationEvaluationState)
        graph.add_node(self._GENERATION_AGENT_NODE, self._run_generation_agent)  # type: ignore
        graph.add_node(self._EVALUATE_NODE, self._run_evaluate)  # type: ignore

        graph.add_edge(START, self._GENERATION_AGENT_NODE)
        graph.add_edge(self._GENERATION_AGENT_NODE, self._EVALUATE_NODE)
        graph.add_conditional_edges(
            self._EVALUATE_NODE,
            self._run_decide,
            [END, self._GENERATION_AGENT_NODE],
        )

        self._compiled_state_graph: CompiledStateGraph[
            GenerationEvaluationState,
            None,
            GenerationEvaluationState,
            GenerationEvaluationState,
        ] = graph.compile()  # type: ignore

        message = 'finished building the t2i generation-evaluation graph'
        _logger.info(message)

    def get_compiled_state_graph(
        self,
    ) -> CompiledStateGraph[
        GenerationEvaluationState,
        None,
        GenerationEvaluationState,
        GenerationEvaluationState,
    ]:
        return self._compiled_state_graph

    def _run_generation_agent(self, state: GenerationEvaluationState) -> dict[str, Any]:
        output = GenerationState.model_validate(
            self._generation_agent.invoke(  # type: ignore
                GenerationState(
                    generation_instructions=state.generation_instructions,
                    reference_images=state.reference_images,
                    feedback=state.feedback,
                    image=None,
                ),
            ),
        )

        return {'image': self._require(output.image, 'generated image')}

    def _run_evaluate(self, state: GenerationEvaluationState) -> dict[str, Any]:
        output = self._evaluate(
            EvaluationInput(
                generation_input=GenerationInput(
                    instructions=state.generation_instructions,
                    feedback=state.feedback,
                    reference_images=state.reference_images,
                ),
                generation_output=GenerationOutput(image=self._require(state.image, 'image')),
                instructions=state.evaluation_instructions,
            ),
        )

        return {
            'evaluation': output.evaluation,
            'feedback': [*state.feedback, output.evaluation.feedback],
        }

    def _run_decide(self, state: GenerationEvaluationState) -> str:
        output = self._decide(DecisionInput(evaluation=self._require(state.evaluation, 'evaluation')))

        return output.destination

    @staticmethod
    def _require(value: T | None, name: str) -> T:
        if value is None:
            message = f'the state has no {name}'
            _logger.error(message)
            raise RuntimeError(message)

        return value

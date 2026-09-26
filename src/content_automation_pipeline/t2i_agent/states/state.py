from content_automation_pipeline.t2i_agent.models.evaluation import Evaluation
from content_automation_pipeline.t2i_agent.states.generation import GenerationState


class State(GenerationState):
    evaluation_instructions: str
    evaluation: Evaluation | None = None

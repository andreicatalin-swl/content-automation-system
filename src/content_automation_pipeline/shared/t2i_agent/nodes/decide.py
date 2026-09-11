from langgraph.graph import END  # type: ignore

from content_automation_pipeline.shared.t2i_agent.models.grade import Grade
from content_automation_pipeline.shared.t2i_agent.states.state import State
from content_automation_pipeline.shared.utilities.logger import create_logger

_logger = create_logger(__name__)

class Decide:
    def __init__(self, repeat: str) -> None:
        self._repeat = repeat

    def __call__(self, state: State) -> str:
        message = f'deciding whether to repeat the generation for prompt={state.prompt}'
        _logger.info(message)

        # Check if there is an evaluation to decide on
        if state.evaluation is None:
            message = f'there is no evaluation to decide on for prompt={state.prompt}'
            _logger.error(message)
            raise RuntimeError(message)

        # Repeat the generation whenever the image did not pass the evaluation
        destination = END if state.evaluation.grade is Grade.PASS else self._repeat

        message = f'finished deciding to continue to {destination} for prompt={state.prompt}'
        _logger.info(message)

        return destination

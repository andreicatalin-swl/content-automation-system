from typing import Final, Generic, TypeVar

from langchain.agents import create_agent  # type: ignore
from langchain.chat_models import init_chat_model

from content_automation_pipeline.utilities.logger import create_logger
from content_automation_pipeline.video_agent.models.script import Script
from content_automation_pipeline.video_agent.states.state import State

_logger = create_logger(__name__)

T = TypeVar('T', bound=Script)

class ScriptWriter(Generic[T]):
    # Default values that can be overridden by the user
    _DEFATLT_MODEL: Final[str] = 'groq:llama-3.1-8b-instant'

    def __init__(self, model: str = _DEFATLT_MODEL) -> None:
        self._model = model

    def __call__(self, state: State[T]) -> T:
        message = f'generating script with model={self._model}'
        _logger.info(message)

        agent = create_agent(init_chat_model(self._model), tools=state['tools'], response_format=state['response_format'])  # type: ignore
        result = agent.invoke({'messages': [state['prompt']]})  # type: ignore
        script = result['structured_response']

        message = f'finished generating script with model={self._model}'
        _logger.info(message)

        return script

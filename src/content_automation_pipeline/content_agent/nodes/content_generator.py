from typing import Final, Generic, TypeVar

from langchain.agents import create_agent  # type: ignore
from langchain.chat_models import init_chat_model
from pydantic import BaseModel

from content_automation_pipeline.content_agent.states.state import State
from content_automation_pipeline.utilities.logger import create_logger

_logger = create_logger(__name__)

T = TypeVar('T', bound=BaseModel)

class ContentGenerator(Generic[T]):
    # Default values that can be overridden by the user
    _DEFAULT_MODEL: Final[str] = 'groq:llama-3.1-8b-instant'
    _DEFAULT_RECURSION_LIMIT: Final[int] = 25

    def __init__(self, model: str = _DEFAULT_MODEL, recursion_limit: int = _DEFAULT_RECURSION_LIMIT) -> None:
        self._model = model
        self._recursion_limit = recursion_limit

    def __call__(self, state: State[T]) -> State[T]:
        message = f'generating content with model={self._model}'
        _logger.info(message)

        agent = create_agent(init_chat_model(self._model), tools=state['tools'], response_format=state['content_schema'])  # type: ignore
        result = agent.invoke({'messages': [state['prompt']]}, config={'recursion_limit': self._recursion_limit})  # type: ignore
        content = result['structured_response']

        message = f'finished generating content with model={self._model}'
        _logger.info(message)

        return State(
            content_schema=state['content_schema'],
            tools=state['tools'],
            prompt=state['prompt'],
            content=content,
        )

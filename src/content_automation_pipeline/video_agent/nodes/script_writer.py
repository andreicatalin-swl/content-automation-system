from typing import Final

from langchain.chat_models import init_chat_model

from content_automation_pipeline.utilities.logger import create_logger
from content_automation_pipeline.video_agent.models.script import Script
from content_automation_pipeline.video_agent.states.state import State

_logger = create_logger(__name__)

class ScriptWriter:
    # Default values that can be overridden by the user
    _DEFAULT_MODEL: Final[str] = 'groq:llama-3.1-8b-instant'

    def __init__(self, model: str = _DEFAULT_MODEL) -> None:
        self._model = model

    def __call__(self, state: State) -> State:
        message = f'generating script with model={self._model}'
        _logger.info(message)

        chat_model = init_chat_model(self._model)
        structured_model = chat_model.with_structured_output(Script)
        script = structured_model.invoke([state['prompt']])

        if not isinstance(script, Script):
            message = f'expected Script from structured output, got {type(script).__name__}'
            _logger.error(message)
            raise TypeError(message)

        message = f'finished generating script with model={self._model}'
        _logger.info(message)

        return State(script=script, tools=state['tools'], prompt=state['prompt'])

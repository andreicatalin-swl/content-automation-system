from typing import Final

from langchain.agents import create_agent
from langchain.chat_models import init_chat_model
from langchain_core.messages import HumanMessage

from content_automation_pipeline.carousel_agent.models.content import Content
from content_automation_pipeline.carousel_agent.states.state import State
from content_automation_pipeline.shared.tools.codex_image_generator import (
    CodexImageGenerator,
)
from content_automation_pipeline.shared.utilities.logger import create_logger

_logger = create_logger(__name__)

class CarouselGenerator:
    # Default values that can be overridden by the user
    _DEFAULT_MODEL: Final[str] = 'groq:llama-3.1-8b-instant'
    _DEFAULT_RECURSION_LIMIT: Final[int] = 25

    # Hardcoded values that cannot be overridden by the user
    _INSTRUCTION_TEMPLATE: Final[str] = (
        'Design a slideable social media carousel of {number_slides} slides for the following context.\n\n'
        "Context: '{context}'\n\n"
        'For every slide, write an image generation prompt describing the image that belongs on it, '
        'and the caption that goes with that image. Every prompt must describe a different image.'
    )

    def __init__(
        self,
        codex_image_generator: CodexImageGenerator,
        model: str = _DEFAULT_MODEL,
        recursion_limit: int = _DEFAULT_RECURSION_LIMIT,
    ) -> None:
        self._codex_image_generator = codex_image_generator
        self._model = model
        self._recursion_limit = recursion_limit

    def __call__(self, state: State) -> State:
        message = f'generating {state.number_slides} slide(s) with model={self._model}'
        _logger.info(message)

        agent = create_agent(init_chat_model(self._model), tools=[], response_format=Content)
        instruction = HumanMessage(
            self._INSTRUCTION_TEMPLATE.format(number_slides=state.number_slides, context=state.context)
        )
        content: Content = agent.invoke(
            {'messages': [instruction]}, config={'recursion_limit': self._recursion_limit}
        )['structured_response']

        message = f'finished generating {len(content.slides)} slide(s) with model={self._model}'
        _logger.info(message)

        return state.model_copy(update={'slides': content.slides})

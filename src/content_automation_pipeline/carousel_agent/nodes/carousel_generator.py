from typing import Final

from langchain.agents import create_agent  # type: ignore
from langchain.chat_models import init_chat_model
from langchain_core.messages import HumanMessage

from content_automation_pipeline.carousel_agent.models.content import Content
from content_automation_pipeline.carousel_agent.states.state import State
from content_automation_pipeline.tools.codex_image_generator import (
    CodexImageGenerator,
    create_generate_tool,
)
from content_automation_pipeline.utilities.logger import create_logger

_logger = create_logger(__name__)

class CarouselGenerator:
    # Default values that can be overridden by the user
    _DEFAULT_MODEL: Final[str] = 'groq:llama-3.1-8b-instant'
    _DEFAULT_RECURSION_LIMIT: Final[int] = 25

    # Hardcoded values that cannot be overridden by the user
    _INSTRUCTION_TEMPLATE: Final[str] = (
        'Generate a slideable social media carousel for the following context.\n\n'
        "Context: '{context}'\n\n"
        'Generate one image per slide with your image generation tool, and write one caption per image. '
        'Return the images and their captions in slide order, with exactly one caption per image.'
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
        message = f'generating carousel with model={self._model}'
        _logger.info(message)

        tools = [create_generate_tool(self._codex_image_generator)]
        prompt = HumanMessage(self._INSTRUCTION_TEMPLATE.format(context=state.context))

        agent = create_agent(init_chat_model(self._model), tools=tools, response_format=Content)  # type: ignore
        result = agent.invoke({'messages': [prompt]}, config={'recursion_limit': self._recursion_limit})  # type: ignore
        content = result['structured_response']

        message = f'finished generating carousel with model={self._model}'
        _logger.info(message)

        return State(content=content, context=state.context)

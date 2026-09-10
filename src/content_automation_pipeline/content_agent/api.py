from typing import TypeVar

from langchain_core.messages import HumanMessage
from langchain_core.tools import BaseTool
from pydantic import BaseModel

from content_automation_pipeline.content_agent.graphs.content_graph import ContentGraph
from content_automation_pipeline.content_agent.states.state import State
from content_automation_pipeline.utilities.logger import create_logger

_logger = create_logger(__name__)

T = TypeVar('T', bound=BaseModel)

def call(prompt: HumanMessage, tools: list[BaseTool], content_schema: type[T]) -> T:
    message = f'running content agent for content_schema={content_schema.__name__}'
    _logger.info(message)

    state: State[T] = {'prompt': prompt, 'tools': tools, 'content_schema': content_schema}
    final_state = ContentGraph[T]().invoke(state)

    message = f'finished running content agent for content_schema={content_schema.__name__}'
    _logger.info(message)

    return final_state['content']  # type: ignore

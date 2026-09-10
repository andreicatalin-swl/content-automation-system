from typing import Generic, TypedDict, TypeVar

from langchain_core.messages import HumanMessage
from langchain_core.tools import BaseTool

from content_automation_pipeline.content_agent.models.content import Content
from content_automation_pipeline.utilities.logger import create_logger

_logger = create_logger(__name__)

T = TypeVar('T', bound=Content)

class State(TypedDict, Generic[T]):
    response_format: type[T]
    tools: list[BaseTool]
    prompt: HumanMessage

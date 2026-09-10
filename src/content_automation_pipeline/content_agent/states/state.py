from typing import Generic, NotRequired, TypedDict, TypeVar

from langchain_core.messages import HumanMessage
from langchain_core.tools import BaseTool
from pydantic import BaseModel

from content_automation_pipeline.utilities.logger import create_logger

_logger = create_logger(__name__)

T = TypeVar('T', bound=BaseModel)

class State(TypedDict, Generic[T]):
    prompt: HumanMessage
    tools: list[BaseTool]
    content_schema: type[T]
    content: NotRequired[T]

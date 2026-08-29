from langchain_core.messages import HumanMessage

from content_automation_pipeline.tools.tool import Tool
from content_automation_pipeline.utilities.logger import create_logger
from content_automation_pipeline.video_agent.models.script import Script

_logger = create_logger(__name__)

class ScriptWriter:
    def __call__(self, script: Script, tools: list[Tool], prompt: HumanMessage) -> Script:
        raise NotImplementedError

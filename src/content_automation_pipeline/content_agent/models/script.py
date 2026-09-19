from pydantic import BaseModel, ConfigDict

from content_automation_pipeline.utilities.logger import create_logger

_logger = create_logger(__name__)

class ScriptEntry(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)

    line: str

    def __repr__(self) -> str:
        return self.line

class Script(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)

    username: str
    title1: str
    title2: str
    subheading: str
    entries: list[ScriptEntry]

    def __repr__(self) -> str:
        return (
            f'{self.title1} {self.title2} - {self.subheading} '
            f'by {self.username} with {len(self.entries)} entries'
        )

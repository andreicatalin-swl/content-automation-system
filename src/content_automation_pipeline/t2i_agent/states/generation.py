from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from content_automation_pipeline.artifacts.artifact import Artifact


class GenerationState(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True, validate_assignment=True)

    generation_instructions: str
    reference_images: list[Path] = Field(default_factory=list)
    feedback: list[str] = Field(default_factory=list)
    image: Artifact | None = None

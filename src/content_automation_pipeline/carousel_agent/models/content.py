from typing import Self

from pydantic import BaseModel, model_validator

from content_automation_pipeline.artifacts.artifact import Artifact
from content_automation_pipeline.utilities.logger import create_logger

_logger = create_logger(__name__)

class Content(BaseModel):
    images: list[Artifact]
    captions: list[str]

    @model_validator(mode='after')
    def _validate_captions(self) -> Self:
        # The number of captions must match the number of images
        if len(self.images) != len(self.captions):
            message = f'expected one caption per image, got {len(self.images)} image(s) and {len(self.captions)} caption(s)'
            _logger.error(message)
            raise ValueError(message)

        return self

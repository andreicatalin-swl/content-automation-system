from enum import StrEnum
from pathlib import Path
from typing import Final

from pydantic import BaseModel, ConfigDict

from content_automation_system.artifacts.artifact import Artifact
from content_automation_system.artifacts.artifact_manager import ArtifactManager
from content_automation_system.content_agent.models.evaluation import (
    Evaluation,
    Grade,
)
from content_automation_system.content_agent.tools.youtube_uploader import (
    YoutubeUploader,
)
from content_automation_system.shared.abstract_node import AbstractNode
from content_automation_system.utilities.logger import create_logger

_logger = create_logger(__name__)

class YoutubePrivacyStatus(StrEnum):
    PRIVATE = 'private'
    UNLISTED = 'unlisted'
    PUBLIC = 'public'

class YoutubeVideoPostingInput(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)

    video: Artifact
    title: str
    description: str
    tags: list[str]
    category_id: str
    privacy_status: YoutubePrivacyStatus
    made_for_kids: bool
    notify_subscribers: bool
    embeddable: bool
    public_stats_viewable: bool
    contains_synthetic_media: bool
    has_paid_product_placement: bool
    default_language: str | None
    default_audio_language: str | None

    def __repr__(self) -> str:
        return f'{self.video!r} posted as {self.title!r}'

class YoutubeVideoPostingOutput(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)

    video_id: str
    url: str

    def __repr__(self) -> str:
        return self.url

# TODO: Implement proper execute(...) -> ... method
class PostYoutubeVideo(AbstractNode[YoutubeVideoPostingInput, YoutubeVideoPostingOutput]):
    def __init__(
        self,
        artifact_manager: ArtifactManager,
        client_secrets_path: Path,
        token_path: Path,
    ) -> None:
        self._artifact_manager = artifact_manager
        self._uploader = YoutubeUploader(client_secrets_path, token_path)

    def execute(self, input: YoutubeVideoPostingInput) -> YoutubeVideoPostingOutput:
        video_id = self._uploader.upload(
            self._artifact_manager.path(input.video),
            self._body(input),
            input.notify_subscribers,
        )
        return YoutubeVideoPostingOutput(
            video_id=video_id,
            url=f'https://www.youtube.com/watch?v={video_id}',
        )

    @staticmethod
    def _body(input: YoutubeVideoPostingInput) -> dict[str, object]:
        snippet: dict[str, object] = {
            'title': input.title,
            'description': input.description,
            'categoryId': input.category_id,
        }
        if input.tags:
            snippet['tags'] = input.tags
        if input.default_language is not None:
            snippet['defaultLanguage'] = input.default_language
        if input.default_audio_language is not None:
            snippet['defaultAudioLanguage'] = input.default_audio_language

        return {
            'snippet': snippet,
            'status': {
                'privacyStatus': input.privacy_status.value,
                'selfDeclaredMadeForKids': input.made_for_kids,
                'embeddable': input.embeddable,
                'publicStatsViewable': input.public_stats_viewable,
                'containsSyntheticMedia': input.contains_synthetic_media,
            },
            'paidProductPlacementDetails': {
                'hasPaidProductPlacement': input.has_paid_product_placement,
            },
        }

class PostedYoutubeVideoEvaluationInput(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)

    youtube_video_posting_input: YoutubeVideoPostingInput
    youtube_video_posting_output: YoutubeVideoPostingOutput
    instructions: str

    def __repr__(self) -> str:
        return f'{self.youtube_video_posting_output!r} against {self.instructions}'

class PostedYoutubeVideoEvaluationOutput(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)

    evaluation: Evaluation

    def __repr__(self) -> str:
        return repr(self.evaluation)

# TODO: Implement proper execute(...) -> ... method
class EvaluatePostedYoutubeVideo(
    AbstractNode[PostedYoutubeVideoEvaluationInput, PostedYoutubeVideoEvaluationOutput]
):
    _NO_FEEDBACK: Final[str] = 'there is no feedback.'

    def execute(self, input: PostedYoutubeVideoEvaluationInput) -> PostedYoutubeVideoEvaluationOutput:
        return PostedYoutubeVideoEvaluationOutput(
            evaluation=Evaluation(grade=Grade.PASS, feedback=self._NO_FEEDBACK),
        )

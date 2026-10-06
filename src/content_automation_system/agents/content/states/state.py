from pydantic import BaseModel, ConfigDict, Field

from content_automation_system.agents.content.nodes.animate_noise import MaskMode
from content_automation_system.agents.content.nodes.post_youtube_video import (
    YoutubePrivacyStatus,
)
from content_automation_system.agents.i2i.models.evaluation import Evaluation
from content_automation_system.artifacts.artifact import Artifact


class State(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True, validate_assignment=True)

    generation_instructions: list[str]
    evaluation_instructions: list[str]
    reference_images: list[Artifact]
    audio: Artifact
    post_to_youtube: bool
    youtube_title: str
    youtube_description: str
    youtube_tags: list[str]
    youtube_category_id: str
    youtube_privacy_status: YoutubePrivacyStatus
    youtube_made_for_kids: bool
    youtube_notify_subscribers: bool
    youtube_embeddable: bool
    youtube_public_stats_viewable: bool
    youtube_contains_synthetic_media: bool
    youtube_has_paid_product_placement: bool
    youtube_default_language: str | None
    youtube_default_audio_language: str | None
    feedback: list[list[str]] = []
    convert_image_duration: float = Field(default=5.0, gt=0.0, allow_inf_nan=False)
    convert_image_fps: int = Field(default=30, gt=0)

    animate_noise_strength: float = Field(default=0.45, ge=0.0, le=1.0, allow_inf_nan=False)
    animate_noise_speed: float = Field(default=30.0, ge=0.0, allow_inf_nan=False)
    animate_noise_scale: float = Field(default=1.0, gt=0.0, allow_inf_nan=False)
    animate_noise_mask_threshold: float = Field(default=0.2, ge=0.0, le=1.0, allow_inf_nan=False)
    animate_noise_mask_softness: float = Field(default=0.35, ge=0.0, le=1.0, allow_inf_nan=False)
    animate_noise_mask_mode: MaskMode = MaskMode.BRIGHTNESS

    images: list[Artifact] = []
    converted_videos: list[Artifact] = []
    animated_videos: list[Artifact] = []
    joined_video: Artifact | None = None
    video: Artifact | None = None
    youtube_video_id: str | None = None
    youtube_url: str | None = None
    evaluations: list[Evaluation] = []

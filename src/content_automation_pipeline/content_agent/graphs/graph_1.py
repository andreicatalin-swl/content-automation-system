from pathlib import Path
from typing import Any, Final, TypeVar

from langgraph.graph import END, START, StateGraph  # type: ignore
from langgraph.graph.state import CompiledStateGraph  # type: ignore
from pydantic import BaseModel, ConfigDict, Field

from content_automation_pipeline.artifacts.artifact import Artifact, Kind
from content_automation_pipeline.artifacts.artifact_manager import ArtifactManager
from content_automation_pipeline.content_agent.nodes.add_audio import (
    AddAudio,
    AudioAdditionInput,
)
from content_automation_pipeline.content_agent.nodes.animate_noise import (
    AnimateNoise,
    MaskMode,
    NoiseAnimationInput,
)
from content_automation_pipeline.content_agent.nodes.convert_image import (
    ConvertImage,
    ImageConversionInput,
)
from content_automation_pipeline.content_agent.nodes.decide import (
    Decide,
    DecisionInput,
)
from content_automation_pipeline.content_agent.nodes.join_videos import (
    JoinVideos,
    VideoJoiningInput,
)
from content_automation_pipeline.content_agent.nodes.post_youtube_video import (
    PostYoutubeVideo,
    YoutubePrivacyStatus,
    YoutubeVideoPostingInput,
)
from content_automation_pipeline.t2i_agent.graphs.generation_evaluation import (
    GenerationEvaluation,
    GenerationEvaluationState,
)
from content_automation_pipeline.t2i_agent.models.evaluation import Evaluation
from content_automation_pipeline.utilities.logger import create_logger

_logger = create_logger(__name__)

T = TypeVar('T')

class State(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True, validate_assignment=True)

    generation_instructions: list[str]
    evaluation_instructions: list[str]
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

class Graph1:
    # Default values that can be overridden by the user
    _KIND: Final[Kind] = Kind.TEMPORARY
    _T2I_GENERATE_MAX_CALLS: Final[int] = 1

    # Hardcoded values that cannot be overridden by the user
    _T2I_AGENT_NODE: Final[str] = 't2i_agent'
    _CONVERT_IMAGE_NODE: Final[str] = 'convert_image'
    _ANIMATE_NOISE_NODE: Final[str] = 'animate_noise'
    _JOIN_VIDEOS_NODE: Final[str] = 'join_videos'
    _ADD_AUDIO_NODE: Final[str] = 'add_audio'
    _POST_YOUTUBE_VIDEO_NODE: Final[str] = 'post_youtube_video'

    def __init__(
        self,
        generations: int,
        t2i_generate_artifact_manager: ArtifactManager,
        t2i_generate_category: str,
        t2i_evaluate_artifact_manager: ArtifactManager,
        convert_image_artifact_manager: ArtifactManager,
        convert_image_category: str,
        animate_noise_artifact_manager: ArtifactManager,
        animate_noise_category: str,
        join_videos_artifact_manager: ArtifactManager,
        join_videos_category: str,
        add_audio_artifact_manager: ArtifactManager,
        add_audio_category: str,
        post_youtube_video_artifact_manager: ArtifactManager,
        post_youtube_video_client_secrets_path: Path,
        post_youtube_video_token_path: Path,
        t2i_generate_kind: Kind = _KIND,
        convert_image_kind: Kind = _KIND,
        animate_noise_kind: Kind = _KIND,
        join_videos_kind: Kind = _KIND,
        add_audio_kind: Kind = _KIND,
        t2i_generate_max_calls: int = _T2I_GENERATE_MAX_CALLS,
    ) -> None:
        _logger.info('building content graph 1')

        self._generations = generations
        self._t2i_agents = [
            GenerationEvaluation(
                generate_artifact_manager=t2i_generate_artifact_manager,
                generate_category=t2i_generate_category,
                generate_kind=t2i_generate_kind,
                generate_max_calls=t2i_generate_max_calls,
                evaluate_artifact_manager=t2i_evaluate_artifact_manager,
            ).get_compiled_state_graph()
            for _ in range(generations)
        ]
        self._convert_image = ConvertImage(
            convert_image_artifact_manager,
            convert_image_category,
            convert_image_kind,
        )
        self._animate_noise = AnimateNoise(
            animate_noise_artifact_manager,
            animate_noise_category,
            animate_noise_kind,
        )
        self._join_videos = JoinVideos(
            join_videos_artifact_manager,
            join_videos_category,
            join_videos_kind,
        )
        self._add_audio = AddAudio(
            add_audio_artifact_manager,
            add_audio_category,
            add_audio_kind,
        )
        self._post_youtube_video = PostYoutubeVideo(
            post_youtube_video_artifact_manager,
            post_youtube_video_client_secrets_path,
            post_youtube_video_token_path,
        )
        self._decide_on_post_to_youtube = Decide(self._POST_YOUTUBE_VIDEO_NODE, END)

        graph = StateGraph(State)
        graph.add_node(self._T2I_AGENT_NODE, self._run_t2i_agent)  # type: ignore
        graph.add_node(self._CONVERT_IMAGE_NODE, self._run_convert_image)  # type: ignore
        graph.add_node(self._ANIMATE_NOISE_NODE, self._run_animate_noise)  # type: ignore
        graph.add_node(self._JOIN_VIDEOS_NODE, self._run_join_videos)  # type: ignore
        graph.add_node(self._ADD_AUDIO_NODE, self._run_add_audio)  # type: ignore
        graph.add_node(self._POST_YOUTUBE_VIDEO_NODE, self._run_post_youtube_video)  # type: ignore

        graph.add_edge(START, self._T2I_AGENT_NODE)
        graph.add_edge(self._T2I_AGENT_NODE, self._CONVERT_IMAGE_NODE)
        graph.add_edge(self._CONVERT_IMAGE_NODE, self._ANIMATE_NOISE_NODE)
        graph.add_edge(self._ANIMATE_NOISE_NODE, self._JOIN_VIDEOS_NODE)
        graph.add_edge(self._JOIN_VIDEOS_NODE, self._ADD_AUDIO_NODE)
        graph.add_conditional_edges(
            self._ADD_AUDIO_NODE,
            self._decide_post_to_youtube_destination,
            [self._POST_YOUTUBE_VIDEO_NODE, END],
        )
        graph.add_edge(self._POST_YOUTUBE_VIDEO_NODE, END)

        self._compiled_state_graph: CompiledStateGraph[State, None, State, State] = graph.compile()  # type: ignore

        _logger.info('finished building content graph 1')

    def get_compiled_state_graph(self) -> CompiledStateGraph[State, None, State, State]:
        return self._compiled_state_graph

    def _run_t2i_agent(self, state: State) -> dict[str, Any]:
        images: list[Artifact] = []
        evaluations: list[Evaluation] = []
        feedback: list[list[str]] = []

        for index in range(self._generations):
            output = GenerationEvaluationState.model_validate(
                self._t2i_agents[index].invoke(  # type: ignore
                    GenerationEvaluationState(
                        generation_instructions=state.generation_instructions[index],
                        evaluation_instructions=state.evaluation_instructions[index],
                        reference_images=[],
                        feedback=state.feedback[index] if index < len(state.feedback) else [],
                        image=None,
                        evaluation=None,
                    ),
                ),
            )
            images.append(self._require(output.image, 'generated image'))
            evaluations.append(self._require(output.evaluation, 'image evaluation'))
            feedback.append(output.feedback)

        return {
            'images': images,
            'evaluations': evaluations,
            'feedback': feedback,
        }

    def _run_convert_image(self, state: State) -> dict[str, Any]:
        videos = [
            self._convert_image(
                ImageConversionInput(
                    image=image,
                    duration=state.convert_image_duration,
                    fps=state.convert_image_fps,
                ),
            ).video
            for image in state.images
        ]

        return {'converted_videos': videos}

    def _run_animate_noise(self, state: State) -> dict[str, Any]:
        videos = [
            self._animate_noise(
                NoiseAnimationInput(
                    video=video,
                    strength=state.animate_noise_strength,
                    speed=state.animate_noise_speed,
                    scale=state.animate_noise_scale,
                    mask_threshold=state.animate_noise_mask_threshold,
                    mask_softness=state.animate_noise_mask_softness,
                    mask_mode=state.animate_noise_mask_mode,
                ),
            ).video
            for video in state.converted_videos
        ]

        return {'animated_videos': videos}

    def _run_join_videos(self, state: State) -> dict[str, Any]:
        output = self._join_videos(VideoJoiningInput(videos=state.animated_videos))

        return {'joined_video': output.video}

    def _run_add_audio(self, state: State) -> dict[str, Any]:
        output = self._add_audio(
            AudioAdditionInput(
                video=self._require(state.joined_video, 'joined video'),
                audio=state.audio,
            ),
        )

        return {'video': output.video}

    def _run_post_youtube_video(self, state: State) -> dict[str, Any]:
        output = self._post_youtube_video(
            YoutubeVideoPostingInput(
                video=self._require(state.video, 'final video'),
                title=state.youtube_title,
                description=state.youtube_description,
                tags=state.youtube_tags,
                category_id=state.youtube_category_id,
                privacy_status=state.youtube_privacy_status,
                made_for_kids=state.youtube_made_for_kids,
                notify_subscribers=state.youtube_notify_subscribers,
                embeddable=state.youtube_embeddable,
                public_stats_viewable=state.youtube_public_stats_viewable,
                contains_synthetic_media=state.youtube_contains_synthetic_media,
                has_paid_product_placement=state.youtube_has_paid_product_placement,
                default_language=state.youtube_default_language,
                default_audio_language=state.youtube_default_audio_language,
            ),
        )

        return {
            'youtube_video_id': output.video_id,
            'youtube_url': output.url,
        }

    def _decide_post_to_youtube_destination(self, state: State) -> str:
        return self._decide_on_post_to_youtube(
            DecisionInput(post_to_youtube=state.post_to_youtube),
        ).destination

    @staticmethod
    def _require(value: T | None, name: str) -> T:
        if value is None:
            message = f'the state has no {name}'
            _logger.error(message)
            raise RuntimeError(message)

        return value

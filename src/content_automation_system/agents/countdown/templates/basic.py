from typing import Final

from content_automation_system.agents.countdown.graphs.graph import Graph
from content_automation_system.agents.countdown.states.state import State
from content_automation_system.artifacts.artifact import Artifact, Kind
from content_automation_system.artifacts.artifact_manager import ArtifactManager
from content_automation_system.utilities.logger import create_logger

_logger = create_logger(__name__)

# Default values that can be overridden by the user
_KIND: Final[Kind] = Kind.TEMPORARY
_MAX_CALLS: Final[int] = 1

# Hardcoded values that cannot be overridden by the user
_SCRIPT_GENERATION_INSTRUCTION_TEMPLATE: Final[str] = (
    'Preserve the supplied values and fill in missing values.\n\n'
    'username: {username}\n'
    'title1: {title1}\n'
    'title2: {title2}\n'
    'subheading: {subheading}\n'
    'top1: {top1}\n'
    'top2: {top2}\n'
    'top3: {top3}\n'
    'top4: {top4}\n'
    'top5: {top5}\n'
    'top6: {top6}\n'
    'top7: {top7}\n'
    'top8: {top8}\n'
    'top9: {top9}\n'
    'top10: {top10}'
)
_SCRIPT_EVALUATION_INSTRUCTION_TEMPLATE: Final[str] = (
    'Verify that the output follows the provided instructions.'
)
_MEDIA_FINDING_INSTRUCTION_TEMPLATE: Final[str] = (
    'Preserve the supplied values and fill in missing values.\n\n'
    'top1_video_link: {top1_video_link}\n'
    'top1_video_start_timestamp: {top1_video_start_timestamp}\n'
    'top1_video_duration: {top1_video_duration}\n'
    'top1_audio_link: {top1_audio_link}\n'
    'top1_audio_start_timestamp: {top1_audio_start_timestamp}\n'
    'top1_audio_duration: {top1_audio_duration}\n'
    'top2_video_link: {top2_video_link}\n'
    'top2_video_start_timestamp: {top2_video_start_timestamp}\n'
    'top2_video_duration: {top2_video_duration}\n'
    'top2_audio_link: {top2_audio_link}\n'
    'top2_audio_start_timestamp: {top2_audio_start_timestamp}\n'
    'top2_audio_duration: {top2_audio_duration}\n'
    'top3_video_link: {top3_video_link}\n'
    'top3_video_start_timestamp: {top3_video_start_timestamp}\n'
    'top3_video_duration: {top3_video_duration}\n'
    'top3_audio_link: {top3_audio_link}\n'
    'top3_audio_start_timestamp: {top3_audio_start_timestamp}\n'
    'top3_audio_duration: {top3_audio_duration}\n'
    'top4_video_link: {top4_video_link}\n'
    'top4_video_start_timestamp: {top4_video_start_timestamp}\n'
    'top4_video_duration: {top4_video_duration}\n'
    'top4_audio_link: {top4_audio_link}\n'
    'top4_audio_start_timestamp: {top4_audio_start_timestamp}\n'
    'top4_audio_duration: {top4_audio_duration}\n'
    'top5_video_link: {top5_video_link}\n'
    'top5_video_start_timestamp: {top5_video_start_timestamp}\n'
    'top5_video_duration: {top5_video_duration}\n'
    'top5_audio_link: {top5_audio_link}\n'
    'top5_audio_start_timestamp: {top5_audio_start_timestamp}\n'
    'top5_audio_duration: {top5_audio_duration}\n'
    'top6_video_link: {top6_video_link}\n'
    'top6_video_start_timestamp: {top6_video_start_timestamp}\n'
    'top6_video_duration: {top6_video_duration}\n'
    'top6_audio_link: {top6_audio_link}\n'
    'top6_audio_start_timestamp: {top6_audio_start_timestamp}\n'
    'top6_audio_duration: {top6_audio_duration}\n'
    'top7_video_link: {top7_video_link}\n'
    'top7_video_start_timestamp: {top7_video_start_timestamp}\n'
    'top7_video_duration: {top7_video_duration}\n'
    'top7_audio_link: {top7_audio_link}\n'
    'top7_audio_start_timestamp: {top7_audio_start_timestamp}\n'
    'top7_audio_duration: {top7_audio_duration}\n'
    'top8_video_link: {top8_video_link}\n'
    'top8_video_start_timestamp: {top8_video_start_timestamp}\n'
    'top8_video_duration: {top8_video_duration}\n'
    'top8_audio_link: {top8_audio_link}\n'
    'top8_audio_start_timestamp: {top8_audio_start_timestamp}\n'
    'top8_audio_duration: {top8_audio_duration}\n'
    'top9_video_link: {top9_video_link}\n'
    'top9_video_start_timestamp: {top9_video_start_timestamp}\n'
    'top9_video_duration: {top9_video_duration}\n'
    'top9_audio_link: {top9_audio_link}\n'
    'top9_audio_start_timestamp: {top9_audio_start_timestamp}\n'
    'top9_audio_duration: {top9_audio_duration}\n'
    'top10_video_link: {top10_video_link}\n'
    'top10_video_start_timestamp: {top10_video_start_timestamp}\n'
    'top10_video_duration: {top10_video_duration}\n'
    'top10_audio_link: {top10_audio_link}\n'
    'top10_audio_start_timestamp: {top10_audio_start_timestamp}\n'
    'top10_audio_duration: {top10_audio_duration}'
)
_FOUND_MEDIA_EVALUATION_INSTRUCTION_TEMPLATE: Final[str] = (
    'Verify that the output follows the provided instructions.'
)
_DOWNLOADED_MEDIA_EVALUATION_INSTRUCTION_TEMPLATE: Final[str] = (
    'Verify that the output follows the provided instructions.'
)
_EDITED_VIDEO_EVALUATION_INSTRUCTION_TEMPLATE: Final[str] = (
    'Verify that the output follows the provided instructions.'
)

def run(
    download_media_artifact_manager: ArtifactManager,
    download_media_category: str,
    edit_video_artifact_manager: ArtifactManager,
    edit_video_category: str,
    edit_video_script: Artifact,
    download_media_kind: Kind = _KIND,
    edit_video_kind: Kind = _KIND,
    generate_script_max_calls: int = _MAX_CALLS,
    find_media_max_calls: int = _MAX_CALLS,
    download_media_max_calls: int = _MAX_CALLS,
    edit_video_max_calls: int = _MAX_CALLS,
    username: str | None = None,
    title1: str | None = None,
    title2: str | None = None,
    subheading: str | None = None,
    top1: str | None = None,
    top2: str | None = None,
    top3: str | None = None,
    top4: str | None = None,
    top5: str | None = None,
    top6: str | None = None,
    top7: str | None = None,
    top8: str | None = None,
    top9: str | None = None,
    top10: str | None = None,
    top1_video_link: str | None = None,
    top1_video_start_timestamp: float | None = None,
    top1_video_duration: float | None = None,
    top1_audio_link: str | None = None,
    top1_audio_start_timestamp: float | None = None,
    top1_audio_duration: float | None = None,
    top2_video_link: str | None = None,
    top2_video_start_timestamp: float | None = None,
    top2_video_duration: float | None = None,
    top2_audio_link: str | None = None,
    top2_audio_start_timestamp: float | None = None,
    top2_audio_duration: float | None = None,
    top3_video_link: str | None = None,
    top3_video_start_timestamp: float | None = None,
    top3_video_duration: float | None = None,
    top3_audio_link: str | None = None,
    top3_audio_start_timestamp: float | None = None,
    top3_audio_duration: float | None = None,
    top4_video_link: str | None = None,
    top4_video_start_timestamp: float | None = None,
    top4_video_duration: float | None = None,
    top4_audio_link: str | None = None,
    top4_audio_start_timestamp: float | None = None,
    top4_audio_duration: float | None = None,
    top5_video_link: str | None = None,
    top5_video_start_timestamp: float | None = None,
    top5_video_duration: float | None = None,
    top5_audio_link: str | None = None,
    top5_audio_start_timestamp: float | None = None,
    top5_audio_duration: float | None = None,
    top6_video_link: str | None = None,
    top6_video_start_timestamp: float | None = None,
    top6_video_duration: float | None = None,
    top6_audio_link: str | None = None,
    top6_audio_start_timestamp: float | None = None,
    top6_audio_duration: float | None = None,
    top7_video_link: str | None = None,
    top7_video_start_timestamp: float | None = None,
    top7_video_duration: float | None = None,
    top7_audio_link: str | None = None,
    top7_audio_start_timestamp: float | None = None,
    top7_audio_duration: float | None = None,
    top8_video_link: str | None = None,
    top8_video_start_timestamp: float | None = None,
    top8_video_duration: float | None = None,
    top8_audio_link: str | None = None,
    top8_audio_start_timestamp: float | None = None,
    top8_audio_duration: float | None = None,
    top9_video_link: str | None = None,
    top9_video_start_timestamp: float | None = None,
    top9_video_duration: float | None = None,
    top9_audio_link: str | None = None,
    top9_audio_start_timestamp: float | None = None,
    top9_audio_duration: float | None = None,
    top10_video_link: str | None = None,
    top10_video_start_timestamp: float | None = None,
    top10_video_duration: float | None = None,
    top10_audio_link: str | None = None,
    top10_audio_start_timestamp: float | None = None,
    top10_audio_duration: float | None = None,
) -> None:
    message = 'running the basic countdown template'
    _logger.info(message)

    state = State(
        generation_instructions=_SCRIPT_GENERATION_INSTRUCTION_TEMPLATE.format(
            username=username,
            title1=title1,
            title2=title2,
            subheading=subheading,
            top1=top1,
            top2=top2,
            top3=top3,
            top4=top4,
            top5=top5,
            top6=top6,
            top7=top7,
            top8=top8,
            top9=top9,
            top10=top10,
        ),
        script_evaluation_instructions=_SCRIPT_EVALUATION_INSTRUCTION_TEMPLATE,
        media_finding_instructions=_MEDIA_FINDING_INSTRUCTION_TEMPLATE.format(
            top1_video_link=top1_video_link,
            top1_video_start_timestamp=top1_video_start_timestamp,
            top1_video_duration=top1_video_duration,
            top1_audio_link=top1_audio_link,
            top1_audio_start_timestamp=top1_audio_start_timestamp,
            top1_audio_duration=top1_audio_duration,
            top2_video_link=top2_video_link,
            top2_video_start_timestamp=top2_video_start_timestamp,
            top2_video_duration=top2_video_duration,
            top2_audio_link=top2_audio_link,
            top2_audio_start_timestamp=top2_audio_start_timestamp,
            top2_audio_duration=top2_audio_duration,
            top3_video_link=top3_video_link,
            top3_video_start_timestamp=top3_video_start_timestamp,
            top3_video_duration=top3_video_duration,
            top3_audio_link=top3_audio_link,
            top3_audio_start_timestamp=top3_audio_start_timestamp,
            top3_audio_duration=top3_audio_duration,
            top4_video_link=top4_video_link,
            top4_video_start_timestamp=top4_video_start_timestamp,
            top4_video_duration=top4_video_duration,
            top4_audio_link=top4_audio_link,
            top4_audio_start_timestamp=top4_audio_start_timestamp,
            top4_audio_duration=top4_audio_duration,
            top5_video_link=top5_video_link,
            top5_video_start_timestamp=top5_video_start_timestamp,
            top5_video_duration=top5_video_duration,
            top5_audio_link=top5_audio_link,
            top5_audio_start_timestamp=top5_audio_start_timestamp,
            top5_audio_duration=top5_audio_duration,
            top6_video_link=top6_video_link,
            top6_video_start_timestamp=top6_video_start_timestamp,
            top6_video_duration=top6_video_duration,
            top6_audio_link=top6_audio_link,
            top6_audio_start_timestamp=top6_audio_start_timestamp,
            top6_audio_duration=top6_audio_duration,
            top7_video_link=top7_video_link,
            top7_video_start_timestamp=top7_video_start_timestamp,
            top7_video_duration=top7_video_duration,
            top7_audio_link=top7_audio_link,
            top7_audio_start_timestamp=top7_audio_start_timestamp,
            top7_audio_duration=top7_audio_duration,
            top8_video_link=top8_video_link,
            top8_video_start_timestamp=top8_video_start_timestamp,
            top8_video_duration=top8_video_duration,
            top8_audio_link=top8_audio_link,
            top8_audio_start_timestamp=top8_audio_start_timestamp,
            top8_audio_duration=top8_audio_duration,
            top9_video_link=top9_video_link,
            top9_video_start_timestamp=top9_video_start_timestamp,
            top9_video_duration=top9_video_duration,
            top9_audio_link=top9_audio_link,
            top9_audio_start_timestamp=top9_audio_start_timestamp,
            top9_audio_duration=top9_audio_duration,
            top10_video_link=top10_video_link,
            top10_video_start_timestamp=top10_video_start_timestamp,
            top10_video_duration=top10_video_duration,
            top10_audio_link=top10_audio_link,
            top10_audio_start_timestamp=top10_audio_start_timestamp,
            top10_audio_duration=top10_audio_duration,
        ),
        found_media_evaluation_instructions=_FOUND_MEDIA_EVALUATION_INSTRUCTION_TEMPLATE,
        downloaded_media_evaluation_instructions=_DOWNLOADED_MEDIA_EVALUATION_INSTRUCTION_TEMPLATE,
        edited_video_evaluation_instructions=_EDITED_VIDEO_EVALUATION_INSTRUCTION_TEMPLATE,
    )

    graph = Graph(
        download_media_artifact_manager=download_media_artifact_manager,
        download_media_category=download_media_category,
        edit_video_artifact_manager=edit_video_artifact_manager,
        edit_video_category=edit_video_category,
        edit_video_script=edit_video_script,
        download_media_kind=download_media_kind,
        edit_video_kind=edit_video_kind,
        generate_script_max_calls=generate_script_max_calls,
        find_media_max_calls=find_media_max_calls,
        download_media_max_calls=download_media_max_calls,
        edit_video_max_calls=edit_video_max_calls,
    )
    graph.get_compiled_state_graph().invoke(state)  # type: ignore

    message = 'finished running the basic countdown template'
    _logger.info(message)

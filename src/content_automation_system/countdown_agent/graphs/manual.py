from typing import Any, Final, TypeVar

from langgraph.graph import END, START, StateGraph  # type: ignore
from langgraph.graph.state import CompiledStateGraph  # type: ignore

from content_automation_system.artifacts.artifact import Kind
from content_automation_system.artifacts.artifact_manager import ArtifactManager
from content_automation_system.countdown_agent.nodes.abstract_evaluate import EvaluationInput
from content_automation_system.countdown_agent.nodes.decide import (
    Decide,
    DecisionInput,
)
from content_automation_system.countdown_agent.nodes.download_media import (
    DownloadMedia,
    EvaluateDownloadedMedia,
    MediaDownloadInput,
    MediaDownloadOutput,
)
from content_automation_system.countdown_agent.nodes.edit_video import (
    EditVideo,
    EvaluateEditedVideo,
    VideoEditingInput,
    VideoEditingOutput,
)
from content_automation_system.countdown_agent.nodes.find_media import (
    EvaluateFoundMedia,
    FindMedia,
    MediaFindingInput,
    MediaFindingOutput,
)
from content_automation_system.countdown_agent.nodes.generate_script import (
    EvaluateGeneratedScript,
    GenerateScript,
    ScriptGenerationInput,
    ScriptGenerationOutput,
)
from content_automation_system.countdown_agent.states.state import State
from content_automation_system.shared.rate_limiting_node_decorator import (
    RateLimitingNodeDecorator,
)
from content_automation_system.utilities.logger import create_logger

_logger = create_logger(__name__)

T = TypeVar('T')

# TODO: Implement proper manual graph
class Manual:
    # Default values that can be overridden by the user
    _KIND: Final[Kind] = Kind.TEMPORARY
    _MAX_CALLS: Final[int] = 1

    # Hardcoded values that cannot be overridden by the user
    _GENERATE_SCRIPT_NODE: Final[str] = 'generate_script'
    _EVALUATE_GENERATED_SCRIPT_NODE: Final[str] = 'evaluate_generated_script'
    _FIND_MEDIA_NODE: Final[str] = 'find_media'
    _EVALUATE_FOUND_MEDIA_NODE: Final[str] = 'evaluate_found_media'
    _DOWNLOAD_MEDIA_NODE: Final[str] = 'download_media'
    _EVALUATE_DOWNLOADED_MEDIA_NODE: Final[str] = 'evaluate_downloaded_media'
    _EDIT_VIDEO_NODE: Final[str] = 'edit_video'
    _EVALUATE_EDITED_VIDEO_NODE: Final[str] = 'evaluate_edited_video'
    _SCRIPT_TEMPLATE: Final[str] = (
        'Every field of the script has already been decided. Answer with these values, keeping the wording, '
        'the order and the meaning exactly as they are given.\n\n'
        'You may fix an obvious mistake, and only an obvious one: a misspelled song, artist or album name, '
        'a stray character, a missing apostrophe or accent, or capitalisation that is plainly wrong for a '
        'name people know. Correct it to what the name really is and change nothing else about the line.\n\n'
        'You may not reword a line, shorten it, lengthen it, reorder the entries, swap one thing for '
        'another, change a number, or add anything of your own. When you are not sure whether something is '
        'a mistake, leave it exactly as it is.\n\n'
        'username: {username}\n'
        'title1: {title1}\n'
        'title2: {title2}\n'
        'subheading: {subheading}\n\n'
        'The entries, in this exact order, one per line:\n\n{entries}'
    )
    _MEDIA_TEMPLATE: Final[str] = (
        'Every link, start timestamp and duration has already been decided. Answer with exactly these '
        'values and change nothing about them. Do not search for anything, do not look for a better '
        'video, and do not adjust a timestamp or a duration.\n\n'
        'One entry for every entry of the script, in this exact order:\n\n{entries}'
    )

    def __init__(
        self,
        download_media_artifact_manager: ArtifactManager,
        download_media_category: str,
        edit_video_artifact_manager: ArtifactManager,
        edit_video_category: str,
        username: str,
        title1: str,
        title2: str,
        subheading: str,
        entries: list[str],
        video_links: list[str],
        video_start_timestamps: list[float],
        video_durations: list[float],
        audio_links: list[str],
        audio_start_timestamps: list[float],
        audio_durations: list[float],
        script_evaluation_instructions: str,
        found_media_evaluation_instructions: str,
        downloaded_media_evaluation_instructions: str,
        edited_video_evaluation_instructions: str,
        download_media_kind: Kind = _KIND,
        edit_video_kind: Kind = _KIND,
        generate_script_max_calls: int = _MAX_CALLS,
        find_media_max_calls: int = _MAX_CALLS,
        download_media_max_calls: int = _MAX_CALLS,
        edit_video_max_calls: int = _MAX_CALLS,
    ) -> None:
        message = 'building the manual countdown graph'
        _logger.info(message)

        self._generation_instructions = self._script_instructions(
            username,
            title1,
            title2,
            subheading,
            entries,
        )
        self._media_finding_instructions = self._media_instructions(
            len(entries),
            video_links,
            video_start_timestamps,
            video_durations,
            audio_links,
            audio_start_timestamps,
            audio_durations,
        )
        self._script_evaluation_instructions = script_evaluation_instructions
        self._found_media_evaluation_instructions = found_media_evaluation_instructions
        self._downloaded_media_evaluation_instructions = downloaded_media_evaluation_instructions
        self._edited_video_evaluation_instructions = edited_video_evaluation_instructions

        self._generate_script = RateLimitingNodeDecorator(GenerateScript(), generate_script_max_calls)
        self._evaluate_generated_script = EvaluateGeneratedScript()
        self._find_media = RateLimitingNodeDecorator(FindMedia(), find_media_max_calls)
        self._evaluate_found_media = EvaluateFoundMedia()
        self._download_media = RateLimitingNodeDecorator(
            DownloadMedia(download_media_artifact_manager, download_media_category, download_media_kind),
            download_media_max_calls,
        )
        self._evaluate_downloaded_media = EvaluateDownloadedMedia()
        self._edit_video = RateLimitingNodeDecorator(
            EditVideo(edit_video_artifact_manager, edit_video_category, edit_video_kind),
            edit_video_max_calls,
        )
        self._evaluate_edited_video = EvaluateEditedVideo()

        self._decide_on_script = Decide(self._FIND_MEDIA_NODE, self._GENERATE_SCRIPT_NODE)
        self._decide_on_found_media = Decide(self._DOWNLOAD_MEDIA_NODE, self._FIND_MEDIA_NODE)
        self._decide_on_downloaded_media = Decide(self._EDIT_VIDEO_NODE, self._DOWNLOAD_MEDIA_NODE)
        self._decide_on_edited_video = Decide(END, self._EDIT_VIDEO_NODE)

        graph = StateGraph(State)
        graph.add_node(self._GENERATE_SCRIPT_NODE, self._run_generate_script)  # type: ignore
        graph.add_node(self._EVALUATE_GENERATED_SCRIPT_NODE, self._run_evaluate_generated_script)  # type: ignore
        graph.add_node(self._FIND_MEDIA_NODE, self._run_find_media)  # type: ignore
        graph.add_node(self._EVALUATE_FOUND_MEDIA_NODE, self._run_evaluate_found_media)  # type: ignore
        graph.add_node(self._DOWNLOAD_MEDIA_NODE, self._run_download_media)  # type: ignore
        graph.add_node(self._EVALUATE_DOWNLOADED_MEDIA_NODE, self._run_evaluate_downloaded_media)  # type: ignore
        graph.add_node(self._EDIT_VIDEO_NODE, self._run_edit_video)  # type: ignore
        graph.add_node(self._EVALUATE_EDITED_VIDEO_NODE, self._run_evaluate_edited_video)  # type: ignore

        graph.add_edge(START, self._GENERATE_SCRIPT_NODE)
        graph.add_edge(self._GENERATE_SCRIPT_NODE, self._EVALUATE_GENERATED_SCRIPT_NODE)
        graph.add_conditional_edges(
            self._EVALUATE_GENERATED_SCRIPT_NODE,
            self._decide_script_destination,
            [self._FIND_MEDIA_NODE, self._GENERATE_SCRIPT_NODE],
        )

        graph.add_edge(self._FIND_MEDIA_NODE, self._EVALUATE_FOUND_MEDIA_NODE)
        graph.add_conditional_edges(
            self._EVALUATE_FOUND_MEDIA_NODE,
            self._decide_found_media_destination,
            [self._DOWNLOAD_MEDIA_NODE, self._FIND_MEDIA_NODE],
        )

        graph.add_edge(self._DOWNLOAD_MEDIA_NODE, self._EVALUATE_DOWNLOADED_MEDIA_NODE)
        graph.add_conditional_edges(
            self._EVALUATE_DOWNLOADED_MEDIA_NODE,
            self._decide_downloaded_media_destination,
            [self._EDIT_VIDEO_NODE, self._DOWNLOAD_MEDIA_NODE],
        )

        graph.add_edge(self._EDIT_VIDEO_NODE, self._EVALUATE_EDITED_VIDEO_NODE)
        graph.add_conditional_edges(
            self._EVALUATE_EDITED_VIDEO_NODE,
            self._decide_edited_video_destination,
            [END, self._EDIT_VIDEO_NODE],
        )

        self._compiled_state_graph: CompiledStateGraph[State, None, State, State] = graph.compile()  # type: ignore

        message = 'finished building the manual countdown graph'
        _logger.info(message)

    def get_compiled_state_graph(self) -> CompiledStateGraph[State, None, State, State]:
        return self._compiled_state_graph

    def _run_generate_script(self, state: State) -> dict[str, Any]:
        output = self._generate_script(self._script_generation_input())

        return {'script': output.script}

    def _run_evaluate_generated_script(self, state: State) -> dict[str, Any]:
        output = self._evaluate_generated_script(
            EvaluationInput[ScriptGenerationInput, ScriptGenerationOutput](
                node_input=self._script_generation_input(),
                node_output=ScriptGenerationOutput(script=self._require(state.script, 'script')),
                evaluation_instructions=self._script_evaluation_instructions,
            ),
        )

        return {'evaluation': output.evaluation}

    def _run_find_media(self, state: State) -> dict[str, Any]:
        output = self._find_media(self._media_finding_input(state))

        return {'media_links': output.media_links}

    def _run_evaluate_found_media(self, state: State) -> dict[str, Any]:
        output = self._evaluate_found_media(
            EvaluationInput[MediaFindingInput, MediaFindingOutput](
                node_input=self._media_finding_input(state),
                node_output=MediaFindingOutput(
                    media_links=self._require(state.media_links, 'media links'),
                ),
                evaluation_instructions=self._found_media_evaluation_instructions,
            ),
        )

        return {'evaluation': output.evaluation}

    def _run_download_media(self, state: State) -> dict[str, Any]:
        output = self._download_media(self._media_download_input(state))

        return {'media_files': output.media_files}

    def _run_evaluate_downloaded_media(self, state: State) -> dict[str, Any]:
        output = self._evaluate_downloaded_media(
            EvaluationInput[MediaDownloadInput, MediaDownloadOutput](
                node_input=self._media_download_input(state),
                node_output=MediaDownloadOutput(
                    media_files=self._require(state.media_files, 'media files'),
                ),
                evaluation_instructions=self._downloaded_media_evaluation_instructions,
            ),
        )

        return {'evaluation': output.evaluation}

    def _run_edit_video(self, state: State) -> dict[str, Any]:
        output = self._edit_video(self._video_editing_input(state))

        return {'video': output.video}

    def _run_evaluate_edited_video(self, state: State) -> dict[str, Any]:
        output = self._evaluate_edited_video(
            EvaluationInput[VideoEditingInput, VideoEditingOutput](
                node_input=self._video_editing_input(state),
                node_output=VideoEditingOutput(video=self._require(state.video, 'video')),
                evaluation_instructions=self._edited_video_evaluation_instructions,
            ),
        )

        return {'evaluation': output.evaluation}

    def _decide_script_destination(self, state: State) -> str:
        return self._decide_on_script(self._decision_input(state)).destination

    def _decide_found_media_destination(self, state: State) -> str:
        return self._decide_on_found_media(self._decision_input(state)).destination

    def _decide_downloaded_media_destination(self, state: State) -> str:
        return self._decide_on_downloaded_media(self._decision_input(state)).destination

    def _decide_edited_video_destination(self, state: State) -> str:
        return self._decide_on_edited_video(self._decision_input(state)).destination

    def _script_generation_input(self) -> ScriptGenerationInput:
        return ScriptGenerationInput(instructions=self._generation_instructions)

    def _media_finding_input(self, state: State) -> MediaFindingInput:
        return MediaFindingInput(
            script=self._require(state.script, 'script'),
            instructions=self._media_finding_instructions,
        )

    @classmethod
    def _script_instructions(
        cls,
        username: str,
        title1: str,
        title2: str,
        subheading: str,
        entries: list[str],
    ) -> str:
        return cls._SCRIPT_TEMPLATE.format(
            username=username,
            title1=title1,
            title2=title2,
            subheading=subheading,
            entries='\n'.join(entries),
        )

    @classmethod
    def _media_instructions(
        cls,
        entries: int,
        video_links: list[str],
        video_start_timestamps: list[float],
        video_durations: list[float],
        audio_links: list[str],
        audio_start_timestamps: list[float],
        audio_durations: list[float],
    ) -> str:
        columns: dict[str, list[str] | list[float]] = {
            'video_link': video_links,
            'video_start_timestamp': video_start_timestamps,
            'video_duration': video_durations,
            'audio_link': audio_links,
            'audio_start_timestamp': audio_start_timestamps,
            'audio_duration': audio_durations,
        }

        # Every column has to line up with the entries, or the answer would be built from ragged rows
        for name, column in columns.items():
            if len(column) != entries:
                message = f'there are {len(column)} values for {name} and {entries} entries'
                _logger.error(message)
                raise ValueError(message)

        blocks: list[str] = []

        for index in range(entries):
            values = '\n'.join(f'    {name}: {column[index]}' for name, column in columns.items())
            blocks.append(f'  Entry {index + 1}\n{values}')

        return cls._MEDIA_TEMPLATE.format(entries='\n\n'.join(blocks))

    @staticmethod
    def _media_download_input(state: State) -> MediaDownloadInput:
        return MediaDownloadInput(media_links=Manual._require(state.media_links, 'media links'))

    @staticmethod
    def _video_editing_input(state: State) -> VideoEditingInput:
        return VideoEditingInput(
            script=Manual._require(state.script, 'script'),
            media_files=Manual._require(state.media_files, 'media files'),
        )

    @staticmethod
    def _decision_input(state: State) -> DecisionInput:
        return DecisionInput(evaluation=Manual._require(state.evaluation, 'evaluation'))

    @staticmethod
    def _require(value: T | None, name: str) -> T:
        if value is None:
            message = f'the state has no {name}'
            _logger.error(message)
            raise RuntimeError(message)

        return value

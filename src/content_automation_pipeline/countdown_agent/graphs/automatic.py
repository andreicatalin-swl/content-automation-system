from typing import Any, Final, TypeVar

from langgraph.graph import END, START, StateGraph  # type: ignore
from langgraph.graph.state import CompiledStateGraph  # type: ignore

from content_automation_pipeline.artifacts.artifact import Kind
from content_automation_pipeline.artifacts.artifact_manager import ArtifactManager
from content_automation_pipeline.countdown_agent.models.evaluation import (
    Evaluation,
    Grade,
)
from content_automation_pipeline.countdown_agent.nodes.decide import (
    Decide,
    DecisionInput,
)
from content_automation_pipeline.countdown_agent.nodes.download_media import (
    DownloadedMediaEvaluationInput,
    DownloadMedia,
    EvaluateDownloadedMedia,
    MediaDownloadInput,
    MediaDownloadOutput,
)
from content_automation_pipeline.countdown_agent.nodes.edit_video import (
    EditedVideoEvaluationInput,
    EditVideo,
    EvaluateEditedVideo,
    VideoEditingInput,
    VideoEditingOutput,
)
from content_automation_pipeline.countdown_agent.nodes.find_media import (
    EvaluateFoundMedia,
    FindMedia,
    FoundMediaEvaluationInput,
    MediaFindingInput,
    MediaFindingOutput,
)
from content_automation_pipeline.countdown_agent.nodes.generate_script import (
    EvaluateGeneratedScript,
    GeneratedScriptEvaluationInput,
    GenerateScript,
    ScriptGenerationInput,
    ScriptGenerationOutput,
)
from content_automation_pipeline.countdown_agent.nodes.rate_limiting_node_decorator import (
    RateLimitingNodeDecorator,
)
from content_automation_pipeline.countdown_agent.states.state import State
from content_automation_pipeline.utilities.logger import create_logger

_logger = create_logger(__name__)

T = TypeVar('T')

class Automatic:
    # Default values that can be overridden by the user
    _KIND: Final[Kind] = Kind.TEMPORARY
    _MAX_CALLS: Final[int] = 1

    # Hardcoded values that cannot be overridden by the user
    _FEEDBACK_MARKER: Final[str] = 'Feedback from attempt'
    _GENERATE_SCRIPT_NODE: Final[str] = 'generate_script'
    _EVALUATE_GENERATED_SCRIPT_NODE: Final[str] = 'evaluate_generated_script'
    _FIND_MEDIA_NODE: Final[str] = 'find_media'
    _EVALUATE_FOUND_MEDIA_NODE: Final[str] = 'evaluate_found_media'
    _DOWNLOAD_MEDIA_NODE: Final[str] = 'download_media'
    _EVALUATE_DOWNLOADED_MEDIA_NODE: Final[str] = 'evaluate_downloaded_media'
    _EDIT_VIDEO_NODE: Final[str] = 'edit_video'
    _EVALUATE_EDITED_VIDEO_NODE: Final[str] = 'evaluate_edited_video'

    def __init__(
        self,
        download_media_artifact_manager: ArtifactManager,
        download_media_category: str,
        edit_video_artifact_manager: ArtifactManager,
        edit_video_category: str,
        download_media_kind: Kind = _KIND,
        edit_video_kind: Kind = _KIND,
        generate_script_max_calls: int = _MAX_CALLS,
        find_media_max_calls: int = _MAX_CALLS,
        download_media_max_calls: int = _MAX_CALLS,
        edit_video_max_calls: int = _MAX_CALLS,
    ) -> None:
        message = 'building the content graph'
        _logger.info(message)
        
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

        message = 'finished building the content graph'
        _logger.info(message)

    def get_compiled_state_graph(self) -> CompiledStateGraph[State, None, State, State]:
        return self._compiled_state_graph

    def _run_generate_script(self, state: State) -> dict[str, Any]:
        output = self._generate_script(self._script_generation_input(state))

        return {'script': output.script}

    def _run_evaluate_generated_script(self, state: State) -> dict[str, Any]:
        output = self._evaluate_generated_script(
            GeneratedScriptEvaluationInput(
                script_generation_input=self._script_generation_input(state),
                script_generation_output=ScriptGenerationOutput(script=self._require(state.script, 'script')),
                evaluation_instructions=state.script_evaluation_instructions,
            ),
        )

        return self._update(state, 'generation_instructions', output.evaluation)

    def _run_find_media(self, state: State) -> dict[str, Any]:
        output = self._find_media(self._media_finding_input(state))

        return {'media_links': output.media_links}

    def _run_evaluate_found_media(self, state: State) -> dict[str, Any]:
        output = self._evaluate_found_media(
            FoundMediaEvaluationInput(
                media_finding_input=self._media_finding_input(state),
                media_finding_output=MediaFindingOutput(
                    media_links=self._require(state.media_links, 'media links'),
                ),
                evaluation_instructions=state.found_media_evaluation_instructions,
            ),
        )

        return self._update(state, 'media_finding_instructions', output.evaluation)

    def _run_download_media(self, state: State) -> dict[str, Any]:
        output = self._download_media(self._media_download_input(state))

        return {'media_files': output.media_files}

    def _run_evaluate_downloaded_media(self, state: State) -> dict[str, Any]:
        output = self._evaluate_downloaded_media(
            DownloadedMediaEvaluationInput(
                media_download_input=self._media_download_input(state),
                media_download_output=MediaDownloadOutput(
                    media_files=self._require(state.media_files, 'media files'),
                ),
                evaluation_instructions=state.downloaded_media_evaluation_instructions,
            ),
        )

        return {'evaluation': output.evaluation}

    def _run_edit_video(self, state: State) -> dict[str, Any]:
        output = self._edit_video(self._video_editing_input(state))

        return {'video': output.video}

    def _run_evaluate_edited_video(self, state: State) -> dict[str, Any]:
        output = self._evaluate_edited_video(
            EditedVideoEvaluationInput(
                video_editing_input=self._video_editing_input(state),
                video_editing_output=VideoEditingOutput(video=self._require(state.video, 'video')),
                evaluation_instructions=state.edited_video_evaluation_instructions,
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

    @staticmethod
    def _update(state: State, instructions_field: str, evaluation: Evaluation) -> dict[str, Any]:
        update: dict[str, Any] = {'evaluation': evaluation}

        # A failed stage runs again from its instructions alone, so the feedback is stacked onto them
        if evaluation.grade is Grade.FAIL:
            instructions: str = getattr(state, instructions_field)
            attempt = instructions.count(Automatic._FEEDBACK_MARKER) + 1
            update[instructions_field] = (
                f'{instructions}\n\n'
                f'{Automatic._FEEDBACK_MARKER} {attempt}, which failed: {evaluation.feedback}'
            )

        return update

    @staticmethod
    def _script_generation_input(state: State) -> ScriptGenerationInput:
        return ScriptGenerationInput(instructions=state.generation_instructions)

    @staticmethod
    def _media_finding_input(state: State) -> MediaFindingInput:
        return MediaFindingInput(
            script=Automatic._require(state.script, 'script'),
            instructions=state.media_finding_instructions,
        )

    @staticmethod
    def _media_download_input(state: State) -> MediaDownloadInput:
        return MediaDownloadInput(media_links=Automatic._require(state.media_links, 'media links'))

    @staticmethod
    def _video_editing_input(state: State) -> VideoEditingInput:
        return VideoEditingInput(
            script=Automatic._require(state.script, 'script'),
            media_files=Automatic._require(state.media_files, 'media files'),
        )

    @staticmethod
    def _decision_input(state: State) -> DecisionInput:
        return DecisionInput(evaluation=Automatic._require(state.evaluation, 'evaluation'))

    @staticmethod
    def _require(value: T | None, name: str) -> T:
        if value is None:
            message = f'the state has no {name}'
            _logger.error(message)
            raise RuntimeError(message)

        return value

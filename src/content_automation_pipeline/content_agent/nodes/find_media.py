import json
from typing import Final

import openai_codex
from pydantic import BaseModel, ConfigDict

from content_automation_pipeline.content_agent.models.evaluation import Evaluation
from content_automation_pipeline.content_agent.models.media_links import (
    MediaLink,
    MediaLinks,
)
from content_automation_pipeline.content_agent.models.script import Script
from content_automation_pipeline.content_agent.tools.youtube_downloader import (
    YoutubeDownloader,
)
from content_automation_pipeline.shared.node import Node, Strategy
from content_automation_pipeline.shared.rate_limited_node import RateLimitedNode
from content_automation_pipeline.utilities.logger import create_logger

_logger = create_logger(__name__)

class MediaFindingInput(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)

    script: Script
    instructions: str

class MediaFindingOutput(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)

    media_links: MediaLinks

class MediaFindingStrategy(Strategy[MediaFindingInput, MediaFindingOutput]):
    # Default values that can be overridden by the user
    _DEFAULT_MAX_QUERY_ATTEMPTS: Final[int] = 1
    # Hardcoded values that cannot be overridden by the user
    _NO_FEEDBACK: Final[str] = 'there is no feedback.'
    _INSTRUCTION_TEMPLATE: Final[str] = (
        'Decide what to search for on YouTube to find the {media_type} that best matches the entry, '
        'following the instructions.\n\n'
        'Entry: {line}\n\n'
        'Title and subheading for context: {title1} {title2} - {subheading}\n\n'
        'Instructions: {instructions}\n\n'
        'Feedback: {feedback}'
    )

    def __init__(
        self,
        max_query_attempts: int = _DEFAULT_MAX_QUERY_ATTEMPTS,
    ) -> None:
        self._max_query_attempts = max_query_attempts
        self._search = YoutubeDownloader.search

    def execute(self, input: MediaFindingInput) -> MediaFindingOutput:
        script = input.script
        entries = [
            self._find_entry_link(entry.line, script.title1, script.title2, script.subheading, input.instructions)
            for entry in script.entries
        ]

        return MediaFindingOutput(media_links=MediaLinks(entries=entries))

    def _find_entry_link(self, line: str, title1: str, title2: str, subheading: str, instructions: str) -> MediaLink:
        with openai_codex.Codex() as codex:
            thread = codex.thread_start(sandbox=openai_codex.Sandbox.read_only)
            video_link = self._find_link(thread, 'video', line, title1, title2, subheading, instructions)
            audio_link = self._find_link(thread, 'audio', line, title1, title2, subheading, instructions)

        return MediaLink(video_link=video_link, audio_link=audio_link)

    def _find_link(
        self,
        thread: openai_codex.Thread,
        media_type: str,
        line: str,
        title1: str,
        title2: str,
        subheading: str,
        instructions: str,
    ) -> str:
        feedback = self._NO_FEEDBACK

        for attempt in range(self._max_query_attempts):
            query = self._ask_for_query(thread, media_type, line, title1, title2, subheading, instructions, feedback)
            results = self._search(query)

            if results:
                return results[0]

            message = f'attempt {attempt + 1}/{self._max_query_attempts} found no results for query={query}'
            _logger.warning(message)
            feedback = f'the query "{query}" returned no results, try a different query.'

        message = f'reached the maximum of {self._max_query_attempts} attempt(s) to find a link for entry={line}'
        _logger.error(message)
        raise RuntimeError(message)

    def _ask_for_query(
        self,
        thread: openai_codex.Thread,
        media_type: str,
        line: str,
        title1: str,
        title2: str,
        subheading: str,
        instructions: str,
        feedback: str,
    ) -> str:
        class _SearchQuery(BaseModel):
            model_config = ConfigDict(extra='forbid', strict=True)

            query: str

        instruction = self._INSTRUCTION_TEMPLATE.format(
            media_type=media_type,
            line=line,
            title1=title1,
            title2=title2,
            subheading=subheading,
            instructions=instructions,
            feedback=feedback,
        )

        result = thread.run(instruction, output_schema=_SearchQuery.model_json_schema())
        final_response = result.final_response

        # Narrow to str
        if final_response is None:
            message = 'did not return a search query'
            _logger.error(message)
            raise RuntimeError(message)

        return _SearchQuery.model_validate_json(final_response).query

class FindMedia(RateLimitedNode[MediaFindingInput, MediaFindingOutput]):
    def __init__(
        self,
        strategy: Strategy[MediaFindingInput, MediaFindingOutput],
        max_calls: int = RateLimitedNode._DEFAULT_MAX_CALLS,
    ) -> None:
        super().__init__(strategy, max_calls)

class FoundMediaEvaluationInput(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)

    # Input for the FindMedia node
    media_finding_input: MediaFindingInput
    # Output from the FindMedia node
    media_finding_output: MediaFindingOutput
    # Instructions for evaluating output given the input
    evaluation_instructions: str

class FoundMediaEvaluationOutput(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)

    evaluation: Evaluation

class FoundMediaEvaluationStrategy(Strategy[FoundMediaEvaluationInput, FoundMediaEvaluationOutput]):
    # Hardcoded values that cannot be overridden by the user
    _INSTRUCTION_TEMPLATE: Final[str] = (
        'Evaluate the output of a node given its input, the required output schema, and the evaluation instructions.\n\n'
        'Assign the grade pass when the output is successful in the evaluation, and the grade fail otherwise. '
        'Give feedback that supports the grade.\n\n'
        'Input: {input}\n\n'
        'Output: {output}\n\n'
        'Output schema: {output_schema}\n\n'
        'Evaluation instructions: {evaluation_instructions}'
    )

    def execute(self, input: FoundMediaEvaluationInput) -> FoundMediaEvaluationOutput:
        instruction = self._INSTRUCTION_TEMPLATE.format(
            input=input.media_finding_input.model_dump_json(),
            output=input.media_finding_output.model_dump_json(),
            output_schema=json.dumps(MediaFindingOutput.model_json_schema()),
            evaluation_instructions=input.evaluation_instructions,
        )

        # Use Codex to grade and give feedback on the media links
        with openai_codex.Codex() as codex:
            thread = codex.thread_start(sandbox=openai_codex.Sandbox.read_only)
            result = thread.run(instruction, output_schema=Evaluation.model_json_schema())

        final_response = result.final_response

        # Narrow to str
        if final_response is None:
            message = 'did not return a response'
            _logger.error(message)
            raise RuntimeError(message)

        return FoundMediaEvaluationOutput(evaluation=Evaluation.model_validate_json(final_response))

class EvaluateFoundMedia(Node[FoundMediaEvaluationInput, FoundMediaEvaluationOutput]):
    def __init__(
        self,
        strategy: Strategy[FoundMediaEvaluationInput, FoundMediaEvaluationOutput],
    ) -> None:
        super().__init__(strategy)

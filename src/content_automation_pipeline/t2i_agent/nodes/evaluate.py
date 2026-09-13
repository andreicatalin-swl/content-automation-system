from abc import ABC, abstractmethod
from typing import Final

import openai_codex

from content_automation_pipeline.artifacts.artifact import Artifact
from content_automation_pipeline.artifacts.artifact_manager import ArtifactManager
from content_automation_pipeline.t2i_agent.models.evaluation import Evaluation
from content_automation_pipeline.t2i_agent.states.state import State
from content_automation_pipeline.utilities.logger import create_logger

_logger = create_logger(__name__)

class EvaluationStrategy(ABC):
    @abstractmethod
    def evaluate(self, prompt: str, artifact: Artifact) -> Evaluation:
        ...

class CodexEvaluationStrategy(EvaluationStrategy):
    # Hardcoded values that cannot be overridden by the user
    _INSTRUCTION_TEMPLATE: Final[str] = (
        'Evaluate the attached image against the description it was generated from.\n\n'
        'Description: {prompt}\n\n'
        'Assign the grade pass when the image matches the description, and the grade fail otherwise. '
        'Describe in the feedback what has to change so the image can be generated again.'
    )

    def __init__(
        self,
        artifact_manager: ArtifactManager,
    ) -> None:
        self._artifact_manager = artifact_manager

    def evaluate(self, prompt: str, artifact: Artifact) -> Evaluation:
        message = f'evaluating image for prompt={prompt}'
        _logger.info(message)

        # Construct the instruction for Codex
        image_path = self._artifact_manager.path(artifact)
        instruction = self._INSTRUCTION_TEMPLATE.format(prompt=prompt)

        # Use Codex to grade the image against the prompt it was generated from
        with openai_codex.Codex() as codex:
            thread = codex.thread_start(sandbox=openai_codex.Sandbox.read_only)
            result = thread.run(
                [openai_codex.TextInput(text=instruction), openai_codex.LocalImageInput(path=str(image_path))],
                output_schema=Evaluation.model_json_schema(),
            )

        final_response = result.final_response

        # Run verification to validate node output quality and correctness
        if not final_response:
            message = 'did not return an evaluation'
            _logger.error(message)
            raise RuntimeError(message)

        evaluation = Evaluation.model_validate_json(final_response)

        message = f'finished evaluating image for prompt={prompt} with grade={evaluation.grade}'
        _logger.info(message)

        return evaluation

class Evaluate:
    _DEFAULT_MAX_ATTEMPTS: Final[int] = 1

    def __init__(
        self,
        strategy: EvaluationStrategy,
        max_attempts: int = _DEFAULT_MAX_ATTEMPTS,
    ) -> None:
        self._strategy = strategy
        self._max_attempts = max_attempts

    def __call__(self, state: State) -> State:
        # Check if the maximum number of attempts has been reached
        if state.evaluation_attempts >= self._max_attempts:
            message = f'reached the maximum of {self._max_attempts} attempt(s) for prompt={state.prompt}'
            _logger.error(message)
            raise RuntimeError(message)

        # Check if there is an image to evaluate
        if state.artifact is None:
            message = f'there is no image to evaluate for prompt={state.prompt}'
            _logger.error(message)
            raise RuntimeError(message)

        state.evaluation_attempts += 1

        # Retry with another evaluation if the strategy fails to produce an evaluation
        try:
            state.evaluation = self._strategy.evaluate(state.prompt, state.artifact)
        except Exception:
            message = f'attempt {state.evaluation_attempts}/{self._max_attempts} failed to evaluate the image for prompt={state.prompt}'
            _logger.exception(message)
            return self(state)

        return state

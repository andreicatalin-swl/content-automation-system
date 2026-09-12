from typing import Final

import openai_codex

from content_automation_pipeline.artifacts.artifact_manager import ArtifactManager
from content_automation_pipeline.t2i_agent.models.evaluation import Evaluation
from content_automation_pipeline.t2i_agent.states.state import State
from content_automation_pipeline.utilities.logger import create_logger

_logger = create_logger(__name__)

class Evaluate:
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
        max_attempts: int,
    ) -> None:
        self._artifact_manager = artifact_manager
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

        message = f'evaluating image for prompt={state.prompt}'
        _logger.info(message)

        image_path = self._artifact_manager.path(state.artifact)
        instruction = self._INSTRUCTION_TEMPLATE.format(prompt=state.prompt)

        # Use Codex to grade the image against the prompt it was generated from
        with openai_codex.Codex() as codex:
            thread = codex.thread_start(sandbox=openai_codex.Sandbox.read_only)
            result = thread.run(
                [openai_codex.TextInput(text=instruction), openai_codex.LocalImageInput(path=str(image_path))],
                output_schema=Evaluation.model_json_schema(),
            )

        state.evaluation_attempts += 1

        # Retry if Codex did not respond with an evaluation
        if not result.final_response:
            message = f'attempt {state.evaluation_attempts}/{self._max_attempts} did not return an evaluation'
            _logger.warning(message)
            return self(state)

        state.evaluation = Evaluation.model_validate_json(result.final_response)

        message = f'finished evaluating image for prompt={state.prompt} with grade={state.evaluation.grade}'
        _logger.info(message)

        return state

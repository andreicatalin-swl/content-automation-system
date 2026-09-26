from pydantic import BaseModel, ConfigDict

from content_automation_pipeline.shared.abstract_node import AbstractNode


class DecisionInput(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)

    post_to_youtube: bool

    def __repr__(self) -> str:
        return repr(self.post_to_youtube)


class DecisionOutput(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)

    destination: str

    def __repr__(self) -> str:
        return self.destination


class Decide(AbstractNode[DecisionInput, DecisionOutput]):
    def __init__(
        self,
        post_node: str,
        skip_node: str,
    ) -> None:
        self._post_node = post_node
        self._skip_node = skip_node

    def execute(self, input: DecisionInput) -> DecisionOutput:
        destination = self._post_node if input.post_to_youtube else self._skip_node

        return DecisionOutput(destination=destination)

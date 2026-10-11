"""Frozen values carried by protocol arrows, separate from command results."""

from typing import Literal

from comeni_core.goal.asked import Constraints
from comeni_core.spell.marks import HumanParamValue, TypeId
from pydantic import BaseModel, ConfigDict, Field


class _Payload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class StatedCandidate(_Payload):
    kind: Literal["input", "measurement"]
    subject: str = Field(min_length=1, max_length=128)
    value: HumanParamValue | None = None


class Extraction(_Payload):
    """A model's suggestions; confirmation creates decisions separately."""

    want: list[TypeId] = Field(min_length=1)
    constraints: Constraints = Field(default_factory=Constraints)
    suggested: Constraints = Field(default_factory=Constraints)
    stated: list[StatedCandidate] = Field(default_factory=list)


class Empty(_Payload):
    pass


class GoalReturned(_Payload):
    extraction: Extraction


class GapAnswered(_Payload):
    answered: Literal["said", "left_open", "no_input"]


class SampleAnswered(_Payload):
    answered: bool


class Amended(_Payload):
    said: str = Field(max_length=2000)


EMPTY = Empty()

Payload = Empty | GoalReturned | GapAnswered | SampleAnswered | Amended

_TYPES = {"understood": GoalReturned, "answer_gap": GapAnswered,
          "upload_sample": SampleAnswered, "amend": Amended}


def check(arrow: str | None, payload: Payload) -> Payload:
    expected = _TYPES.get(arrow, Empty)
    if type(payload) is not expected:
        raise ValueError(f"{arrow}: payload must be {expected.__name__}")
    return payload


class ContextStamp(_Payload):
    decision_revision: int = Field(ge=0)
    context_digest: str = Field(min_length=64, max_length=64)

"""Frozen values carried by protocol arrows, separate from command results."""

from typing import Literal, NamedTuple

from comeni_core.goal.asked import Constraints
from comeni_core.spell.marks import HumanParamValue, TypeId
from pydantic import BaseModel, ConfigDict, Field

from mendel_authoring.blueprint import Blueprint


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
    conflicts: bool = False
    continuation: Literal["gather", "goal", "build", "complete", "stopped"] = "gather"


class Amended(_Payload):
    said: str = Field(max_length=2000)


class Correction(_Payload):
    subject: str
    value: HumanParamValue | None = None
    who: str
    kind: Literal["measurement", "input", "producer", "retain", "observation"]
    observation_id: str | None = None
    states: list[str] = Field(default_factory=list)
    continuation: Literal["gather", "goal", "build", "complete", "stopped"]
    before: Blueprint | None = None
    after: Blueprint | None = None
    missing: str | None = None
    pin_blocked: bool = False


EMPTY = Empty()

Payload = Empty | GoalReturned | GapAnswered | SampleAnswered | Amended | Correction

_TYPES = {"understood": GoalReturned, "answer_gap": GapAnswered,
          "upload_sample": SampleAnswered, "amend": Amended,
          "correct_fact": Correction, "answer_disagreement": Correction,
          "release_producer": Correction, "fork_correction": Correction}


def check(arrow: str | None, payload: Payload) -> Payload:
    expected = _TYPES.get(arrow, Empty)
    if type(payload) is not expected:
        raise ValueError(f"{arrow}: payload must be {expected.__name__}")
    return payload


class ContextStamp(NamedTuple):
    """Plain immutable values identifying the context a background result belongs to."""

    decision_revision: int
    context_digest: str

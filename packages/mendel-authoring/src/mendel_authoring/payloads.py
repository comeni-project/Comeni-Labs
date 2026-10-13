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
    value: HumanParamValue | list[HumanParamValue] | None = None


class Extraction(_Payload):
    """A model's suggestions; confirmation creates decisions separately."""

    want: list[TypeId] = Field(min_length=1)
    constraints: Constraints = Field(default_factory=Constraints)
    suggested: Constraints = Field(default_factory=Constraints)
    stated: list[StatedCandidate] = Field(default_factory=list)


class Empty(_Payload):
    pass


class GapAnswered(_Payload):
    answered: Literal["said", "left_open", "no_input"]


class SampleAnswered(_Payload):
    answered: bool
    conflicts: bool = False
    continuation: Literal["gather", "goal", "build", "complete", "stopped"] = "gather"


class Amended(_Payload):
    said: str = Field(max_length=2000)


class DecisionChange(_Payload):
    """One change to intent or facts, from any caller — the person's click or edit, the chat
    model's reply, a stage's own handler (Part I.0 spec §5.1). `heard` is the person's words it
    was taken from, already checked (`heard.find`); `retract` removes what `subject` names."""

    kind: Literal["want", "input", "measurement", "require", "pin", "parameter", "asked",
                  "producer", "retain", "observation"]
    subject: str = Field(min_length=1, max_length=256)
    value: HumanParamValue | list[HumanParamValue] | None = None
    states: list[str] = Field(default_factory=list)
    retract: bool = False
    heard: str | None = Field(default=None, max_length=500)
    heard_seq: int | None = None
    actor: Literal["person", "model"] = "person"
    invocation_id: str | None = None
    observation_id: str | None = None


class GoalReturned(_Payload):
    """What the model read from the person's first words (Part I.0 §5.3): changes it heard,
    quoting them, which are recorded; and changes it suggests, which wait for a click."""

    heard: list[DecisionChange] = Field(default_factory=list)
    suggested: list[DecisionChange] = Field(default_factory=list)


class Correction(_Payload):
    subject: str
    value: HumanParamValue | list[HumanParamValue] | None = None
    who: str
    kind: Literal["measurement", "input", "producer", "retain", "observation", "want",
                  "require", "pin", "parameter", "asked"]
    observation_id: str | None = None
    states: list[str] = Field(default_factory=list)
    continuation: Literal["gather", "goal", "build", "complete", "stopped"]
    before: Blueprint | None = None
    after: Blueprint | None = None
    missing: str | None = None
    missing_states: list[str] = Field(default_factory=list)
    pin_blocked: bool = False
    change: DecisionChange | None = None
    """The general change this correction carries (Part I.0); `None` for the older kinds."""


EMPTY = Empty()

Payload = Empty | GoalReturned | GapAnswered | SampleAnswered | Amended | Correction

_TYPES = {"understood": GoalReturned, "answer_gap": GapAnswered,
          "upload_sample": SampleAnswered, "compare_evidence": SampleAnswered, "amend": Amended,
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

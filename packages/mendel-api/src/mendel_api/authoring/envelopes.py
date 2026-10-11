"""Closed offers, including their immutable context and fixed answer options."""

from typing import Annotated, Any, Literal, Self

from comeni_core.diagnostics import coded
from comeni_core.goal.asked import Goal
from comeni_core.plan.draft import DraftEdge
from comeni_core.spell.marks import NodeId
from mendel_authoring.amend import ChooseTool
from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, model_validator

from mendel_api.authoring.types import FactKind, GoalSummary, Question, StepProposal


class _Shape(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class OfferContext(_Shape):
    draft_revision: int = Field(ge=0)
    decision_revision: int = Field(ge=0)
    session_version: int = Field(ge=0)
    registry: str


class _Offer(_Shape):
    context: OfferContext
    options: dict[str, str]


class GoalOffer(_Offer):
    offer: Literal["goal"] = "goal"
    block: GoalSummary
    goal: Goal

    @model_validator(mode="after")
    def _same_goal(self) -> Self:
        if self.block.goal != self.goal or self.options != {"accept": "accept"}:
            raise ValueError("the goal and its fixed options must agree with the card")
        return self


class GapOffer(_Offer):
    offer: Literal["gap"] = "gap"
    subject: str = Field(min_length=1, max_length=128)
    kind: FactKind
    why: str
    block: Question

    @model_validator(mode="after")
    def _fixed_options(self) -> Self:
        if set(self.options) != {o.id for o in self.block.options}:
            raise ValueError("question options must equal the offered options")
        return self


class StepOffer(_Offer):
    offer: Literal["step"] = "step"
    node: NodeId
    block: StepProposal
    amendments: dict[str, ChooseTool]
    edges: list[DraftEdge]

    @model_validator(mode="after")
    def _same_step(self) -> Self:
        if self.node != self.block.node:
            raise ValueError("the offered node must equal the step card's node")
        if not set(self.amendments) <= set(self.options):
            raise ValueError("amendments must name offered options")
        for option, amendment in self.amendments.items():
            if self.options[option] != amendment.pin.contract:
                raise ValueError("an amendment must select its offered contract")
        return self


class PacingOffer(_Offer):
    offer: Literal["pacing"] = "pacing"
    block: Question

    @model_validator(mode="after")
    def _fixed_options(self) -> Self:
        if set(self.options) != {o.id for o in self.block.options}:
            raise ValueError("pacing options must equal the offered options")
        return self


class DisagreementOffer(_Offer):
    offer: Literal["disagreement"] = "disagreement"
    subject: str
    observation_id: str
    current_revision_id: str | None
    continuation: Literal["gather", "goal", "build", "complete", "stopped"]
    block: Question

    @model_validator(mode="after")
    def _fixed_options(self) -> Self:
        if (set(self.options) != {"keep_current", "use_measurement", "correct"}
                or set(self.options) != {o.id for o in self.block.options}):
            raise ValueError("disagreement options must explicitly retain, select, or correct")
        return self


Offer = Annotated[GoalOffer | GapOffer | StepOffer | PacingOffer | DisagreementOffer,
                  Field(discriminator="offer")]
_ADAPTER = TypeAdapter(Offer)


def parse(payload, *, kind):
    envelope = _ADAPTER.validate_python(payload)
    if envelope.offer != kind:
        raise ValueError("the envelope variant does not match the proposal kind")
    return envelope


def prepare(payload, *, kind, draft, session):
    return parse({**payload, "offer": kind, "context": {
        "draft_revision": draft.revision, "decision_revision": draft.decision_revision,
        "session_version": session.row_version, "registry": session.registry_digest,
    }}, kind=kind).model_dump(mode="json")


def answer(envelope, *, option, subject=None, decision_revision=None):
    if option not in envelope.options:
        raise ValueError(coded("MI0205", "that option was not offered"))
    if subject is not None and getattr(envelope, "subject", None) != subject:
        raise ValueError(coded("MI0205", "that answer names a different subject"))
    if (decision_revision is not None
            and decision_revision != envelope.context.decision_revision):
        raise ValueError(coded("MI0201", "the selected decisions changed after this offer"))
    return envelope.options[option]


class LegacyOffer(_Shape):
    """An archived snapshot, never accepted as a live mutation offer."""

    offer: Literal["legacy"] = "legacy"
    kind: str
    snapshot: dict[str, Any]


HistoryOffer = Offer | LegacyOffer


def historical(payload, *, kind):
    if "offer" in payload:
        return parse(payload, kind=kind)
    return LegacyOffer(kind=kind, snapshot=payload)

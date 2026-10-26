"""Typed questions, answers, and persistent records for unresolved planning choices.

Each decision declares a `kind` discriminator so its candidates, chosen value, and overrides
retain their domain-specific types during serialization and replay.
"""

from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from comeni_core.plan.tiers import Tier
from comeni_core.review import Answer, Question, ValueSource
from comeni_core.spell.marks import (
    ContractId,
    DecisionKey,
    EdgeRef,
    HumanParamValue,
    Line,
    MeasurementId,
    NodeId,
    ParamValue,
    ResolverId,
    StateName,
    Subject,
    TypeId,
)


class DecisionKind(StrEnum):
    """What sort of question was asked. The discriminator, and closed."""

    PARAM = "param"
    PRODUCER = "producer"
    SOURCE = "source"
    FACT = "fact"


class Ambiguity(Question):
    """A typed question that deterministic resolution could not answer."""

    node_id: NodeId
    subject: Subject
    """Declared subject written into the persistent decision record."""

    def key(self) -> str:
        return f"{self.node_id}.{self.subject}"


class ParamAsked(Ambiguity):
    """No rule matched and no default exists. Tier 4 for a parameter."""

    kind: Literal[DecisionKind.PARAM] = DecisionKind.PARAM
    candidates: list[ParamValue] = Field(default_factory=list)
    tier_hint: int | None = None


class ProducerAsked(Ambiguity):
    """A choice between otherwise indistinguishable producer contracts."""

    kind: Literal[DecisionKind.PRODUCER] = DecisionKind.PRODUCER
    candidates: list[ContractId] = Field(default_factory=list)
    states: list[StateName] = Field(default_factory=list)

    def key(self) -> str:
        """Identify the producer question by type, independently of the current winner."""
        return self.subject


class SourceAsked(Ambiguity):
    """Two upstream outputs could feed one port, equally well."""

    kind: Literal[DecisionKind.SOURCE] = DecisionKind.SOURCE
    candidates: list[EdgeRef] = Field(default_factory=list)
    type_id: TypeId = ""
    required: list[StateName] = Field(default_factory=list)


AmbiguityKinds = (ParamAsked, ProducerAsked, SourceAsked)
"""Question shapes that may cross the ambiguity-resolution boundary."""


class Resolution(Answer):
    """A resolver's typed answer to an ambiguity."""

    value: ParamValue
    """Resolved scalar value, narrowed from the generic answer contract."""
    why: Line
    confidence: float = 0.0
    """Optional resolver confidence; generic answers do not declare this field."""
    by: ResolverId = "flag-only"
    """Identifier of the resolver implementation that supplied the answer."""
    how: ValueSource = ValueSource.RESOLVER
    """Source category that settled the value, distinct from the resolver ID and tier."""


class _Decided(BaseModel):
    """Fields and authorship rules shared by every persistent decision."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    key: DecisionKey
    subject: Subject
    """Object being decided; `kind` separately identifies the decision category."""
    reason: Line
    """Model- or resolver-written explanation."""
    confidence: float = 0.0
    resolved_by: ResolverId
    tier: Tier = Tier.AMBIGUOUS

    model_override_by: ResolverId = ""
    """Model responsible for `model_override`; empty when no model overrode the result."""

    @model_validator(mode="after")
    def _one_author(self) -> "_Decided":
        """Require one attributable override author.

        Human and model overrides are mutually exclusive. A model override requires its model
        ID, and a model ID requires a non-null override. Null parameter overrides cannot be
        distinguished from absence because `HumanParamValue` includes `None`.
        """
        model = getattr(self, "model_override", None)
        if model is not None and not self.model_override_by:
            raise ValueError(
                "model_override without model_override_by: an override with no author is "
                "indistinguishable from the resolver's own answer"
            )
        human = getattr(self, "human_override", None)
        if model is not None and human is not None:
            raise ValueError(
                "both human_override and model_override are set; a choice has one author"
            )
        if self.model_override_by and model is None:
            raise ValueError(
                f"model_override_by is {self.model_override_by!r} but no model_override is "
                f"recorded; an author with no act reads as a model decision that never happened"
            )
        return self


class ParamDecision(_Decided):
    """The selected value for a parameter whose domain may still be open."""

    kind: Literal[DecisionKind.PARAM] = DecisionKind.PARAM
    candidates: list[ParamValue] = Field(default_factory=list)
    chosen: ParamValue
    model_override: HumanParamValue = None
    """A model-authored replacement, kept separate from a human override."""

    human_override: HumanParamValue = None
    """A reviewer-authored replacement, restricted to safe human parameter values."""

    override_reason: Line = ""
    """Reviewer's explanation; an empty value means no explanation was supplied."""


class ProducerDecision(_Decided):
    """Which contract produces a type here."""

    kind: Literal[DecisionKind.PRODUCER] = DecisionKind.PRODUCER
    candidates: list[ContractId] = Field(default_factory=list)
    chosen: ContractId
    human_override: ContractId | None = None
    model_override: ContractId | None = None
    unknown: list[MeasurementId] = Field(
        default_factory=list, exclude_if=lambda unknown: not unknown
    )
    """Unknown measurements blocking this choice; omitted from serialization when empty."""


class SourceDecision(_Decided):
    """Which upstream output feeds a consumer's port."""

    kind: Literal[DecisionKind.SOURCE] = DecisionKind.SOURCE
    candidates: list[EdgeRef] = Field(default_factory=list)
    chosen: EdgeRef
    human_override: EdgeRef | None = None
    model_override: EdgeRef | None = None


class FactDecision(_Decided):
    """An unknown shared fact required by a chosen tool.

    The eventual answer is stored as a fact rather than as a step-specific parameter decision,
    so this temporary record is not replayed after the fact becomes known.
    """

    kind: Literal[DecisionKind.FACT] = DecisionKind.FACT
    candidates: list[ParamValue] = Field(default_factory=list)
    chosen: ParamValue = None
    """Nothing is chosen here: the answer is recorded as the fact."""
    unknown: list[MeasurementId]


DecisionRecord = Annotated[
    ParamDecision | ProducerDecision | SourceDecision | FactDecision,
    Field(discriminator="kind"),
]
"""Persistent decision union, discriminated by `kind`."""

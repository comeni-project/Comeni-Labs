"""Decision records: what was ambiguous, what was chosen, and why.

**A record declares its kind.** `DecisionRecord.chosen` used to carry three different sorts
of value under one type, and the discriminator was a string prefix that was not even
consistent:

    subject=f"producer:{type_id}"    # chosen is a ContractId
    subject=f"source:{port.name}"    # chosen is "{node}.{port}"
    subject=param_name               # chosen is a ParamValue — no prefix at all

Two kinds prefixed, one not, so "what kind of decision is this?" was answered by
pattern-matching a string nobody designed to be parsed. That is audit A16, and it is why
A3's path-shaped blocklist could not be applied to `chosen`: `dual.bam` is an *edge
reference* and is character-for-character a filename.

With three types the collision goes away by construction. `EdgeRef` is
`<identifier>.<identifier>`, so `dual.bam` is accepted **because it is declared**, not
tolerated because a blocklist was narrowed around it — and `run.cram` is refused for naming
no node. `HumanParamValue`'s blocklist survives on `ParamDecision.human_override` alone,
which is the one kind with no domain yet; that is Plan 2 Task 11's job.
"""

from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from comeni_core.plan.tiers import Tier
from comeni_core.review import Answer, Question, ValueSource
from comeni_core.spell.marks import (
    ContractId,
    DecisionKey,
    EdgeRef,
    HumanParamValue,
    Line,
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


class Ambiguity(Question):
    """A question the deterministic ladder could not answer.

    **This is a door, and it was the only one with no type discipline.** A32: `candidates:
    list[Any]` and `context: dict[str, Any]`, no `model_config` at all, so `extra` defaulted
    to *ignore* — a field misspelled at the call site vanished, and any object at all could
    be attached to a value that a model provider sees. It projects to `AmbiguityRequest`,
    which is a closed payload; the closed half was downstream of the open half.

    Three kinds, so `context`'s three uses become declared fields on the kind that has them.
    A model sitting behind this port sees what the registry declares and nothing else.
    """

    node_id: NodeId
    subject: Subject
    """Re-narrowed from `Question.subject`, which is a plain `str`.

    `Subject` is a declared mark and this value reaches `pipeline.yml` through every
    decision record, so the looser base type must not win by inheritance. Same move
    `Resolution` makes on `value`.
    """

    def key(self) -> str:
        return f"{self.node_id}.{self.subject}"


class ParamAsked(Ambiguity):
    """No rule matched and no default exists. Tier 4 for a parameter."""

    kind: Literal[DecisionKind.PARAM] = DecisionKind.PARAM
    candidates: list[ParamValue] = Field(default_factory=list)
    tier_hint: int | None = None


class ProducerAsked(Ambiguity):
    """Several contracts produce this and nothing distinguishes them. Invariant 8."""

    kind: Literal[DecisionKind.PRODUCER] = DecisionKind.PRODUCER
    candidates: list[ContractId] = Field(default_factory=list)
    states: list[StateName] = Field(default_factory=list)

    def key(self) -> str:
        """What is being decided, never who won it.

        The inherited key is `node_id.subject`, and a producer question's `node_id` is the
        *winning candidate's* process name — so installing one more contract renamed the
        question. `upgrade` found no record under the new name, reported a curator's recorded
        override as `ORPHANED — your edit no longer applies to anything`, and asked the
        identical question one line above under the new name. Audit A126.

        `subject` is already `producer:<type_id>`, which identifies the question uniquely
        within a pipeline: a contract appears at most once (A97), so there is exactly one
        producer question per type. `ParamAsked` and `SourceAsked` keep the inherited form,
        because those genuinely are per-step — two steps may ask about the same parameter
        name and mean different things.
        """
        return self.subject


class SourceAsked(Ambiguity):
    """Two upstream outputs could feed one port, equally well."""

    kind: Literal[DecisionKind.SOURCE] = DecisionKind.SOURCE
    candidates: list[EdgeRef] = Field(default_factory=list)
    type_id: TypeId = ""
    required: list[StateName] = Field(default_factory=list)


AmbiguityKinds = (ParamAsked, ProducerAsked, SourceAsked)
"""The three shapes a tier-4 question can take.

Named as a tuple so `tests/test_egress.py` can assert the projection to `AmbiguityRequest`
is *total* — a fourth kind added without a slot at the door would fail that test rather than
quietly not be told to a model."""


class Resolution(Answer):
    """The answer coming back through the port. Also a boundary, in the other direction."""

    value: ParamValue
    """Re-narrowed from `Answer.value`, which is `Any`. The base is deliberately looser
    than this subclass — see the spec's §4.2."""
    why: Line
    confidence: float = 0.0
    """Stays on this subclass. A forge fill has no confidence, and putting the field on
    `Answer` would declare one that nothing writes."""
    by: ResolverId = "flag-only"
    """A declared id, not a bare `str`: this is written into every `DecisionRecord` and
    reaches a publish bundle, and it is filled in by whatever implements the port.

    Was `resolved_by`. Renamed to the shared `Answer.by` in Plan 2.5 — the forge's
    `FilledValue.by` carried the same fact (a username, a model id, a resolver id) under
    the shorter name, and one of the two spellings had to go.
    """
    how: ValueSource = ValueSource.RESOLVER
    """Who settled it, as distinct from *how well* (`tier`) and *by which implementation*
    (`by`). Was `source`.

    Only `ReplayResolver` sets this to `HUMAN`, and only when the record it replayed carries
    a `human_override` — the one field in the system that is by design a person's answer.
    `by` cannot carry it: that names the implementation, and the implementation replaying a
    human's answer is still `replay`.

    Defaulted rather than required so nothing else changes shape. A resolver could set it
    untruthfully, which is the same standing as `confidence` and `why` — the port is a
    boundary against undeclared *shapes*, never against a component of ours lying in a
    declared one.
    """


class _Decided(BaseModel):
    """What every decision carries, whatever kind it is."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    key: DecisionKey
    subject: Subject
    """Still carried, because `kind` says *what sort* and this says *of what* — which
    contract's parameter, which type's producer. Redundant for two of three kinds; leaving
    it is the smaller change and `ReplayResolver` matches on `key`, which is unchanged."""
    reason: Line
    """Model- or resolver-written prose. Declared free text; see `ResolvedValue.reason`."""
    confidence: float = 0.0
    resolved_by: ResolverId
    tier: Tier = Tier.AMBIGUOUS


class ParamDecision(_Decided):
    """Which value a parameter takes. The one kind with no declared domain yet."""

    kind: Literal[DecisionKind.PARAM] = DecisionKind.PARAM
    candidates: list[ParamValue] = Field(default_factory=list)
    chosen: ParamValue
    human_override: HumanParamValue = None
    """A reviewer's answer, guarded against path-shaped values by a blocklist because a
    parameter has no declared domain to check against. Audit A3, and still a stopgap —
    the other two kinds no longer need one, which is the difference a type makes."""

    override_reason: Line = ""
    """Why the person answered it that way. **The field that did not exist.**

    Tier 4 is the honesty mechanism and the declared difference from a chat window, and it is
    the one tier where a *person* supplies the answer — with nowhere to say why. `why.reason`
    is re-derived from the resolver's `Resolution.reason` on every re-materialisation, so a
    hand-written sentence was replaced by *"selected the first of 1 candidates without
    judgement — please review"* under `source: human`, and `upgrade` reported "1 decisions
    replayed" without mentioning the loss. Audit A77.

    Empty means a person answered and gave no reason, which is legal and is said in those
    words rather than by falling back to the flag-only text — that text describes what
    happened *before* the person arrived, which is A111.
    """


class ProducerDecision(_Decided):
    """Which contract produces a type here."""

    kind: Literal[DecisionKind.PRODUCER] = DecisionKind.PRODUCER
    candidates: list[ContractId] = Field(default_factory=list)
    chosen: ContractId
    human_override: ContractId | None = None


class SourceDecision(_Decided):
    """Which upstream output feeds a consumer's port."""

    kind: Literal[DecisionKind.SOURCE] = DecisionKind.SOURCE
    candidates: list[EdgeRef] = Field(default_factory=list)
    chosen: EdgeRef
    human_override: EdgeRef | None = None


DecisionRecord = Annotated[
    ParamDecision | ProducerDecision | SourceDecision,
    Field(discriminator="kind"),
]
"""A decision, discriminated on `kind`.

A published bundle round-trips through this, so `kind` reaches the artifact: every record
in every bundle gains a field. Nothing is published yet, which makes that free now and
expensive later — the same argument that deleted `ShadowRecord` in Part B.
"""

"""What an authoring session is made of: modes, phases, blocks, proposals, and replies.

**This module holds no behaviour.** It is the vocabulary the browser, the service layer and the
model all read, and keeping it inert is what lets Task 3's state machine be pure and Task 8's
reducer be a switch rather than a pile of `if`s.

Three rules run through everything below, each written down because the alternative is what a
protocol drifts into:

1. **A state is named, never inferred from an absent field.** `pending` and `failed` are two
   members of one enum, not two nullable timestamps. A `None` meaning *not yet* and a `None`
   meaning *no* are the same value on the wire, and the reader cannot tell which was meant.
2. **Every interactive thing has a stable id, and the browser posts the id.** Not a copied
   contract, not a value — an id the engine issued. That is what makes "a model cannot produce
   a value outside the candidate set" checkable at the boundary instead of trusted afterwards.
3. **Prose is bounded and everything else is typed.** An unbounded string in a protocol becomes
   an unbounded string in a prompt.

The block vocabulary is `docs/superpowers/plans/2026-09-07-the-living-pipeline.md` §2. The
phases are that section's state diagram, and they are transcribed rather than invented so the
diagram stays the specification.
"""

from enum import StrEnum
from typing import Annotated, Literal, Self, get_args

from comeni_core.goal.asked import Goal
from comeni_core.spell.marks import ContractId, HumanParamValue, NodeId, OptionId, TypeId
from pydantic import BaseModel, ConfigDict, Field, model_validator

# **The Forge's number, not a new one.** `forge_jobs.CHAT_TAIL` bounds what a model is shown of
# a review conversation, and §2 says to follow that precedent until evaluation shows a different
# one is needed. It has not, so this is the same 6 — and it is a named constant in both places
# rather than a literal, so the day somebody measures a better number there is one edit here.
CHAT_TAIL = 6

# Long enough for a paragraph explaining a choice, short enough that nobody pastes a file into
# it. `comeni_ai.choice.WHY_LIMIT` bounds the same kind of string for the same reason.
PROSE_LIMIT = 2000

Prose = Annotated[str, Field(max_length=PROSE_LIMIT)]
"""Bounded human-readable text inside the protocol.

Deliberately **not** `comeni_core`'s `Text`: that alias marks a string as crossing an egress
door, and most of what is below never leaves this machine. A block rendered in the browser and a
string sent to a provider are different claims, and marking both the same way would make the
egress guard's allowlist meaningless by flooding it.
"""


class Mode(StrEnum):
    """How much the person is asked.

    **Two policies over one engine**, which is §1.2 and the reason this is an enum rather than
    two services. Spawn is not "Build with the questions skipped by a different code path" — it
    is the same proposal stream with every safe proposal auto-accepted and the declared tier-4
    resolver answering what remains. If the two ever need different engines, that is a design
    change and this enum is where it surfaces.
    """

    BUILD = "build"
    SPAWN = "spawn"


class Phase(StrEnum):
    """Where a session is in §2's diagram.

    Transcribed from that diagram rather than derived from what the code happens to need, so the
    picture stays the specification. `failed` is a phase and not a flag, because a session that
    failed to reach a provider must be able to retry *into a named place* — §2 draws two arrows
    out of it, back to `understanding` and to `resolving`.
    """

    UNDERSTANDING = "understanding"
    GOAL_REVIEW = "goal_review"
    RESOLVING = "resolving"
    BUILDING = "building"
    COMPLETE = "complete"
    FAILED = "failed"


class ProposalState(StrEnum):
    """What became of a proposal.

    **`stale` is the member that earns the enum.** A proposal made against revision 4 and
    answered after revision 5 landed was not rejected — nobody rejected it — and it is not
    pending, because applying it would write over work the person did in between. Without a name
    for that, the service layer has to encode it as "pending but the revision does not match",
    which is a rule living in whichever caller remembered it.
    """

    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    STALE = "stale"


class TurnState(StrEnum):
    """Whether an assistant turn has landed.

    A user turn appears immediately and its answer arrives later, so the transcript holds a turn
    that exists and has no content yet. Two booleans would make `pending and failed`
    representable; three members do not.
    """

    PENDING = "pending"
    ANSWERED = "answered"
    FAILED = "failed"


class BlockKind(StrEnum):
    """The eight things an assistant turn can contain (§2).

    The browser renders these with an exhaustive `switch`, so adding a member here fails
    TypeScript until it has a renderer — which is the intended order. A ninth kind is a design
    decision about what the conversation can say, not a formatting choice.
    """

    NARRATIVE = "narrative"
    GOAL_SUMMARY = "goal_summary"
    QUESTION = "question"
    STEP_PROPOSAL = "step_proposal"
    SETTING_REQUEST = "setting_request"
    CHANGE_SET = "change_set"
    RECEIPT = "receipt"
    NOTICE = "notice"


class NoticeKind(StrEnum):
    """What a `notice` is about.

    Closed, because these are the states the interface draws differently — a refusal is not a
    validation finding and neither is a completion. `REFUSAL` is where a provider's failure
    surfaces, and it carries a code rather than a provider's message for `GateFailure`'s reason.
    """

    PENDING = "pending"
    REFUSAL = "refusal"
    STALE = "stale"
    VALIDATION = "validation"
    COMPLETE = "complete"


class _Shape(BaseModel):
    """Closed and immutable, for `EgressPayload`'s reasons one layer up.

    `extra="forbid"` so a field cannot be added at runtime — the shape a reviewer read is the
    shape that travels. `frozen=True` so a block handed to the reducer cannot be edited into a
    different block by whoever holds it.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)


class Option(_Shape):
    """One answer a person may pick.

    `id` is what comes back. `label` is what a human reads and a model is shown, and it is
    **never** what is posted — that distinction is the whole mechanism: a value chosen by id
    cannot be a value nobody offered.
    """

    id: OptionId
    label: Prose
    note: Prose | None = None
    recommended: bool = False


class _Block(_Shape):
    """Every block has an id, because the next turn has to be able to refer to it."""

    id: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")


class Narrative(_Block):
    """Bounded prose, optionally naming steps that already exist."""

    kind: Literal[BlockKind.NARRATIVE] = BlockKind.NARRATIVE
    text: Prose
    refers_to: list[NodeId] = []


class GoalSummary(_Block):
    """The typed `Goal` beside the plain-language reading of it.

    Both, rather than either. The `Goal` is what the resolver runs on and the summary is what
    the person checks — and the point of the goal-review phase is that a person can catch a
    misunderstanding *before* a pipeline is built on it. A summary with no goal cannot be acted
    on; a goal with no summary cannot be checked by the person whose analysis it is.
    """

    kind: Literal[BlockKind.GOAL_SUMMARY] = BlockKind.GOAL_SUMMARY
    goal: Goal
    have: Prose
    do: Prose
    get: Prose


class Question(_Block):
    """One typed question with a closed set of answers, or a declared open one.

    `exhaustive` is the honest half. A closed list that is *not* exhaustive is a shortlist, and
    the interface has to say which it is showing — this is `comeni_core.review.Question`'s
    property, kept rather than re-derived.
    """

    kind: Literal[BlockKind.QUESTION] = BlockKind.QUESTION
    asks: Prose
    why_open: Prose
    options: list[Option] = []
    exhaustive: bool = True


class StepProposal(_Block):
    """A step the engine proposes, with what it would replace and why.

    `tier` is the resolution tier the choice exits at, so the interface can draw a settled step
    and an ambiguous one differently without asking a second question. `alternatives` are the
    other candidates as options — the ghost node the artboards draw on hover.
    """

    kind: Literal[BlockKind.STEP_PROPOSAL] = BlockKind.STEP_PROPOSAL
    node: NodeId
    contract: ContractId
    produces: list[TypeId] = []
    reason: Prose
    tier: int = Field(ge=1, le=4)
    alternatives: list[Option] = []


class SettingRequest(_Block):
    """A setting the engine cannot settle, with the premise it read.

    `premise` is separate from `reason` for the reason Plan 1.14 split `axis_reason` off
    `reason`: *why this question is being asked* and *why this answer would win* are two
    questions, and one field answering both is how a registry came to cite the STAR paper as the
    reason HISAT2 was chosen.
    """

    kind: Literal[BlockKind.SETTING_REQUEST] = BlockKind.SETTING_REQUEST
    node: NodeId
    setting: str = Field(min_length=1, max_length=128)
    current: Prose | None = None
    options: list[Option] = []
    reason: Prose
    premise: Prose | None = None


class ChangeSet(_Block):
    """Exactly what a conversational revision would touch, before it touches it.

    The list is the point. "I will switch the aligner" is a sentence; this is the set of nodes
    and settings that sentence turns out to mean, shown before the person accepts it.
    """

    kind: Literal[BlockKind.CHANGE_SET] = BlockKind.CHANGE_SET
    summary: Prose
    adds: list[NodeId] = []
    removes: list[NodeId] = []
    settings: list[str] = []


class Receipt(_Block):
    """What was committed, after the fact and immutably.

    A receipt is not a proposal that happened to be accepted — it is the record that something
    *was* applied, at a revision, by an actor. `by` distinguishes a person from the model for
    the reason `model_override` exists on all three decision kinds: a pipeline an agent
    assembled must not read as one a person drew by hand.
    """

    kind: Literal[BlockKind.RECEIPT] = BlockKind.RECEIPT
    summary: Prose
    revision: int = Field(ge=0)
    by: Literal["person", "model", "resolver"]


class Notice(_Block):
    """Pending, refusal, stale, validation or completion.

    `code` carries a diagnostic rather than a provider's sentence — `GateFailure`'s lesson, one
    level up: machine-generated text is the likeliest leak precisely because nobody wrote it and
    nobody reads it.
    """

    kind: Literal[BlockKind.NOTICE] = BlockKind.NOTICE
    notice: NoticeKind
    text: Prose
    code: str | None = Field(default=None, max_length=16)


Block = Annotated[
    Narrative
    | GoalSummary
    | Question
    | StepProposal
    | SettingRequest
    | ChangeSet
    | Receipt
    | Notice,
    Field(discriminator="kind"),
]
"""Every block, discriminated on `kind`.

A tagged union rather than one wide optional model: the browser's exhaustive switch and this
discriminator are the same claim made twice, in the two languages, and a kind that exists in one
and not the other fails rather than renders blank.
"""

BLOCK_TYPES: tuple[type[_Block], ...] = get_args(get_args(Block)[0])
"""The members of `Block`, enumerable at runtime.

**Derived, not retyped.** This was a hand-written tuple beside the union for one commit, which
is the pair-that-must-agree shape this repository keeps finding to be one mechanism and one
decoration — a block added to the union and forgotten here would leave every test that walks
this list quietly checking seven of eight kinds.
"""


class _Envelope(_Shape):
    """One parsed block, so a bare dict can be validated against the discriminated union."""

    block: Block


def parse_block(data: object) -> _Block:
    """Validate one block dict against the union, refusing an unknown `kind`.

    Wrapped rather than exposed as `TypeAdapter`, because the failure mode this closes is a
    caller reaching for `Narrative.model_validate` on data whose `kind` says otherwise — which
    succeeds, silently, by ignoring the discriminator.
    """
    return _Envelope.model_validate({"block": data}).block


# ── what a model may reply ────────────────────────────────────────────────────────────────


class AskedQuestion(_Shape):
    """A question the **model** raises, before the engine has minted ids for it.

    **Deliberately not a `Question`.** That one is a block with an `id` and `Option`s carrying
    ids, and those ids are the engine's to issue — rule 2 of this module. A model that named its
    own option ids would be authoring the set that its own next reply is checked against, which
    turns the boundary into a formality.

    So this carries labels, the engine mints the ids when it stores the question, and the next
    turn's `chose` is held to *those*.
    """

    asks: Prose
    why_open: Prose
    choices: list[Prose] = []
    exhaustive: bool = True
    """Whether `choices` is the whole of what is possible. A shortlist presented as a closed set
    is how a person comes to believe they were shown everything."""


class GoalUnderstanding(_Shape):
    """The first call's answer: prose in, a typed `Goal` out.

    **Separate from `AuthoringIntent` on purpose.** One shape covering both would have half its
    fields null on every call, which is precisely the configuration the Forge measured a local
    model doing worst on. The first call has no pipeline to talk about; a later one has nothing
    else to talk about.

    `have`/`do`/`get` are the plain-language reading the person checks the `Goal` against. The
    model writes both halves and the person is shown both, so a misunderstanding is visible at
    review time rather than after a build.
    """

    goal: Goal
    have: Prose
    do: Prose
    get: Prose
    questions: list[AskedQuestion] = []
    """What could not be settled from what the person said.

    **The grouping question needs somewhere to come back to.** §1.7 says *do not infer one
    silently*, and a reply shape with nowhere to put a question can only infer: it would force a
    `Goal` stating a sample structure nobody confirmed, and that goal validates, resolves and
    builds.
    """


class SettingProposal(_Shape):
    """A value the model proposes for an open setting.

    **The one place a model may produce a value rather than choose an id**, and it is bounded
    three ways rather than trusted: the step is a `NodeId`, the value is a `HumanParamValue` —
    audit A3's guard, which refuses a path-shaped value — and §1.3 requires the engine to
    validate it and, when consequential, to show it before applying.

    `chose` is here for the ordinary case where the engine already offered a closed set: naming
    the option is stronger than restating its value, and a proposal carrying both must agree.
    """

    node: NodeId
    setting: str = Field(min_length=1, max_length=128)
    chose: OptionId | None = None
    value: HumanParamValue | None = None
    because: Prose


class AuthoringIntent(_Shape):
    """A follow-up turn, reduced to exactly one intent.

    **One object with validated exclusive fields**, which is what Task 2 asks for over a nested
    union: the JSON schema stays one level deep, and a local model that cannot reliably pick a
    variant tag can still fill exactly one field.

    Exclusivity is validated rather than documented. A reply naming both a chosen option and a
    goal revision is a reply nobody can act on, and letting it through means the service layer
    resolves the ambiguity by field order — a rule that lives wherever somebody wrote it and is
    different in the next caller.

    There is nowhere here to put YAML, a graph, or a contract body. That is §1.3, and it is a
    property of the shape rather than a check performed on it: the model chooses among things
    the engine already named, or it says something in prose that re-enters the loop as a new
    goal — it never authors the artifact.
    """

    chose: OptionId | None = None
    """An option the engine offered, by id. An identifier, so prose and paths are refused."""

    revise: Prose | None = None
    """A goal revision in the person's own words. Re-enters `understanding`; it does not edit."""

    explain: Prose | None = None
    """A request for explanation. Mutates nothing, so it needs no revision and no proposal."""

    setting: SettingProposal | None = None
    """A value proposed for an open setting. Validated, and shown before it is applied."""

    proceed: bool = False
    """*Go on* — they are happy and want the next step. The one intent with no payload, and it
    still joins the exclusivity check below: *continue, and also revise the goal* is not a turn
    anybody can act on."""

    unsupported: Prose | None = None
    """What was asked is not something this conversation can do, and what would work instead.

    **The sixth intent exists so the other five stay honest.** Without somewhere to say *no*,
    the closest-looking alternative is always available — and a request to edit the registry
    arriving as a goal revision is worse than a refusal, because it looks like it worked.
    """

    refers_to: list[NodeId] = []
    """The steps an explanation is about, as ids the engine issued.

    Typed rather than parsed back out of the prose, which is what makes rejecting an invented
    reference a set difference instead of a regex over English.
    """

    @model_validator(mode="after")
    def _exactly_one(self) -> Self:
        """`refers_to` is deliberately outside the count: it qualifies an explanation rather
        than being an intent of its own, and including it would make a grounded explanation
        read as two intents at once."""
        intents = ("chose", "revise", "explain", "setting", "proceed", "unsupported")
        set_fields = [name for name in intents if getattr(self, name)]
        if len(set_fields) != 1:
            raise ValueError(
                f"an authoring intent carries exactly one of {'/'.join(intents)}, "
                f"not {set_fields or 'none'}"
            )
        return self


# ── what the browser posts ────────────────────────────────────────────────────────────────


class Say(_Shape):
    """A person saying something.

    **No `expected_revision`, and that is the point.** Saying something proposes no change, so
    it cannot conflict with one. Giving every message a revision would make a chat message a
    thing that can overwrite a draft, which is the confusion §2 separates by having two request
    types instead of one with a nullable field.
    """

    text: Prose


class AcceptProposal(_Shape):
    """Applying a proposal, against the revision the person was looking at.

    `expected_revision` is required rather than defaulted. A request that cannot say what it saw
    cannot be checked for staleness at all, and a default would mean "whatever is current",
    which is exactly the read-then-write race the field exists to close.
    """

    proposal_id: str = Field(min_length=1, max_length=64)
    expected_revision: int = Field(ge=0)


class RejectProposal(_Shape):
    """Declining a proposal. Carries a revision for `AcceptProposal`'s reason: rejecting a
    proposal the person can no longer see is as wrong as accepting one."""

    proposal_id: str = Field(min_length=1, max_length=64)
    expected_revision: int = Field(ge=0)
    because: Prose | None = None

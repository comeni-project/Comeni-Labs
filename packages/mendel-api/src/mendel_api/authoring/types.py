"""What a builder conversation is made of: turns, their blocks, and the facts it gathers.

**This module holds no behaviour.** It is the vocabulary the browser, the service layer and the
agent all read (#463).

Three rules run through everything below, each written down because the alternative is what a
protocol drifts into:

1. **A state is named, never inferred from an absent field.** `pending` and `failed` are two
   members of one enum, not two nullable timestamps.
2. **Every interactive thing has a stable id, and the browser posts the id.** That is what makes
   an answer outside the offered set checkable at the boundary instead of trusted afterwards.
3. **Prose is bounded and everything else is typed.** An unbounded string in a protocol becomes
   an unbounded string in a prompt.
"""

from enum import StrEnum
from typing import Annotated, Literal, Self, get_args

from comeni_core.spell.marks import HumanParamValue
from pydantic import BaseModel, ConfigDict, Field, model_validator

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


class TurnState(StrEnum):
    """Whether an assistant turn has landed.

    A user turn appears immediately and its answer arrives later, so the transcript holds a turn
    that exists and has no content yet. Two booleans would make `pending and failed`
    representable; three members do not.
    """

    PENDING = "pending"
    ANSWERED = "answered"
    FAILED = "failed"


class Purpose(StrEnum):
    """Which of the builder's calls an `ai_invocation` row records — one member per committed
    prompt id. Here rather than in `services.authoring_ai` (which re-exports it) so `models.py`
    can build its CHECK without an import cycle (issue 274).

    **Scoped by `agent`, not spelled to be globally unique.** The forge declares a `chat` purpose
    too, and `agent='builder' AND purpose='chat'` is what tells them apart, which is precisely
    what that column is for. Inventing `builder_chat` here would put the agent name in two
    columns and let them disagree.
    """

    GOAL = "goal"
    FAMILY = "family"
    CHAT = "chat"
    TIER4 = "tier4"
    AGENT = "agent"
    """The builder agent's loop (#463): every model call of an agent turn."""
    GAP = "gap"
    ASK = "ask"
    READBACK = "readback"
    CHARACTERISE_FAMILY = "characterise_family"
    CHARACTERISE = "characterise"


class TurnRole(StrEnum):
    """Who wrote a turn of the conversation, as stored (issue 274).

    `AuthoringRole` (door 5's payload) says person or *model*; the stored turn says assistant.
    They are different spellings for different places and stay apart.
    """

    PERSON = "person"
    ASSISTANT = "assistant"


class BlockKind(StrEnum):
    """What an agent turn can contain (#463): a notice, its words, a line per tool it called,
    and a question to the person.

    The browser renders these with an exhaustive `switch`, so adding a member here fails
    TypeScript until it has a renderer — which is the intended order.
    """

    NOTICE = "notice"
    MESSAGE = "message"
    TOOL = "tool"
    ASK = "ask"


class NoticeKind(StrEnum):
    """What a `notice` is about.

    `REFUSAL` is where a provider's failure
    surfaces, and it carries a code rather than a provider's message for `GateFailure`'s reason.
    """

    REFUSAL = "refusal"
    LIMIT = "limit"
    """The builder agent stopped at its step or token limit (#463)."""


class _Shape(BaseModel):
    """Closed and immutable, for `EgressPayload`'s reasons one layer up.

    `extra="forbid"` so a field cannot be added at runtime — the shape a reviewer read is the
    shape that travels. `frozen=True` so a block handed to the reducer cannot be edited into a
    different block by whoever holds it.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)


class FactKind(StrEnum):
    INPUT = "input"
    MEASUREMENT = "measurement"


class SampleFact(_Shape):
    """One fact measured on one uploaded sample (#466)."""

    measurement: str = Field(min_length=1, max_length=128)
    value: HumanParamValue | None = None
    coverage: Literal["head", "all"] | None = None


class UploadedSample(_Shape):
    """One sample of an upload, kept with the session: its name and files, and what was
    measured on it (#466). Session state only: a sample's name never reaches a goal, a
    pipeline, a model or a log (operator, 11-12)."""

    name: str = Field(min_length=1, max_length=256)
    files: list[str] = []
    outcome: str = Field(min_length=1, max_length=32)
    facts: list[SampleFact] = []


class FactSource(StrEnum):
    """Where a fact came from, which is what the goal card and the tier-3 premise show."""

    MEASURED = "measured"  # an inspector read the file (14.7.6)
    MODEL_READ = "model_read"  # the characteriser read it (14.7.7)
    PERSON_SAID = "person_said"  # the person stated it
    OPEN = "open"  # nobody knows; the tiers carry it as tier 4
    VARIES = "varies"  # the person said it differs between samples (#466)


class Fact(_Shape):
    """One thing gathering learned, and who it came from. Nothing is guessed (protocol rule 5)."""

    kind: FactKind
    subject: str = Field(min_length=1, max_length=128)
    """A type id for an input, a measurement id for a measurement."""
    value: HumanParamValue | list[HumanParamValue] | None = None
    states: list[str] = []
    source: FactSource
    sample: str | None = Field(default=None, max_length=64)
    pieces: list[str] = []
    """The inspector pieces that measured it, `fastq@1.0.0` then `read_length@1.0.0` (#134).
    Empty for anything a person said."""
    evidence: dict[str, int | float] | None = None
    """How much they read, counts only. Session state, not a door payload: the goal gets the
    typed `Evidence`, which holds only the counts it declares."""
    coverage: Literal["head", "all"] | None = None
    """How much of the data it was measured on (#465): `head` for part of it."""
    heard: Prose | None = None
    """The person's own words it was taken from, when a model heard it (Part I.0 §5.4): shown on
    the goal card so a misreading (*"not paired-end"*) is caught there. Session state only."""

    @model_validator(mode="after")
    def _open_has_no_value(self) -> Self:
        if self.source is FactSource.OPEN and self.value is not None:
            raise ValueError("an open fact has no value: nobody knows it")
        if self.source is FactSource.VARIES and self.value is not None:
            raise ValueError("a fact that differs between samples has no one value")
        return self


class Reason(_Shape):
    """One line of why a question is asked, and where it comes from (Part I.1)."""

    text: Prose
    detail: Prose | None = None
    """A tool's declared description, or a rule's citation."""


class Explanation(_Shape):
    """What a question is about and why it is asked: `what` is curated (the registry's
    `explain`), the rest the engine's, derived from the gap walk (Part I.1 §4). I.3 hands the same
    fields to the AI as its sources."""

    name: Prose
    what: Prose | None = None
    needed: list[Reason] = []
    reads: Literal["steps", "rule"] | None = None
    """How `needed` reads: the steps that can read an input, or the rule a measurement decides."""
    settles: list[Prose] = []
    """For an input: what a sample of it would answer, by name, among the questions still open."""
    read_by: Literal["inspector", "ai"] | None = None
    """Who would read a sample of it: an inspector, the AI, or nothing here."""
    files: int = 1
    """The most files one sample of it may be: 2 where a format reads it as a pair (issue
    328). The upload card says *both files if your reads are paired* only then."""


class _Block(_Shape):
    """Every block has an id, because the next turn has to be able to refer to it."""

    id: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")


class Notice(_Block):
    """A refusal, or the agent stopping at its limit.

    `code` carries a diagnostic rather than a provider's sentence — `GateFailure`'s lesson, one
    level up: machine-generated text is the likeliest leak precisely because nobody wrote it and
    nobody reads it.
    """

    kind: Literal[BlockKind.NOTICE] = BlockKind.NOTICE
    notice: NoticeKind
    text: Prose
    code: str | None = Field(default=None, max_length=16)


class AgentMessage(_Block):
    """What the builder agent says, in its own words (#463). `narration` is what it said beside a
    tool call, while working (#504): drawn with its trail, not as its answer."""

    kind: Literal[BlockKind.MESSAGE] = BlockKind.MESSAGE
    text: Annotated[str, Field(max_length=16000)]
    narration: bool = False


class ToolLine(_Block):
    """One tool the agent called: its name, a line a person reads, whether it worked, and the
    refusal when it did not (#463). `running` while the tool has not returned (#504): its label
    says what is happening now."""

    kind: Literal[BlockKind.TOOL] = BlockKind.TOOL
    name: str = Field(max_length=64)
    label: Prose
    ok: bool
    summary: Prose = ""
    running: bool = False
    node: str | None = Field(default=None, max_length=64)
    """The step the call read or changed, where it names one (#499): what an answer links to."""


class AgentAsk(_Block):
    """A question the agent put to the person, and how it is answered (#463)."""

    kind: Literal[BlockKind.ASK] = BlockKind.ASK
    question_id: str = Field(max_length=32)
    question: Prose
    shape: Literal["options", "number", "yes_no", "data", "text"]
    options: list[Prose] = []
    unit: str = Field(default="", max_length=20)
    type_id: str | None = Field(default=None, max_length=128)


Block = Annotated[
    Notice
    | AgentMessage
    | ToolLine
    | AgentAsk,
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
this list quietly skipping it.
"""


class _Envelope(_Shape):
    """One parsed block, so a bare dict can be validated against the discriminated union."""

    block: Block


def parse_block(data: object) -> _Block:
    """Validate one block dict against the union, refusing an unknown `kind`.

    Wrapped rather than exposed as `TypeAdapter`, because the failure mode this closes is a
    caller reaching for one member's `model_validate` on data whose `kind` says otherwise —
    which succeeds, silently, by ignoring the discriminator.
    """
    return _Envelope.model_validate({"block": data}).block

"""Typed commands submitted by people and background jobs to an authoring session.

Commands contain plain values so the authoring core has no dependency on API, database, queue, or
provider types. Each command's ``takes`` set declares which protocol arrows its recorder may use.
"""

from dataclasses import dataclass
from typing import ClassVar

from mendel_authoring.types import Command

_NONE: frozenset[Command] = frozenset()


@dataclass(frozen=True, slots=True)
class OpenSession:
    draft_id: str
    who: str
    takes: ClassVar[frozenset[Command]] = _NONE


@dataclass(frozen=True, slots=True)
class OpenDrawn:
    """A draft's conversation, opened with nothing said if it has none (one builder, #395)."""

    draft_id: str
    who: str
    takes: ClassVar[frozenset[Command]] = _NONE


@dataclass(frozen=True, slots=True)
class Begin:
    prompt: str
    who: str
    takes: ClassVar[frozenset[Command]] = frozenset({Command.DESCRIBE})


@dataclass(frozen=True, slots=True)
class Say:
    session_id: str
    text: str
    takes: ClassVar[frozenset[Command]] = frozenset({Command.DESCRIBE, Command.REPLY_IN_WORDS})


@dataclass(frozen=True, slots=True)
class AnswerTurn:
    session_id: str
    seq: int
    blocks: list
    base_revision: int
    invocation_id: str | None = None
    takes: ClassVar[frozenset[Command]] = _NONE


@dataclass(frozen=True, slots=True)
class Understood:
    """The model read the person's words: `reading` is a `payloads.GoalReturned` dump."""

    session_id: str
    reading: dict
    takes: ClassVar[frozenset[Command]] = frozenset({Command.UNDERSTOOD})


@dataclass(frozen=True, slots=True)
class AskedBack:
    session_id: str
    takes: ClassVar[frozenset[Command]] = frozenset({Command.ASKED_BACK})


@dataclass(frozen=True, slots=True)
class ProviderFailed:
    session_id: str
    takes: ClassVar[frozenset[Command]] = frozenset({Command.PROVIDER_FAILED})


@dataclass(frozen=True, slots=True)
class Retry:
    session_id: str
    takes: ClassVar[frozenset[Command]] = frozenset({Command.RETRY})


@dataclass(frozen=True, slots=True)
class DecideGoal:
    proposal_id: str
    decision: str
    expected_revision: int
    by: str
    edited: dict | None = None
    takes: ClassVar[frozenset[Command]] = frozenset({Command.CONFIRM_GOAL, Command.REVISE_GOAL})


@dataclass(frozen=True, slots=True)
class Revised:
    session_id: str
    by: str
    takes: ClassVar[frozenset[Command]] = frozenset({Command.REVISED})


@dataclass(frozen=True, slots=True)
class StoreReadback:
    session_id: str
    text: str
    stamp: tuple[int, str] | None
    takes: ClassVar[frozenset[Command]] = _NONE


@dataclass(frozen=True, slots=True)
class ReadbackFailed:
    session_id: str
    stamp: tuple[int, str] | None
    takes: ClassVar[frozenset[Command]] = _NONE


@dataclass(frozen=True, slots=True)
class Resume:
    session_id: str
    takes: ClassVar[frozenset[Command]] = _NONE


@dataclass(frozen=True, slots=True)
class AnswerGap:
    proposal_id: str
    option: str
    value: object
    by: str
    takes: ClassVar[frozenset[Command]] = frozenset({Command.ANSWER_GAP})


@dataclass(frozen=True, slots=True)
class PrefillGap:
    proposal_id: str
    option: str
    value: object
    note: str
    takes: ClassVar[frozenset[Command]] = _NONE


@dataclass(frozen=True, slots=True)
class StorePhrasing:
    session_id: str
    subject: str
    asked: dict
    stamp: tuple[int, str] | None
    takes: ClassVar[frozenset[Command]] = _NONE


@dataclass(frozen=True, slots=True)
class PhrasingFailed:
    session_id: str
    subject: str
    stamp: tuple[int, str] | None
    takes: ClassVar[frozenset[Command]] = _NONE


@dataclass(frozen=True, slots=True)
class UploadSample:
    session_id: str
    proposal_id: str
    files: tuple
    """`((name, head bytes), ...)`: one file, or a pair."""
    by: str
    takes: ClassVar[frozenset[Command]] = frozenset(
        {Command.UPLOAD_SAMPLE, Command.COMPARE_EVIDENCE}
    )


@dataclass(frozen=True, slots=True)
class SampleInspected:
    proposal_id: str
    inspection: dict
    by: str
    expected_decision_revision: int | None = None
    expected_session_version: int | None = None
    takes: ClassVar[frozenset[Command]] = frozenset(
        {Command.UPLOAD_SAMPLE, Command.COMPARE_EVIDENCE}
    )


@dataclass(frozen=True, slots=True)
class ReadingAnswered:
    proposal_id: str
    attempt: int
    reply: dict
    by: str
    handed_back: bool
    invocation_id: str | None = None
    expected_decision_revision: int | None = None
    expected_session_version: int | None = None
    takes: ClassVar[frozenset[Command]] = frozenset(
        {Command.UPLOAD_SAMPLE, Command.COMPARE_EVIDENCE}
    )


@dataclass(frozen=True, slots=True)
class ReadingFailed:
    proposal_id: str
    attempt: int
    state: str
    code: str | None
    takes: ClassVar[frozenset[Command]] = _NONE


@dataclass(frozen=True, slots=True)
class StartBuilding:
    session_id: str
    takes: ClassVar[frozenset[Command]] = _NONE


@dataclass(frozen=True, slots=True)
class SettleStep:
    """*Continue*: keep this step as the blueprint has it (spec §14.5)."""

    proposal_id: str
    expected_revision: int
    by: str
    takes: ClassVar[frozenset[Command]] = frozenset({Command.CONTINUE})


@dataclass(frozen=True, slots=True)
class Amend:
    """One of the amendments a step's card offered, **by id** — `alt_N` for a tool, `fact_<m>`
    for a fact with its `value` — so nothing outside the offered set can be sent (spec §14.5);
    the door part 4's model will use too. A card offered against a registry that has since moved
    is re-offered instead, which is *continue*'s arrow."""

    proposal_id: str
    option: str
    value: object | None
    by: str
    expected_decision_revision: int | None = None
    expected_draft_revision: int | None = None
    expected_session_version: int | None = None
    takes: ClassVar[frozenset[Command]] = frozenset(
        {Command.AMEND, Command.CONTINUE, Command.CORRECT_FACT}
    )


@dataclass(frozen=True, slots=True)
class ChoosePacing:
    proposal_id: str
    option: str
    by: str
    takes: ClassVar[frozenset[Command]] = frozenset({Command.CHOOSE_PACING})


@dataclass(frozen=True, slots=True)
class RecordEdit:
    session_id: str
    graph: dict
    by: str
    expected_revision: int | None = None
    takes: ClassVar[frozenset[Command]] = _NONE


@dataclass(frozen=True, slots=True)
class CorrectFact:
    session_id: str
    subject: str
    value: object | None
    by: str
    expected_decision_revision: int
    expected_draft_revision: int
    expected_session_version: int
    kind: str = "measurement"
    takes: ClassVar[frozenset[Command]] = frozenset({Command.CORRECT_FACT})


@dataclass(frozen=True, slots=True)
class AnswerDisagreement:
    proposal_id: str
    option: str
    value: object | None
    by: str
    expected_decision_revision: int
    expected_draft_revision: int
    expected_session_version: int
    takes: ClassVar[frozenset[Command]] = frozenset(
        {Command.ANSWER_DISAGREEMENT}
    )


@dataclass(frozen=True, slots=True)
class ReleaseProducer:
    session_id: str
    type_id: str
    states: tuple[str, ...]
    by: str
    expected_decision_revision: int
    expected_draft_revision: int
    expected_session_version: int
    takes: ClassVar[frozenset[Command]] = frozenset(
        {Command.RELEASE_PRODUCER}
    )


@dataclass(frozen=True, slots=True)
class Change:
    """Any change to intent or facts, from anyone (Part I.0 spec §5.1): `change` is a
    `payloads.DecisionChange` dump. It takes the correction section's arrows, so it is offered
    exactly where a correction is — at a waiting node, never during async work."""

    session_id: str
    change: dict
    by: str
    expected_decision_revision: int
    expected_draft_revision: int
    expected_session_version: int
    takes: ClassVar[frozenset[Command]] = frozenset({Command.CORRECT_FACT})


COMMANDS: tuple[type, ...] = (
    OpenSession,
    OpenDrawn,
    Begin,
    Say,
    AnswerTurn,
    Understood,
    AskedBack,
    ProviderFailed,
    Retry,
    DecideGoal,
    Revised,
    StoreReadback,
    ReadbackFailed,
    Resume,
    AnswerGap,
    PrefillGap,
    StorePhrasing,
    PhrasingFailed,
    UploadSample,
    SampleInspected,
    ReadingAnswered,
    ReadingFailed,
    StartBuilding,
    SettleStep,
    Amend,
    ChoosePacing,
    RecordEdit,
    CorrectFact,
    Change,
    AnswerDisagreement,
    ReleaseProducer,
)

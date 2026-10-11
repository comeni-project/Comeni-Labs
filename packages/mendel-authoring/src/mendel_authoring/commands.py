"""What a person or a job does to an authoring session, typed (spec §11.3 of the consultant
build). **Plain values only**, so the core holds no shell type: a goal edited on the card is its
JSON, a sample's files are bytes, a model's reply its dump. The shell's recorder for each
(`mendel_api.services.session.records`) validates what it needs.

`takes` names the arrows of the diagram a command's recorder may take; the binding test holds a
recorder to it. Field order matches the parameters of the function each replaces, which is what
let the tests' call sites be rewritten by a script (plan 1c, Task 10)."""

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
    session_id: str
    goal: dict
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
        {Command.UPLOAD_SAMPLE, Command.COMPARE_EVIDENCE})


@dataclass(frozen=True, slots=True)
class SampleInspected:
    proposal_id: str
    inspection: dict
    by: str
    expected_decision_revision: int | None = None
    expected_session_version: int | None = None
    takes: ClassVar[frozenset[Command]] = frozenset(
        {Command.UPLOAD_SAMPLE, Command.COMPARE_EVIDENCE})


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
        {Command.UPLOAD_SAMPLE, Command.COMPARE_EVIDENCE})


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
        {Command.AMEND, Command.CONTINUE, Command.CORRECT_FACT})


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
    takes: ClassVar[frozenset[Command]] = frozenset({Command.ANSWER_DISAGREEMENT})


@dataclass(frozen=True, slots=True)
class ReleaseProducer:
    session_id: str
    type_id: str
    states: tuple[str, ...]
    by: str
    expected_decision_revision: int
    expected_draft_revision: int
    expected_session_version: int
    takes: ClassVar[frozenset[Command]] = frozenset({Command.RELEASE_PRODUCER})


@dataclass(frozen=True, slots=True)
class ForkCorrection(CorrectFact):
    takes: ClassVar[frozenset[Command]] = frozenset({Command.FORK_CORRECTION})


COMMANDS: tuple[type, ...] = (
    OpenSession, Begin, Say, AnswerTurn, Understood, AskedBack, ProviderFailed, Retry,
    DecideGoal, Revised, StoreReadback, ReadbackFailed,
    Resume, AnswerGap, PrefillGap, StorePhrasing, PhrasingFailed,
    UploadSample, SampleInspected, ReadingAnswered, ReadingFailed,
    StartBuilding, SettleStep, Amend, ChoosePacing, RecordEdit,
    CorrectFact, AnswerDisagreement, ReleaseProducer, ForkCorrection,
)

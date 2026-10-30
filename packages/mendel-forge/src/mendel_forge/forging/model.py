"""What an adaptation is made of: pieces, items, and every revision of each (spec §2).

**Append-only.** An item's history is its list of revisions, decisions included; nothing is
overwritten, so what the AI proposed stays visible beside what the person decided.

Pure data; `rules.apply` is the only thing that moves it.
"""

import re
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, JsonValue


class Piece(StrEnum):
    """In order: a piece is drafted only once the one before it is approved."""

    QUESTIONS = "questions"
    CONTRACT = "contract"
    PARAMETERS = "parameters"
    VOCABULARY = "vocabulary"
    RULES = "rules"
    TESTS = "tests"


PIECES: tuple[Piece, ...] = tuple(Piece)


class Actor(StrEnum):
    AI = "ai"
    PERSON = "person"
    REGISTRY = "registry"
    """A re-forge's starting values, from the registry's current contract: proposals like the
    AI's, never decisions."""


class Move(StrEnum):
    # Proposals (the AI's, or the registry's on a re-forge): they wait for a person.
    DRAFT = "draft"
    REVISE = "revise"
    ADD = "add"
    PROPOSE_REMOVAL = "propose_removal"
    # Decisions: only a person issues them, and they count at once.
    ANSWER = "answer"
    WRITE = "write"
    APPROVE = "approve"
    CHANGE = "change"
    REJECT = "reject"
    REMOVE = "remove"


PROPOSALS = frozenset({Move.DRAFT, Move.REVISE, Move.ADD, Move.PROPOSE_REMOVAL})
DECISIONS = frozenset(Move) - PROPOSALS
VALUE_MOVES = frozenset({Move.DRAFT, Move.REVISE, Move.ADD, Move.ANSWER, Move.WRITE, Move.CHANGE})
"""The moves that carry a value; an item's value is its latest one. A REJECT that restores an
approved value carries that value too."""


_DECIDING = frozenset({Move.WRITE, Move.CHANGE, Move.ANSWER})


class Status(StrEnum):
    PROPOSED = "proposed"
    APPROVED = "approved"
    REJECTED = "rejected"
    REMOVED = "removed"
    REOPENED = "reopened"
    """Was approved; something it depends on changed. Keeps its value, needs approval again."""


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class Revision(_Frozen):
    n: int
    """1, 2, …: the item's revision number. A command names the one it was issued against."""
    move: Move
    actor: Actor
    value: JsonValue = None
    because: str | None = None
    invocation: str | None = None
    """The model call that produced it, if any (`ai_invocation.id`)."""
    by: str | None = None
    """Who, for a person's move."""


class Item(_Frozen):
    key: str
    """`<piece>:<kind>:<name>`, e.g. `contract:port:reads`, `rules:rule:alignment`."""
    piece: Piece
    revisions: tuple[Revision, ...]
    status: Status

    @property
    def current(self) -> Revision:
        return self.revisions[-1]

    @property
    def value(self) -> JsonValue:
        return next((r.value for r in reversed(self.revisions)
                     if r.move in VALUE_MOVES or (r.move is Move.REJECT and r.value is not None)),
                    None)

    @property
    def decided(self) -> JsonValue:
        """The value as last decided: what a rejected proposal falls back to."""
        decided, pending = None, None
        for r in self.revisions:
            if r.move in PROPOSALS:
                pending = r.value
            elif r.move is Move.APPROVE:
                decided = pending
            elif r.move in _DECIDING or (r.move is Move.REJECT and r.value is not None):
                decided = r.value
        return decided

    @property
    def was_approved(self) -> bool:
        """Whether a decision ever made this item count (what re-opening hangs on)."""
        return any(r.move in {Move.APPROVE, Move.WRITE, Move.ANSWER, Move.CHANGE}
                   for r in self.revisions)


class Adaptation(_Frozen):
    items: dict[str, Item] = {}
    depends_on: tuple[str, ...] = ()


class Command(_Frozen):
    move: Move
    actor: Actor
    item: str
    expected: int | None = None
    """The revision number this was issued against; a stale one is refused."""
    value: JsonValue = None
    because: str | None = None
    invocation: str | None = None
    by: str | None = None


KEY = re.compile(
    r"^(questions|contract|parameters|vocabulary|rules|tests):"
    r"[a-z_]+(:[A-Za-z][A-Za-z0-9._-]{0,120})?$"
)
"""Every item key: `<piece>:<kind>[:<name>]`. A key names a file in the draft layer, so nothing
outside this grammar (a `/`, a `..`, a space) is ever accepted."""


def piece_of(key: str) -> Piece:
    return Piece(key.split(":", 1)[0])

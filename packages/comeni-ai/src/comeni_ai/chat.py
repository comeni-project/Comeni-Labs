"""A multi-turn exchange, validated the same way a single answer is.

**`converse` is `generate` with a history, and that is the whole design.** The boundary this
package holds is *nothing a model says is taken on trust*; a conversation does not weaken it,
so the answer is still validated against a shape the caller declared before any caller sees
it. A chat method returning free prose would be the one call in this package that skipped the
check, and it would be the call people reached for.

**The envelope is provider-neutral and holds no domain types.** `Turn` is a role and some
text. What a *useful* answer looks like — which evidence it cited, what it could not answer —
is the caller's shape, because those are the caller's concepts. The Forge declares its own;
this module would be the start of a shared pile if it declared one for it.

**History is the caller's to bound.** Nothing here trims, summarises or drops a turn: a
transport that silently discarded the middle of a conversation would make an answer
unexplainable from the record, and the record is what review reads. A caller that has more
history than it can afford decides *which* turns to drop and says so.
"""

from enum import StrEnum

from pydantic import BaseModel, ConfigDict

from comeni_ai.client import Client

__all__ = ["Role", "Turn", "converse"]


class Role(StrEnum):
    """Who said a turn. Closed, because a provider that invents a fourth is a provider
    speaking a dialect this package should refuse rather than pass through."""

    USER = "user"
    ASSISTANT = "assistant"


class Turn(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    role: Role
    text: str


def _transcript(history: list[Turn]) -> str:
    """The conversation, labelled, oldest first.

    **Flattened into one prompt rather than sent as a provider message array.** Invariant 13
    says a local model must work identically, and multi-turn message handling is exactly where
    providers differ — one that silently reorders or drops a system turn would give the local
    lane a different conversation from the hosted one for the same input. One prompt is one
    thing to record, one digest to compare, and one shape to replay from a fixture.
    """
    return "\n\n".join(f"{turn.role.value}: {turn.text}" for turn in history)


def converse[T: BaseModel](
    client: Client,
    history: list[Turn],
    question: str,
    shape: type[T],
    evidence: list[str],
) -> T | None:
    """Ask `question` with `history` behind it. `None` when the model declines or misfits.

    `history` is the bounded tail the caller chose, oldest first, and excludes `question`.

    **Takes a `Client`, like `choose_one` does.** Why the answer was declined is read off
    `client.last_refusal`, so a caller reporting a refusal reads one place whichever helper it
    used. An earlier draft took a `ModelAccess` and stashed refusals in a module-level map
    keyed by `id()` — which CPython reuses once the object is collected, so a later call could
    read a refusal belonging to a different, dead conversation.
    """
    prior = _transcript(history)
    instruction = f"The conversation so far:\n\n{prior}\n\n{question}" if prior else question
    return client.generate(instruction, shape, evidence)

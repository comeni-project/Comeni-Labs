"""Provider-neutral conversation helpers with validated replies.

Conversation history is flattened into a prompt and sent through :meth:`Client.generate`, so
the caller's reply model remains the admission boundary. Callers own history limits and domain
reply types; this module neither trims turns nor introduces domain-specific envelopes.
"""

from enum import StrEnum

from pydantic import BaseModel, ConfigDict

from comeni_ai.client import Client

__all__ = ["Role", "Turn", "converse"]


class Role(StrEnum):
    """Supported speakers in a conversation transcript."""

    USER = "user"
    ASSISTANT = "assistant"


class Turn(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    role: Role
    text: str


def _transcript(history: list[Turn]) -> str:
    """Return labelled turns, oldest first, as one provider-neutral prompt."""
    return "\n\n".join(f"{turn.role.value}: {turn.text}" for turn in history)


def converse[T: BaseModel](
    client: Client,
    history: list[Turn],
    question: str,
    shape: type[T],
    evidence: list[str],
) -> T | None:
    """Ask ``question`` after ``history`` and validate the reply as ``shape``.

    ``history`` is the caller-selected bounded tail, ordered oldest first and excluding the new
    question. Returns ``None`` on transport refusal or validation failure; details remain on
    ``client.last_refusal``.
    """
    prior = _transcript(history)
    instruction = f"The conversation so far:\n\n{prior}\n\n{question}" if prior else question
    return client.generate(instruction, shape, evidence)

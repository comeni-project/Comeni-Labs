"""The review conversation: a curator's turn in, a model's turn back.

**A message is stored before anything is queued, and that ordering is the product decision.**
§7: *the pending message is visible immediately*. A curator who types a question and sees
nothing until a model answers cannot tell *sent* from *lost*, and at 227 seconds they will
retype it. The row is the receipt.

**Nothing here moves an adaptation.** A conversation about a candidate does not change where the
candidate is in its lifecycle, and a chat that could move one would be a chat that can approve
one. That is also what makes it safe to ask a question while a generation is running.
"""

from datetime import UTC, datetime

from comeni_core.diagnostics import coded
from mendel_forge.ai.schemas import Citation
from mendel_forge.workflow import MessageRole, MessageState
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select

from mendel_api.db import session_scope
from mendel_api.models import ForgeAdaptation, ForgeMessage

_FROZEN = ConfigDict(extra="forbid", frozen=True)

MAX_MESSAGE = 4000
"""How long a curator's question may be.

A limit rather than none, because this string crosses **egress door 5** and an unbounded field
is one somebody eventually pastes a file into. Four thousand characters is several paragraphs of
genuine review and well under any provider's limit, so it never truncates a real question.
"""


class Turn(BaseModel):
    """One message, as a page renders it."""

    model_config = _FROZEN

    id: int
    role: MessageRole
    state: MessageState
    content: str
    citations: tuple[Citation, ...] = ()
    """**Typed, so the page can make each one clickable.** It was a bare `list`, which reaches
    the generated client as `unknown[]` — and §5.8's whole argument for an envelope rather than
    prose is that a claim resting on a source fact and one resting on a model proposal must be
    told apart by a reader. An untyped list puts that distinction where nothing can read it."""
    revision_id: str | None = None
    at: datetime


def conversation(adaptation_id: str) -> tuple[Turn, ...]:
    """Every turn, oldest first. **The whole thread, not a tail.**

    The bound in `forge_jobs.CHAT_TAIL` is about what a *model* is shown, and it exists so the
    record does not get pushed out of the context window. A person reading the page wants the
    conversation they had, and truncating it would hide the question whose answer they are
    looking at.
    """
    with session_scope() as session:
        rows = session.scalars(
            select(ForgeMessage)
            .where(ForgeMessage.adaptation_id == adaptation_id)
            .order_by(ForgeMessage.id)
        ).all()
        return tuple(
            Turn(
                id=row.id,
                role=MessageRole(row.role),
                state=MessageState(row.state),
                content=row.content,
                citations=row.citations,
                revision_id=row.revision_id,
                at=row.at,
            )
            for row in rows
        )


def ask(adaptation_id: str, *, message: str) -> Turn:
    """Store a curator's question as `pending`, grounded on the current revision.

    **Grounded at the moment of asking, not at the moment of answering.** A revision that lands
    while the question sits in the queue would otherwise re-ground it, and the answer would be
    about a candidate the curator never saw — which is §5.8's whole argument for pinning to a
    revision in the first place.
    """
    text = message.strip()
    if not text:
        raise ValueError(
            coded("MI0112", "a review question needs something in it")
            + "\n  an empty turn costs a model call and tells the next reader nothing"
        )
    if len(text) > MAX_MESSAGE:
        raise ValueError(
            coded("MI0112", f"a review question is at most {MAX_MESSAGE} characters")
            + f"\n  this one is {len(text)}; quote the part you are asking about"
        )

    with session_scope() as session:
        adaptation = session.get(ForgeAdaptation, adaptation_id)
        if adaptation is None:
            raise KeyError(adaptation_id)
        row = ForgeMessage(
            adaptation_id=adaptation_id,
            revision_id=adaptation.current_revision_id,
            role=MessageRole.CURATOR.value,
            state=MessageState.PENDING.value,
            content=text,
            citations=[],
            at=datetime.now(UTC),
        )
        session.add(row)
        session.flush()
        return Turn(
            id=row.id,
            role=MessageRole.CURATOR,
            state=MessageState.PENDING,
            content=row.content,
            citations=[],
            revision_id=row.revision_id,
            at=row.at,
        )

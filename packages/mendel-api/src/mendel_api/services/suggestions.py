"""The model's suggestions: offered, applied by one click as the person's own change, or set
aside (Part I.0 spec §5.3).

A suggestion is a change the model handed over that the engine would not record on its own —
it did not quote the person, or the goal was already confirmed, when every change is shown
before it moves anything. Applying one performs `c.Change` as the person; a later change to the
same subject makes it stale, because it was offered against a picture that moved."""

from dataclasses import dataclass
from datetime import UTC, datetime
from secrets import token_hex

from comeni_core.diagnostics import coded
from mendel_authoring import commands as c
from mendel_authoring.payloads import DecisionChange
from sqlalchemy import select

from mendel_api.db import session_scope
from mendel_api.models import (
    PipelineAuthoringSession,
    PipelineAuthoringSuggestion,
    PipelineDraft,
    SuggestionState,
)


@dataclass(frozen=True)
class SuggestionView:
    id: str
    change: DecisionChange
    heard: bool
    says: str


def offer(
    session_id: str, change: DecisionChange, *, heard: bool, invocation_id: str | None
) -> str:
    with session_scope() as db:
        suggestion_id = token_hex(16)
        db.add(
            PipelineAuthoringSuggestion(
                id=suggestion_id,
                session_id=session_id,
                change=change.model_dump(mode="json"),
                heard=heard,
                state=SuggestionState.PENDING.value,
                invocation_id=invocation_id,
                created_at=datetime.now(UTC),
            )
        )
        db.flush()
        return suggestion_id


def pending(session_id: str) -> list[SuggestionView]:
    from mendel_api.services import changes

    with session_scope() as db:
        rows = db.scalars(
            select(PipelineAuthoringSuggestion)
            .where(
                PipelineAuthoringSuggestion.session_id == session_id,
                PipelineAuthoringSuggestion.state == SuggestionState.PENDING.value,
            )
            .order_by(PipelineAuthoringSuggestion.created_at)
        ).all()
        found = [(row.id, DecisionChange.model_validate(row.change), row.heard) for row in rows]
    return [
        SuggestionView(id=i, change=ch, heard=h, says=changes.describe(ch)) for i, ch, h in found
    ]


def state(suggestion_id: str) -> str:
    with session_scope() as db:
        return db.get(PipelineAuthoringSuggestion, suggestion_id).state


def _settle(db, row, to: SuggestionState) -> None:
    row.state = to.value
    row.settled_at = datetime.now(UTC)


def _pending_row(db, session_id: str, suggestion_id: str):
    row = db.get(PipelineAuthoringSuggestion, suggestion_id, with_for_update=True)
    if row is None or row.session_id != session_id:
        raise KeyError(suggestion_id)
    if row.state != SuggestionState.PENDING.value:
        raise ValueError(
            coded(
                "MI0201",
                "this suggestion was offered against answers that "
                "have changed since; read them again",
            )
        )
    return row


def apply(session_id: str, suggestion_id: str, *, by: str) -> dict:
    """The person takes the suggestion: its change, performed as theirs."""
    from mendel_api.services import session

    with session_scope() as db:
        row = _pending_row(db, session_id, suggestion_id)
        change = DecisionChange.model_validate(row.change).model_copy(update={"actor": "person"})
        sess = db.get(PipelineAuthoringSession, session_id)
        draft = db.get(PipelineDraft, sess.draft_id)
        versions = (draft.decision_revision, draft.revision, sess.row_version)
    result = session.perform(
        c.Change(session_id, change.model_dump(mode="json"), by, *versions)
    ).result
    with session_scope() as db:
        _settle(db, db.get(PipelineAuthoringSuggestion, suggestion_id), SuggestionState.APPLIED)
    return result


def mark_applied(suggestion_id: str) -> None:
    """Applied by another path (an edited goal card that kept it)."""
    with session_scope() as db:
        _settle(db, db.get(PipelineAuthoringSuggestion, suggestion_id), SuggestionState.APPLIED)


def dismiss(session_id: str, suggestion_id: str, *, by: str) -> None:
    with session_scope() as db:
        _settle(db, _pending_row(db, session_id, suggestion_id), SuggestionState.DISMISSED)


def stale_for(draft_id: str, change: DecisionChange) -> None:
    """A change was recorded: every waiting suggestion about the same subject, in any session of
    the draft, was offered against what it replaced."""
    with session_scope() as db:
        sessions = select(PipelineAuthoringSession.id).where(
            PipelineAuthoringSession.draft_id == draft_id
        )
        for row in db.scalars(
            select(PipelineAuthoringSuggestion).where(
                PipelineAuthoringSuggestion.session_id.in_(sessions),
                PipelineAuthoringSuggestion.state == SuggestionState.PENDING.value,
            )
        ):
            offered = DecisionChange.model_validate(row.change)
            if (offered.kind, offered.subject) == (change.kind, change.subject):
                _settle(db, row, SuggestionState.STALE)

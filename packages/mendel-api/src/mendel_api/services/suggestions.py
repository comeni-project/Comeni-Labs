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
    measured: object = None
    """The measured value a stated one contradicts (#345): the card asks *are you sure?*, and
    *yes* records what the person said."""
    edit: str | None = None
    """The hand edit this reading came from; every reading of one edit is taken together."""


def measured_against(draft_id: str, change: DecisionChange):
    """The value the sample measured for this subject, when the change states another (#345).

    A person may know better than an inspector, but a contradiction of the sample is asked
    about once before it is followed, never recorded on a model's reading alone."""
    from mendel_api.authoring.types import FactKind, FactSource
    from mendel_api.services import authoring_decisions

    if change.kind != "measurement" or change.retract:
        return None
    return next((fact.value for fact in authoring_decisions.facts(draft_id)
                 if fact.kind is FactKind.MEASUREMENT and fact.subject == change.subject
                 and fact.source is FactSource.MEASURED and fact.value != change.value), None)


def unchanged(draft_id: str, change: DecisionChange) -> bool:
    """The record already says this, so there is nothing to offer. Walk 3's model listed the
    known want and inputs again beside the one fact it was told, and each became a card."""
    from mendel_api.services import decisions

    if change.retract:
        return False
    current = decisions.read(draft_id)

    def same_states(states) -> bool:
        return not change.states or sorted(change.states) == sorted(states)

    if change.kind == "want":
        return any(w.present and w.type_id == change.subject and same_states(w.states)
                   for w in current.wants)
    if change.kind == "input" and change.value is not False:
        return any(i.present and i.type_id == change.subject and same_states(i.states)
                   for i in current.inputs)
    if change.kind == "measurement":
        return any(f.subject == change.subject and f.value == change.value
                   for f in current.facts)
    return False


def _says(change: DecisionChange, measured) -> str:
    from mendel_api.services import changes

    if measured is None:
        return changes.describe(change)
    label = change.subject.replace("_", " ")
    return f"Are you sure the {label} is {change.value}? Your sample measured {measured}."


def offer(
    session_id: str, change: DecisionChange, *, heard: bool, invocation_id: str | None,
    edit: str | None = None, says: str | None = None,
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
                edit=edit,
                says=says,
                created_at=datetime.now(UTC),
            )
        )
        db.flush()
        return suggestion_id


def offer_edit(session_id: str, readings) -> list[str]:
    """Every reading of one hand edit, offered as one group in the order read, worded by the
    engine. A waiting reading about the same subject was read from an edit this one replaces,
    so its whole group goes stale: two readings of one thing are never both applied."""
    edit = token_hex(16)
    subjects = {reading.change().subject for reading in readings}
    with session_scope() as db:
        older = {row.edit for row in _pending_edits(db, session_id)
                 if DecisionChange.model_validate(row.change).subject in subjects}
        for row in _pending_edits(db, session_id):
            if row.edit in older:
                _settle(db, row, SuggestionState.STALE)
    return [offer(session_id, reading.change(), heard=False, invocation_id=None, edit=edit,
                  says=reading.said) for reading in readings]


def _pending_edits(db, session_id: str):
    return db.scalars(select(PipelineAuthoringSuggestion).where(
        PipelineAuthoringSuggestion.session_id == session_id,
        PipelineAuthoringSuggestion.state == SuggestionState.PENDING.value,
        PipelineAuthoringSuggestion.edit.is_not(None),
    ).with_for_update()).all()


def _group(db, session_id: str, suggestion_id: str) -> list[str]:
    """The suggestion and, for a reading, the rest of its edit, in the order offered."""
    row = db.get(PipelineAuthoringSuggestion, suggestion_id)
    if row is None or row.session_id != session_id or row.edit is None:
        return [suggestion_id]
    return list(db.scalars(select(PipelineAuthoringSuggestion.id).where(
        PipelineAuthoringSuggestion.edit == row.edit,
        PipelineAuthoringSuggestion.state == SuggestionState.PENDING.value,
    ).order_by(PipelineAuthoringSuggestion.created_at)))


def pending(session_id: str) -> list[SuggestionView]:
    with session_scope() as db:
        draft_id = db.get(PipelineAuthoringSession, session_id).draft_id
        rows = db.scalars(
            select(PipelineAuthoringSuggestion)
            .where(
                PipelineAuthoringSuggestion.session_id == session_id,
                PipelineAuthoringSuggestion.state == SuggestionState.PENDING.value,
            )
            .order_by(PipelineAuthoringSuggestion.created_at)
        ).all()
        found = [(row.id, DecisionChange.model_validate(row.change), row.heard, row.edit,
                  row.says) for row in rows]
    views = []
    for i, ch, h, edit, said in found:
        measured = measured_against(draft_id, ch)
        views.append(SuggestionView(id=i, change=ch, heard=h, says=said or _says(ch, measured),
                                    measured=measured, edit=edit))
    return views


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


async def apply(session_id: str, suggestion_id: str, *, by: str) -> dict:
    """The person takes the suggestion: its change, performed as theirs, **and the jobs it asks
    for queued after the commit** (`act`, review I1) — the next question's phrasing, a card's
    read-back."""
    from starlette.concurrency import run_in_threadpool

    from mendel_api.services import session

    def group():
        with session_scope() as db:
            _pending_row(db, session_id, suggestion_id)
            return _group(db, session_id, suggestion_id)

    def read(one):
        with session_scope() as db:
            row = _pending_row(db, session_id, one)
            change = DecisionChange.model_validate(row.change).model_copy(
                update={"actor": "person"})
            sess = db.get(PipelineAuthoringSession, session_id)
            draft = db.get(PipelineDraft, sess.draft_id)
            return change, (draft.decision_revision, draft.revision, sess.row_version)

    # **A hand edit's readings are taken together**, in the order read (a want before the tool
    # that makes it); each is one command, as every change is.
    done = None
    for one in await run_in_threadpool(group):
        change, versions = await run_in_threadpool(read, one)
        done = await session.act(
            c.Change(session_id, change.model_dump(mode="json"), by, *versions))
        await run_in_threadpool(mark_applied, one)
    return done.result


def mark_applied(suggestion_id: str) -> None:
    """Applied by another path (an edited goal card that kept it)."""
    with session_scope() as db:
        _settle(db, db.get(PipelineAuthoringSuggestion, suggestion_id), SuggestionState.APPLIED)


def dismiss(session_id: str, suggestion_id: str, *, by: str) -> None:
    with session_scope() as db:
        _pending_row(db, session_id, suggestion_id)
        for one in _group(db, session_id, suggestion_id):
            _settle(db, _pending_row(db, session_id, one), SuggestionState.DISMISSED)


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

"""Authoring sessions, turns and proposals, made durable.

**The rules live in `authoring/state.py`; this file holds rows.** Every phase change goes through
`state.advance` and every settlement through `state.settle`, so the diagram in the plan's §2 is
enforced in one place rather than re-derived by each verb here. That is `forge_state.py`'s split
and it earns its keep the same way: the second caller is where a remembered `if` fails.

**Two things are compared on every mutating write**, and they catch different mistakes:

- `expected_revision` against `pipeline_draft.revision` — the client acted on a picture of the
  draft, and the picture is stale. This is the two-tab case, which §2 calls ordinary.
- `row_version` on the session — the *session* moved, even if the draft did not. A model answer
  landing after the person revised their goal is this one, and only this one.

Neither is a timestamp, for the reason `state.settle` records: two writes inside one clock tick
are indistinguishable by time, which is precisely when the comparison matters.

**Nothing here composes a prompt or calls a provider.** `services/authoring_ai.py` is Task 6's,
and keeping the transport out of this file is what lets every test below run against a database
and no model.
"""

import secrets
from datetime import UTC, datetime

from comeni_core.diagnostics import coded
from sqlalchemy import select, update

from mendel_api.authoring import state as st
from mendel_api.authoring.types import Mode, Phase, ProposalState, TurnState
from mendel_api.db import session_scope
from mendel_api.models import (
    PipelineAuthoringProposal,
    PipelineAuthoringSession,
    PipelineAuthoringTurn,
    PipelineDraft,
)


def _now() -> datetime:
    return datetime.now(UTC)


def _id() -> str:
    """`secrets.token_hex(16)`, exactly as `PipelineDraft` uses.

    Opaque rather than serial for `routes/build.py`'s reason: the API may not take a path, and a
    guessable id is the next-worst thing.
    """
    return secrets.token_hex(16)


def open_session(draft_id: str, *, mode: Mode, who: str) -> str:
    """Start a conversation about a draft, or refuse if one is already open.

    **One session per draft**, which the unique index enforces and this refuses first — the same
    two-mechanism arrangement `forge_state.begin` uses, so a person reads a sentence rather than
    a constraint violation.
    """
    with session_scope() as session:
        if session.get(PipelineDraft, draft_id) is None:
            raise KeyError(draft_id)

        existing = session.scalar(
            select(PipelineAuthoringSession).where(
                PipelineAuthoringSession.draft_id == draft_id
            )
        )
        if existing is not None:
            raise ValueError(
                coded("MI0200", "this draft already has an authoring session")
                + f"\n  it is {existing.id}, in phase {existing.phase}"
            )

        session_id = _id()
        now = _now()
        session.add(
            PipelineAuthoringSession(
                id=session_id,
                draft_id=draft_id,
                mode=mode.value,
                phase=Phase.UNDERSTANDING.value,
                failed_from=None,
                goal=None,
                blueprint={},
                registry_digest="",
                cursor=0,
                row_version=1,
                who=who,
                created_at=now,
                updated_at=now,
            )
        )
    return session_id


def read(session_id: str) -> dict:
    """Everything a browser needs to draw the session, in one read.

    **The checkpoint's shape.** Task 3 asks that restarting the API between writing and reading
    changes nothing, and that is only checkable if one call returns the whole picture: phase,
    transcript, the pending proposal, the confirmed goal, and the draft's revision. Assembling it
    from four endpoints would make the checkpoint a statement about four caches.
    """
    with session_scope() as db:
        row = db.get(PipelineAuthoringSession, session_id)
        if row is None:
            raise KeyError(session_id)
        draft = db.get(PipelineDraft, row.draft_id)

        turns = db.scalars(
            select(PipelineAuthoringTurn)
            .where(PipelineAuthoringTurn.session_id == session_id)
            .order_by(PipelineAuthoringTurn.seq)
        ).all()
        pending = db.scalar(
            select(PipelineAuthoringProposal).where(
                PipelineAuthoringProposal.session_id == session_id,
                PipelineAuthoringProposal.state == ProposalState.PENDING.value,
            )
        )
        return {
            "id": row.id,
            "draft_id": row.draft_id,
            "mode": row.mode,
            "phase": row.phase,
            "failed_from": row.failed_from,
            "goal": row.goal,
            "cursor": row.cursor,
            "row_version": row.row_version,
            "revision": draft.revision if draft else 0,
            "turns": [
                {
                    "seq": t.seq,
                    "role": t.role,
                    "state": t.state,
                    "text": t.text,
                    "blocks": t.blocks,
                    "base_revision": t.base_revision,
                }
                for t in turns
            ],
            "pending_proposal": (
                None
                if pending is None
                else {
                    "id": pending.id,
                    "kind": pending.kind,
                    "payload": pending.payload,
                    "draft_revision": pending.draft_revision,
                }
            ),
        }


def move(session_id: str, event: st.Event, *, row_version: int, **values: object) -> Phase:
    """One phase change, compare-and-swap on the session's own version.

    `state.advance` decides *whether* and `UPDATE … WHERE row_version` decides *whether it is
    still ours*. Both are needed and they catch different mistakes — the first an illegal move,
    the second a legal move applied to a session somebody else already moved.
    """
    with session_scope() as db:
        row = db.get(PipelineAuthoringSession, session_id)
        if row is None:
            raise KeyError(session_id)

        current = Phase(row.phase)
        came_from = Phase(row.failed_from) if row.failed_from else None
        target = st.advance(current, event, came_from)

        # Cleared on every move that is not *into* failure, so a retried session does not carry
        # the phase of a failure it has already recovered from — `forge_state.move` clears
        # `failed_stage` for exactly this reason, and a stale one sends the next retry wrong.
        failed = st.failed_from(current).value if target is Phase.FAILED else None

        done = db.execute(
            update(PipelineAuthoringSession)
            .where(
                PipelineAuthoringSession.id == session_id,
                PipelineAuthoringSession.row_version == row_version,
            )
            .values(
                phase=target.value,
                failed_from=failed,
                row_version=row_version + 1,
                updated_at=_now(),
                **values,
            )
        )
        if done.rowcount != 1:
            raise ValueError(
                coded("MI0201", "this session moved while you were looking at it")
                + f"\n  you held version {row_version}; it is at {row.row_version}"
                + "\n  re-read it before acting on it"
            )
    return target


def say(session_id: str, text: str) -> int:
    """Record what a person said, and the pending turn that will answer it.

    **Two rows, written together.** The assistant's turn exists as `pending` from the moment the
    person's is accepted, so the transcript can draw the waiting. A browser inventing that
    placeholder locally would lose it on reload, which is the defect this closes rather than the
    tidiness it looks like.
    """
    with session_scope() as db:
        row = db.get(PipelineAuthoringSession, session_id)
        if row is None:
            raise KeyError(session_id)
        draft = db.get(PipelineDraft, row.draft_id)
        revision = draft.revision if draft else 0

        seq = _next_seq(db, session_id)
        now = _now()
        db.add(
            PipelineAuthoringTurn(
                session_id=session_id,
                seq=seq,
                role="person",
                state=TurnState.ANSWERED.value,
                blocks=[],
                text=text,
                base_revision=revision,
                at=now,
            )
        )
        db.add(
            PipelineAuthoringTurn(
                session_id=session_id,
                seq=seq + 1,
                role="assistant",
                state=TurnState.PENDING.value,
                blocks=[],
                text="",
                base_revision=revision,
                at=now,
            )
        )
        return seq + 1


def _next_seq(db, session_id: str) -> int:
    """The next position in the transcript.

    Derived from the rows rather than counted on the session, because a counter on the session is
    a second source of truth for the same fact. The unique index on `(session_id, seq)` is what
    makes a race here a refusal rather than two turns at one position.
    """
    highest = db.scalar(
        select(PipelineAuthoringTurn.seq)
        .where(PipelineAuthoringTurn.session_id == session_id)
        .order_by(PipelineAuthoringTurn.seq.desc())
        .limit(1)
    )
    return 0 if highest is None else highest + 1


def answer(
    session_id: str,
    seq: int,
    *,
    blocks: list,
    base_revision: int,
    invocation_id: str | None = None,
) -> bool:
    """Fill in a pending assistant turn, unless the draft has moved under it.

    **Returns `False` rather than raising when the answer is late.** A model call that finishes
    after the person revised their goal has not failed — it answered a question that is no longer
    being asked — and the turn is marked `failed` so the transcript says so. Raising would make
    the worker's ordinary case an exception path.
    """
    with session_scope() as db:
        row = db.get(PipelineAuthoringSession, session_id)
        if row is None:
            raise KeyError(session_id)
        draft = db.get(PipelineDraft, row.draft_id)
        current = draft.revision if draft else 0

        late = current != base_revision
        done = db.execute(
            update(PipelineAuthoringTurn)
            .where(
                PipelineAuthoringTurn.session_id == session_id,
                PipelineAuthoringTurn.seq == seq,
                PipelineAuthoringTurn.state == TurnState.PENDING.value,
            )
            .values(
                state=TurnState.FAILED.value if late else TurnState.ANSWERED.value,
                blocks=[] if late else blocks,
                ai_invocation_id=invocation_id,
                at=_now(),
            )
        )
        # rowcount 0 is a duplicate delivery: the turn is already answered, and re-answering it
        # would overwrite one account of what happened with another.
        return done.rowcount == 1 and not late


def propose(session_id: str, *, kind: str, payload: dict, turn_id: int | None = None) -> str:
    """Offer something, against the draft as it stands now.

    Refuses a second pending proposal rather than letting the partial unique index do it, so the
    caller reads a sentence. §2's MVP rule is one pending mutation proposal per session.
    """
    with session_scope() as db:
        row = db.get(PipelineAuthoringSession, session_id)
        if row is None:
            raise KeyError(session_id)
        draft = db.get(PipelineDraft, row.draft_id)

        outstanding = db.scalar(
            select(PipelineAuthoringProposal).where(
                PipelineAuthoringProposal.session_id == session_id,
                PipelineAuthoringProposal.state == ProposalState.PENDING.value,
            )
        )
        if outstanding is not None:
            raise ValueError(
                coded("MI0203", "this session already has a proposal waiting for an answer")
                + f"\n  it is {outstanding.id}"
            )

        proposal_id = _id()
        db.add(
            PipelineAuthoringProposal(
                id=proposal_id,
                session_id=session_id,
                turn_id=turn_id,
                kind=kind,
                payload=payload,
                state=ProposalState.PENDING.value,
                chosen_option=None,
                by=None,
                draft_revision=draft.revision if draft else 0,
                created_at=_now(),
                settled_at=None,
            )
        )
    return proposal_id


def decide(
    proposal_id: str,
    decision: ProposalState,
    *,
    expected_revision: int,
    by: str,
    chosen_option: str | None = None,
) -> st.Settlement:
    """Accept or reject a proposal, or say why it cannot be settled.

    Every refusal path leaves the draft untouched, which is the property Task 3 asks for: *a
    stale proposal never applies to a newer draft*. A stale one is additionally **marked** stale,
    because the person needs to see that the engine withdrew it rather than that they declined
    it — and that write is the one case where a refusal still changes a row.
    """
    with session_scope() as db:
        row = db.get(PipelineAuthoringProposal, proposal_id)
        if row is None:
            raise KeyError(proposal_id)
        session_row = db.get(PipelineAuthoringSession, row.session_id)
        draft = db.get(PipelineDraft, session_row.draft_id)
        revision = draft.revision if draft else 0

        outcome = st.settle(
            current=ProposalState(row.state),
            proposal_revision=row.draft_revision,
            draft_revision=revision,
            expected_revision=expected_revision,
            decision=decision,
        )

        if outcome.state is not ProposalState(row.state):
            row.state = outcome.state.value
            row.settled_at = _now()
            if outcome.applies:
                row.by = by
                row.chosen_option = chosen_option

        if outcome.bumps_revision and draft is not None:
            draft.revision = revision + 1
            draft.updated_at = _now()

    return outcome

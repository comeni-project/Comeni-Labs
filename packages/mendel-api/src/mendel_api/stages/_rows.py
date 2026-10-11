"""Rows every stage writes (plan 1c): the session's version, the transcript's turns, proposals.

Moved verbatim from `services/authoring.py`. **`store_goal` and the proposal kinds live here**
because gathering, the card and building all write or read them.
"""

import secrets
from collections.abc import Callable
from datetime import UTC, datetime

from comeni_core.diagnostics import coded
from mendel_authoring import state as st
from sqlalchemy import select, update

from mendel_api.authoring import envelopes
from mendel_api.authoring.types import (
    Narrative,
    ProposalKind,
    ProposalState,
    TurnRole,
    TurnState,
)
from mendel_api.db import session_scope
from mendel_api.models import (
    PipelineAuthoringProposal,
    PipelineAuthoringSession,
    PipelineAuthoringTurn,
    PipelineDraft,
)
from mendel_api.services import draft_mutations


def now() -> datetime:
    return datetime.now(UTC)


def new_id() -> str:
    """`secrets.token_hex(16)`, exactly as `PipelineDraft` uses.

    Opaque rather than serial for `routes/build.py`'s reason: the API may not take a path, and a
    guessable id is the next-worst thing.
    """
    return secrets.token_hex(16)


def next_seq(db, session_id: str) -> int:
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

        proposal_id = new_id()
        db.add(
            PipelineAuthoringProposal(
                id=proposal_id,
                session_id=session_id,
                turn_id=turn_id,
                kind=kind,
                payload=envelopes.prepare(payload, kind=kind, draft=draft, session=row),
                state=ProposalState.PENDING.value,
                chosen_option=None,
                by=None,
                draft_revision=draft.revision if draft else 0,
                created_at=now(),
                settled_at=None,
            )
        )
    return proposal_id


def read_offer(db, proposal):
    """Validate the whole offer and its decision context before applying an answer."""
    envelope = envelopes.parse(proposal.payload, kind=proposal.kind)
    row = db.get(PipelineAuthoringSession, proposal.session_id)
    draft = db.get(PipelineDraft, row.draft_id)
    if envelope.context.decision_revision != draft.decision_revision:
        raise ValueError(coded("MI0201", "the selected decisions changed after this offer"))
    return envelope


def settlement(proposal_id: str, decision: ProposalState, expected_revision: int):
    """What `decide` would say, written nowhere: its refusals, checked before the diagram."""
    with session_scope() as db:
        row = db.get(PipelineAuthoringProposal, proposal_id)
        if row is None:
            raise KeyError(proposal_id)
        draft = db.get(PipelineDraft, db.get(PipelineAuthoringSession, row.session_id).draft_id)
        return st.settle(
            current=ProposalState(row.state),
            proposal_revision=row.draft_revision,
            draft_revision=draft.revision if draft else 0,
            expected_revision=expected_revision,
            decision=decision,
        )


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
        session_row = draft_mutations.lock_session(db, row.session_id)
        row = db.get(PipelineAuthoringProposal, proposal_id, with_for_update=True,
                     populate_existing=True)
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
            row.settled_at = now()
            if outcome.applies:
                row.by = by
                row.chosen_option = chosen_option

        if outcome.bumps_revision and draft is not None:
            draft_mutations.touch(db, draft)

    return outcome


STEP = ProposalKind.STEP
"""The proposal `kind` for a step offered from a blueprint."""


def note(session_id: str, text: str, *, code: str) -> None:
    """An answered assistant turn holding one refusal notice — something the engine says that
    no model call produced, the same shape `_refused` writes for one that did."""
    engine_turn(
        session_id,
        lambda seq: [{"kind": "notice", "id": f"notice-{seq}", "notice": "refusal",
                      "text": text[:2000], "code": code}],
    )


def engine_turn(session_id: str, blocks: Callable[[int], list[dict]]) -> None:
    """An answered assistant turn holding blocks the engine wrote — no model call.

    `blocks` is given the turn's seq, which is known only inside the transaction, so each block
    is built, and validated, with its real id."""
    with session_scope() as db:
        draft = db.get(PipelineDraft, db.get(PipelineAuthoringSession, session_id).draft_id)
        seq = next_seq(db, session_id)
        db.add(
            PipelineAuthoringTurn(
                session_id=session_id,
                seq=seq,
                role=TurnRole.ASSISTANT,
                state=TurnState.ANSWERED.value,
                blocks=blocks(seq),
                text="",
                base_revision=draft.revision if draft else 0,
                at=now(),
            )
        )


def swap(db, session_id: str, version: int, **values: object) -> None:
    """Write a session's values inside an open transaction, compare-and-swap on its version.

    **Never its phase or node**: the dispatcher moves a session (`services/session.py`,
    14.7.8.1), and this writes what a step recorded — facts, a blueprint, the cursor.
    """
    done = db.execute(
        update(PipelineAuthoringSession)
        .where(
            PipelineAuthoringSession.id == session_id,
            PipelineAuthoringSession.row_version == version,
        )
        .values(
            row_version=version + 1,
            updated_at=now(),
            **values,
        )
    )
    if done.rowcount != 1:
        raise ValueError(
            coded("MI0201", "this session moved while the blueprint was being resolved")
            + f"\n  it was at version {version} when the work started"
            + "\n  re-read it before acting on it"
        )


def store_goal(session_id: str, goal: dict | None) -> None:
    """The session's goal: the want the model read until the card composes one (14.7.3), then the
    confirmed goal. No move: the dispatcher moves the session (14.7.8.1)."""
    with session_scope() as db:
        row = db.get(PipelineAuthoringSession, session_id)
        if row is None:
            raise KeyError(session_id)
        row.goal = goal
        row.row_version += 1
        row.updated_at = now()


GOAL = ProposalKind.GOAL
"""The proposal `kind` for a goal summary awaiting confirmation."""


GAP = ProposalKind.GAP
"""The proposal `kind` for one thing the want needs that no fact settles yet."""


def say_engine(session_id: str, text: str) -> None:
    """An answered assistant turn holding one narrative the engine wrote — no model call."""
    engine_turn(
        session_id,
        lambda seq: [Narrative(id=f"said-{seq}", text=text[:2000]).model_dump(mode="json")],
    )



def pending_of(db, session_id: str):
    """The session's pending proposal, if any, read inside an open transaction."""
    return db.scalar(
        select(PipelineAuthoringProposal).where(
            PipelineAuthoringProposal.session_id == session_id,
            PipelineAuthoringProposal.state == ProposalState.PENDING.value,
        )
    )

"""Deleting what a person asks to delete (Part H spec §5.1). **Permanent**: there is no undo.

Children first, in one transaction: the decision rows' subject↔revision cycle is deferred, every
other foreign key is `RESTRICT`. **A draft's model calls are not deleted**: `ai_invocation` has
no foreign key so that a deleted session does not take its audit rows with it. Their text goes.

**A fork keeps what it inherited.** A corrected fork reads its parent's observations through its
own evidence access (Part F). Each observation another draft still uses is handed to the oldest
such draft, so the fork's history reads exactly as before and only the parent is gone.
"""

import shutil
from datetime import UTC, datetime
from typing import NamedTuple

import sqlalchemy as sa
from comeni_core.diagnostics import coded

from mendel_api.db import session_scope
from mendel_api.decision_models import PipelineEvidenceAccess, PipelineObservation
from mendel_api.models import (
    AiInvocation,
    GateRun,
    GateState,
    PipelineAuthoringSession,
    PipelineDraft,
    ReplyCleared,
)
from mendel_api.settings import settings

_SUBJECTS = ("pipeline_input", "pipeline_want", "pipeline_fact", "pipeline_producer",
             "pipeline_parameter", "pipeline_review", "pipeline_asked")
"""Each with its `_revision` table. A subject names its current revision and every revision its
subject, both `RESTRICT`, which Postgres checks at the end of each statement even where the
constraint is deferrable: so a subject and its revisions go in one statement."""

_AFTER = ("pipeline_evidence_access", "pipeline_observation", "pipeline_phrasing",
          "pipeline_decision_migration")
"""What the revisions reference, after them."""


class Deleted(NamedTuple):
    rows: int
    replies_cleared: int


def clear_replies(db, where, reason: str) -> int:
    """Empty the reply text of the calls `where` selects, saying why. Their record stays."""
    result = db.execute(
        sa.update(AiInvocation)
        .where(where, AiInvocation.response.is_not(None))
        .values(response=None, response_cleared=ReplyCleared(reason).value,
                response_cleared_at=datetime.now(UTC))
    )
    return result.rowcount


def _hand_inherited_evidence_on(db, draft_id: str) -> None:
    borrowers = db.execute(
        sa.select(PipelineEvidenceAccess.observation_id, PipelineEvidenceAccess.draft_id)
        .join(PipelineObservation,
              PipelineObservation.id == PipelineEvidenceAccess.observation_id)
        .join(PipelineDraft, PipelineDraft.id == PipelineEvidenceAccess.draft_id)
        .where(PipelineObservation.draft_id == draft_id,
               PipelineEvidenceAccess.draft_id != draft_id)
        .order_by(PipelineDraft.updated_at, PipelineDraft.id)
    ).all()
    heir: dict[str, str] = {}
    for observation_id, borrower in borrowers:
        heir.setdefault(observation_id, borrower)
    for observation_id, borrower in heir.items():
        db.execute(sa.update(PipelineObservation)
                   .where(PipelineObservation.id == observation_id)
                   .values(draft_id=borrower))
        db.execute(sa.update(PipelineEvidenceAccess)
                   .where(PipelineEvidenceAccess.observation_id == observation_id,
                          PipelineEvidenceAccess.draft_id == borrower)
                   .values(inherited=False))


def delete_draft(draft_id: str) -> Deleted:
    with session_scope() as db:
        draft = db.get(PipelineDraft, draft_id, with_for_update=True)
        if draft is None:
            raise KeyError(draft_id)
        live = db.scalar(sa.select(sa.func.count()).select_from(GateRun).where(
            GateRun.draft_id == draft_id,
            GateRun.state.in_([GateState.QUEUED.value, GateState.RUNNING.value])))
        if live:
            raise ValueError(coded("MI0401", "a gate is running on this draft; let it finish, "
                                             "then delete the draft"))
        sessions = list(db.scalars(sa.select(PipelineAuthoringSession.id)
                                   .where(PipelineAuthoringSession.draft_id == draft_id)))
        _hand_inherited_evidence_on(db, draft_id)
        rows = 0
        for subject in _SUBJECTS:
            rows += db.execute(sa.text(
                f"WITH gone AS (DELETE FROM {subject} WHERE draft_id = :d RETURNING 1) "
                f"DELETE FROM {subject}_revision WHERE draft_id = :d"), {"d": draft_id}).rowcount
        for table in _AFTER:
            rows += db.execute(sa.text(f"DELETE FROM {table} WHERE draft_id = :d"),
                               {"d": draft_id}).rowcount
        if sessions:
            for table in ("pipeline_authoring_suggestion", "pipeline_authoring_proposal",
                          "pipeline_authoring_turn"):
                rows += db.execute(sa.text(f"DELETE FROM {table} WHERE session_id = ANY(:s)"),
                                   {"s": sessions}).rowcount
            rows += db.execute(sa.delete(PipelineAuthoringSession)
                               .where(PipelineAuthoringSession.draft_id == draft_id)).rowcount
        # **After the sessions go, never before** (review finding 2): a reply being written now
        # either waits on them and finds them gone, or is committed before this reads it.
        cleared = (clear_replies(db, AiInvocation.session_id.in_(sessions), "deleted")
                   if sessions else 0)
        rows += db.execute(sa.delete(GateRun).where(GateRun.draft_id == draft_id)).rowcount
        db.execute(sa.update(PipelineDraft).where(PipelineDraft.forked_from == draft_id).values(
            forked_from=None, fork_key=None, fork_sequence=None, fork_at=None))
        db.delete(draft)
        rows += 1
    shutil.rmtree(settings.draft_root / draft_id, ignore_errors=True)
    return Deleted(rows, cleared)

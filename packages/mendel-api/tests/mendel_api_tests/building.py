"""Reusable building scenarios and fixtures for API tests."""

import pytest
from comeni_core import yaml_strict
from comeni_core.plan.draft import DraftGraph, DraftProvenance
from mendel_api.authoring.types import Phase
from mendel_api.db import session_scope
from mendel_api.models import (
    PipelineAuthoringProposal,
    PipelineAuthoringSession,
    PipelineDraft,
)
from mendel_api.services import drafts
from mendel_api.services import session as facade
from mendel_authoring import commands
from mendel_authoring import state as st
from mendel_resolver.goal import Goal
from support.paths import ROOT as REPOSITORY_ROOT

from mendel_api_tests import session_setup as authoring_setup
from mendel_api_tests.database import truncate

ROOT = REPOSITORY_ROOT


HISAT2 = "nf-core/hisat2/align@2.2.2"


@pytest.fixture
def clean():
    """Every table these rows touch, in one statement — `clean_forge`'s reason, extended by the
    two tables a session and its draft add. Each foreign key here is `RESTRICT`."""
    tables = (
        "forge_message, forge_event, forge_revision, forge_adaptation, forge_catalogue_item, "
        "forge_source_snapshot, ai_invocation, pipeline_authoring_proposal, "
        "pipeline_authoring_turn, pipeline_authoring_session, pipeline_draft, gate_run"
    )
    with session_scope() as session:
        session.execute(truncate(f"TRUNCATE TABLE {tables}"))
    yield


def _goal() -> Goal:
    return Goal.model_validate(yaml_strict.load(ROOT / "tests" / "fixtures" / "goal-v6" / "rnaseq-goal.yml"))


def _without_read_length() -> Goal:
    data = yaml_strict.load(ROOT / "tests" / "fixtures" / "goal-v6" / "rnaseq-goal.yml")
    data["profile"].pop("read_length")
    return Goal.model_validate(data)


def _resolving(goal: Goal | None = None) -> str:
    """A session whose goal has been confirmed, sitting in `resolving`."""
    draft_id = drafts.create(DraftGraph(), "rnaseq", "ana")
    session_id = facade.perform(commands.OpenSession(draft_id, "ana")).result
    authoring_setup.move(session_id, st.Event.WANT_RETURNED, row_version=1)
    authoring_setup.move(session_id, st.Event.NOTHING_MISSING, row_version=2)
    authoring_setup.move(
        session_id,
        st.Event.GOAL_ACCEPTED,
        row_version=3,
        goal=(goal or _goal()).model_dump(mode="json"),
    )
    return session_id


def _draft(session_id: str) -> tuple[DraftGraph, DraftProvenance, int]:
    with session_scope() as db:
        row = db.get(PipelineAuthoringSession, session_id)
        draft = db.get(PipelineDraft, row.draft_id)
        return (
            DraftGraph.model_validate(draft.graph),
            DraftProvenance.model_validate(draft.provenance or {}),
            draft.revision,
        )


def _proposal(proposal_id: str) -> PipelineAuthoringProposal:
    with session_scope() as db:
        row = db.get(PipelineAuthoringProposal, proposal_id)
        db.expunge(row)
        return row


def _phase(session_id: str) -> Phase:
    with session_scope() as db:
        return Phase(db.get(PipelineAuthoringSession, session_id).phase)


# ── answering ─────────────────────────────────────────────────────────────────────────────
def _answer_all(session_id: str, first: str) -> None:
    proposal_id = first
    while proposal_id is not None:
        _, _, revision = _draft(session_id)
        outcome = facade.perform(commands.SettleStep(proposal_id, revision, "ana")).result
        assert outcome.settlement.refusal is None, outcome.settlement.refusal
        proposal_id = outcome.next_proposal


# ── Part G, Task 6: what a run needs, apart from what the registry lacks ─────────────────────
def _walked_to_the_end_with_hisat2(case, show_gaps: bool) -> dict:
    with session_scope() as db:
        db.get(PipelineAuthoringSession, case.session_id).show_gaps = show_gaps
    facade.perform(commands.Amend(case.proposal_id, case.option_id, None, "ana"))
    for _ in range(20):
        picture = facade.read(case.session_id)
        pending = picture["pending_proposal"]
        if pending is None:
            return picture
        facade.perform(commands.SettleStep(pending["id"], picture["revision"], "ana"))
    raise AssertionError("the walk did not end within 20 steps")


def _receipt(picture) -> str:
    return next(
        b["summary"]
        for t in reversed(picture["turns"])
        for b in t["blocks"]
        if b["kind"] == "receipt" and b["id"].startswith("wrap-")
    )

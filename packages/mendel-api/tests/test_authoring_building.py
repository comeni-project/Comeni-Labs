"""A session's blueprint, stored and answered step by step, against a real database.

`test_blueprint.py` holds the engine to the registry with no rows. What cannot be checked there
is that the commit is **one transaction** — graph, sidecar, revision, the proposal's outcome and
the next proposal land together — and that a refusal changes nothing it should not. That is what
this file is for.
"""

from pathlib import Path

import pytest
from comeni_ai import Client, ModelAccess
from comeni_core import yaml_strict
from comeni_core.plan.draft import DraftGraph, DraftProvenance
from comeni_core.plan.tiers import ValueSource
from mendel_api.authoring import state as st
from mendel_api.authoring.resolver import Call
from mendel_api.authoring.types import Mode, Phase, ProposalState
from mendel_api.db import session_scope
from mendel_api.models import (
    AiInvocation,
    PipelineAuthoringProposal,
    PipelineAuthoringSession,
    PipelineDraft,
)
from mendel_api.services import authoring, authoring_ai, drafts
from mendel_api.services import blueprint as bp
from mendel_resolver.goal import Goal
from sqlalchemy import select, text

ROOT = Path(__file__).resolve().parents[3]
HISAT2 = "nf-core/hisat2/align@2.2.2"


def _database_is_reachable() -> bool:
    try:
        with session_scope() as session:
            session.execute(text("SELECT 1"))
    except Exception:
        return False
    return True


pytestmark = pytest.mark.skipif(
    not _database_is_reachable(), reason="no database — run `docker compose up -d postgres`"
)


@pytest.fixture
def clean():
    """Every table these rows touch, in one statement — `clean_forge`'s reason, extended by the
    two tables a session and its draft add. Each foreign key here is `RESTRICT`."""
    tables = (
        "forge_message, forge_event, forge_revision, forge_adaptation, forge_catalogue_item, "
        "forge_source_snapshot, ai_invocation, pipeline_authoring_proposal, "
        "pipeline_authoring_turn, pipeline_authoring_session, pipeline_draft"
    )
    with session_scope() as session:
        session.execute(text(f"TRUNCATE TABLE {tables}"))
    yield


def _goal() -> Goal:
    return Goal.model_validate(yaml_strict.load(ROOT / "examples" / "rnaseq-goal.yml"))


def _resolving(mode: Mode = Mode.BUILD) -> str:
    """A session whose goal has been confirmed, sitting in `resolving`."""
    draft_id = drafts.create(DraftGraph(), "rnaseq", "ana")
    session_id = authoring.open_session(draft_id, mode=mode, who="ana")
    authoring.move(session_id, st.Event.GOAL_RETURNED, row_version=1)
    authoring.move(
        session_id,
        st.Event.GOAL_ACCEPTED,
        row_version=2,
        goal=_goal().model_dump(mode="json"),
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


# ── starting ──────────────────────────────────────────────────────────────────────────────


def test_building_stores_the_blueprint_and_offers_its_first_step(clean):
    session_id = _resolving()
    first = authoring.start_building(session_id)

    assert _phase(session_id) is Phase.BUILDING
    assert _proposal(first).payload["node"] == "star_genomegenerate"
    with session_scope() as db:
        row = db.get(PipelineAuthoringSession, session_id)
        assert row.blueprint["order"][0] == "star_genomegenerate"
        # **The regression.** A digest is seventy-one characters and the column was 64.
        assert len(row.registry_digest) == 71
        assert db.get(PipelineDraft, row.draft_id).goal is not None


def test_building_cannot_start_from_any_phase_but_resolving(clean):
    draft_id = drafts.create(DraftGraph(), "rnaseq", "ana")
    session_id = authoring.open_session(draft_id, mode=Mode.BUILD, who="ana")
    with pytest.raises(ValueError, match="MI0200"):
        authoring.start_building(session_id)


# ── answering ─────────────────────────────────────────────────────────────────────────────


def _answer_all(session_id: str, first: str, *, reject: set[str] = frozenset()) -> None:
    proposal_id = first
    while proposal_id is not None:
        node = _proposal(proposal_id).payload["node"]
        _, _, revision = _draft(session_id)
        outcome = authoring.settle_step(
            proposal_id,
            ProposalState.REJECTED if node in reject else ProposalState.ACCEPTED,
            expected_revision=revision,
            by="ana",
        )
        assert outcome.settlement.refusal is None, outcome.settlement.refusal
        proposal_id = outcome.next_proposal


def test_accepting_every_step_completes_the_session_with_the_whole_spine(clean):
    session_id = _resolving()
    _answer_all(session_id, authoring.start_building(session_id))
    graph, provenance, revision = _draft(session_id)

    assert _phase(session_id) is Phase.COMPLETE
    assert revision == 5
    assert len(graph.nodes) == 5
    assert {(e.from_node, e.to_node) for e in graph.edges} == {
        ("trimgalore", "star_align"),
        ("star_genomegenerate", "star_align"),
        ("star_align", "samtools_sort"),
        ("samtools_sort", "subread_featurecounts"),
    }
    assert provenance.node("star_align").selection.source is ValueSource.RESOLVER


def test_a_rejected_step_is_never_wired_to_and_does_not_move_the_revision(clean):
    session_id = _resolving()
    _answer_all(session_id, authoring.start_building(session_id), reject={"trimgalore"})
    graph, _, revision = _draft(session_id)

    assert "trimgalore" not in {n.id for n in graph.nodes}
    assert all("trimgalore" not in (e.from_node, e.to_node) for e in graph.edges)
    assert revision == 4


def test_choosing_an_alternative_commits_it_as_a_persons_choice(clean):
    session_id = _resolving()
    proposal_id = authoring.start_building(session_id)
    while _proposal(proposal_id).payload["node"] != "star_align":
        _, _, revision = _draft(session_id)
        proposal_id = authoring.settle_step(
            proposal_id, ProposalState.ACCEPTED, expected_revision=revision, by="ana"
        ).next_proposal

    options = _proposal(proposal_id).payload["options"]
    chosen = next(option for option, contract in options.items() if contract == HISAT2)
    _, _, revision = _draft(session_id)
    outcome = authoring.settle_step(
        proposal_id,
        ProposalState.ACCEPTED,
        expected_revision=revision,
        by="ana",
        chosen_option=chosen,
    )
    graph, provenance, _ = _draft(session_id)

    assert outcome.settlement.refusal is None
    assert next(n for n in graph.nodes if n.id == "star_align").contract_id == HISAT2
    assert provenance.node("star_align").selection.source is ValueSource.HUMAN
    assert _proposal(proposal_id).chosen_option == chosen


# ── what is refused, and what it leaves alone ─────────────────────────────────────────────


def test_an_option_that_was_never_offered_is_refused_and_changes_nothing(clean):
    session_id = _resolving()
    proposal_id = authoring.start_building(session_id)
    outcome = authoring.settle_step(
        proposal_id,
        ProposalState.ACCEPTED,
        expected_revision=0,
        by="ana",
        chosen_option="alt_99",
    )
    graph, _, revision = _draft(session_id)

    assert "MI0205" in outcome.settlement.refusal
    assert revision == 0 and graph.nodes == []
    assert _proposal(proposal_id).state == ProposalState.PENDING.value


def test_acting_on_an_old_picture_of_the_draft_is_refused(clean):
    """The two-tab case, through the step path rather than the generic one."""
    session_id = _resolving()
    proposal_id = authoring.start_building(session_id)
    outcome = authoring.settle_step(
        proposal_id, ProposalState.ACCEPTED, expected_revision=7, by="ana"
    )

    assert "MI0201" in outcome.settlement.refusal
    assert _draft(session_id)[2] == 0


def test_a_registry_that_moved_marks_the_proposal_stale_and_re_resolves(clean, monkeypatch):
    """`MI0206`. The option was offered against one registry; applying it against another would
    write a choice nobody made. Nothing reaches the draft, the proposal is `stale` rather than
    `rejected`, and a fresh proposal for the same step is waiting against the new digest."""
    session_id = _resolving()
    proposal_id = authoring.start_building(session_id)

    moved = "sha256:" + "0" * 64
    monkeypatch.setattr(bp, "registry_digest", lambda roots: moved)
    outcome = authoring.settle_step(
        proposal_id, ProposalState.ACCEPTED, expected_revision=0, by="ana"
    )

    assert "MI0206" in outcome.settlement.refusal
    assert _proposal(proposal_id).state == ProposalState.STALE.value
    assert _draft(session_id)[2] == 0
    assert _proposal(outcome.next_proposal).payload["node"] == "star_genomegenerate"
    with session_scope() as db:
        assert db.get(PipelineAuthoringSession, session_id).registry_digest == moved

    retried = authoring.settle_step(
        outcome.next_proposal, ProposalState.ACCEPTED, expected_revision=0, by="ana"
    )
    assert retried.settlement.refusal is None
    assert _draft(session_id)[2] == 1


# ── the audit ─────────────────────────────────────────────────────────────────────────────


def test_every_tier_four_call_becomes_an_invocation_row(clean):
    """The adapter keeps its calls in memory; this is where they are written down. A refused call
    is recorded with its code, because those are the rows worth reading."""
    calls = [
        Call("producer:alignment.bam", "nf-core/star/align@1.11.0", "fake/test",
             "builder.tier4.v1", "a" * 64, None),
        Call("producer:alignment.bam", None, "fake/test",
             "builder.tier4.v1", "b" * 64, "MA0005: 'nf-core/salmon' was not offered"),
    ]
    ids = authoring_ai.record_calls(
        calls, client=Client(ModelAccess(model="fake/test")), registry="sha256:" + "1" * 64
    )
    with session_scope() as db:
        rows = {row.id: row for row in db.scalars(select(AiInvocation)).all()}

    assert [rows[i].state for i in ids] == ["succeeded", "refused"]
    assert rows[ids[1]].failure_code == "MA0005"
    assert {rows[i].purpose for i in ids} == {"tier4"}
    assert {rows[i].agent for i in ids} == {"builder"}
    assert rows[ids[0]].duration_ms is None

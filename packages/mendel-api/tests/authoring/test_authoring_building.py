"""A session's blueprint, stored and answered step by step, against a real database.

`test_blueprint.py` holds the engine to the registry with no rows. What cannot be checked there
is that the commit is **one transaction** — graph, sidecar, revision, the proposal's outcome and
the next proposal land together — and that a refusal changes nothing it should not. That is what
this file is for."""

import pytest
from comeni_ai import Client, ModelAccess
from comeni_core.plan.draft import DraftGraph
from comeni_core.plan.tiers import ValueSource
from mendel_api.authoring.resolver import Call
from mendel_api.authoring.types import Phase, ProposalState
from mendel_api.db import session_scope
from mendel_api.models import (
    AiInvocation,
    PipelineAuthoringSession,
)
from mendel_api.services import authoring_ai, drafts
from mendel_api.services import blueprint as bp
from mendel_api.services import session as facade
from mendel_api_tests import session_setup as authoring_setup
from mendel_api_tests.building import (
    HISAT2,
    _answer_all,
    _draft,
    _phase,
    _proposal,
    _receipt,
    _resolving,
    _walked_to_the_end_with_hisat2,
)
from mendel_api_tests.building import (
    clean as clean,
)
from mendel_api_tests.database import reachable
from mendel_authoring import commands
from mendel_authoring import state as st
from mendel_resolver.goal import Goal
from sqlalchemy import select

pytestmark = pytest.mark.skipif(not reachable(), reason="no database — run `make test-db`")


# ── starting ──────────────────────────────────────────────────────────────────────────────
def test_building_stores_the_blueprint_and_offers_its_first_step(clean):
    session_id = _resolving()
    first = authoring_setup.start_building(session_id)

    assert _phase(session_id) is Phase.BUILDING
    assert _proposal(first).payload["node"] == "star_genomegenerate"
    with session_scope() as db:
        row = db.get(PipelineAuthoringSession, session_id)
        assert row.blueprint["order"][0] == "star_genomegenerate"
        # **The regression.** A digest is seventy-one characters and the column was 64.
        assert len(row.registry_digest) == 71
        from mendel_api.services import decisions

        assert decisions.goal(row.draft_id).want


def test_building_cannot_start_from_any_phase_but_resolving(clean):
    draft_id = drafts.create(DraftGraph(), "rnaseq", "ana")
    session_id = facade.perform(commands.OpenSession(draft_id, "ana")).result
    with pytest.raises(ValueError, match="MI0200"):
        authoring_setup.start_building(session_id)


def test_a_goal_missing_an_input_fails_into_the_log_with_its_code(clean):
    """**Found by the first walk (#115).** *paired-end RNA-seq to gene counts* was confirmed as
    `have: [fastq.reads]`, and resolving died on `nothing produces genome.fasta` — raised as a
    422 to a toast, written nowhere, with the session in `failed` and no way to read why after a
    reload. A resolver refusal is a fact about the goal, so it belongs in the conversation."""
    draft_id = drafts.create(DraftGraph(), "rnaseq", "ana")
    session_id = facade.perform(commands.OpenSession(draft_id, "ana")).result
    authoring_setup.move(session_id, st.Event.WANT_RETURNED, row_version=1)
    authoring_setup.move(session_id, st.Event.NOTHING_MISSING, row_version=2)
    only_reads = Goal.model_validate(
        {"have": [{"type_id": "fastq.reads"}], "want": ["counts.matrix"]}
    )
    authoring_setup.move(
        session_id, st.Event.GOAL_ACCEPTED, row_version=3, goal=only_reads.model_dump(mode="json")
    )

    assert authoring_setup.start_building(session_id) is None
    assert _phase(session_id) is Phase.FAILED

    last = facade.read(session_id)["turns"][-1]
    assert last["role"] == "assistant"
    [notice] = last["blocks"]
    assert notice["kind"] == "notice" and notice["code"] == "MI0207"
    assert "genome.fasta" in notice["text"]
    assert "[]" not in notice["text"]


def test_continuing_every_step_completes_the_session_with_the_whole_spine(clean):
    """Each *Continue* reviews one step, and the draft — the blueprint's reviewed steps — moves
    one revision for each."""
    session_id = _resolving()
    first = authoring_setup.start_building(session_id)
    _, _, started = _draft(session_id)
    _answer_all(session_id, first)
    graph, provenance, revision = _draft(session_id)

    assert _phase(session_id) is Phase.COMPLETE
    assert revision == started + 5
    assert len(graph.nodes) == 5
    assert {(e.from_node, e.to_node) for e in graph.edges} == {
        ("trimgalore", "star_align"),
        ("star_genomegenerate", "star_align"),
        ("star_align", "samtools_sort"),
        ("samtools_sort", "subread_featurecounts"),
    }
    assert provenance.node("star_align").selection.source is ValueSource.RESOLVER


def test_choosing_another_tool_rebuilds_the_pipeline_as_a_persons_choice(clean):
    """Spec §14.3: the tool goes into the goal as a pin and the blueprint is resolved again, so
    HISAT2 replaces STAR's step — under its own id, with its own index — credited to the person."""
    from mendel_api_tests.canvas_scenarios import at_aligner

    case = at_aligner()
    session_id, proposal_id, chosen = case.session_id, case.proposal_id, case.option_id
    outcome = facade.perform(commands.Amend(proposal_id, chosen, None, "ana")).result
    graph, provenance, _ = _draft(session_id)

    assert outcome.settlement.refusal is None
    assert next(n for n in graph.nodes if n.id == "hisat2_align").contract_id == HISAT2
    assert "star_align" not in {n.id for n in graph.nodes}
    assert provenance.node("hisat2_align").selection.source is ValueSource.HUMAN
    assert _proposal(proposal_id).chosen_option == chosen


# ── what is refused, and what it leaves alone ─────────────────────────────────────────────
def test_an_option_that_was_never_offered_is_refused_and_changes_nothing(clean):
    session_id = _resolving()
    proposal_id = authoring_setup.start_building(session_id)
    before = _draft(session_id)
    with pytest.raises(ValueError, match="MI0205"):
        facade.perform(commands.Amend(proposal_id, "alt_99", None, "ana"))

    assert _draft(session_id) == before
    assert _proposal(proposal_id).state == ProposalState.PENDING.value


def test_acting_on_an_old_picture_of_the_draft_is_refused(clean):
    """The two-tab case, through the step path rather than the generic one."""
    session_id = _resolving()
    proposal_id = authoring_setup.start_building(session_id)
    _, _, revision = _draft(session_id)
    outcome = facade.perform(commands.SettleStep(proposal_id, revision + 6, "ana")).result

    assert "MI0201" in outcome.settlement.refusal
    assert _draft(session_id)[2] == revision


def test_a_registry_that_moved_marks_the_proposal_stale_and_re_resolves(clean, monkeypatch):
    """`MI0206`. The card was offered against one registry; applying it against another would
    write a choice nobody made. Nothing is applied, the card is `stale` rather than `rejected`,
    and the walk offers the same step again from the blueprint resolved against the new digest."""
    session_id = _resolving()
    proposal_id = authoring_setup.start_building(session_id)
    _, _, revision = _draft(session_id)

    moved = "sha256:" + "0" * 64
    monkeypatch.setattr(bp, "registry_digest", lambda roots: moved)
    outcome = facade.perform(commands.SettleStep(proposal_id, revision, "ana")).result

    assert "MI0206" in outcome.settlement.refusal
    assert _proposal(proposal_id).state == ProposalState.STALE.value
    assert _draft(session_id)[0].nodes == []
    assert _proposal(outcome.next_proposal).payload["node"] == "star_genomegenerate"
    with session_scope() as db:
        assert db.get(PipelineAuthoringSession, session_id).registry_digest == moved

    _, _, revision = _draft(session_id)
    retried = facade.perform(commands.SettleStep(outcome.next_proposal, revision, "ana")).result
    assert retried.settlement.refusal is None
    assert [n.id for n in _draft(session_id)[0].nodes] == ["star_genomegenerate"]


# ── the audit ─────────────────────────────────────────────────────────────────────────────
def test_every_tier_four_call_becomes_an_invocation_row(clean):
    """The adapter keeps its calls in memory; this is where they are written down. A refused call
    is recorded with its code, because those are the rows worth reading."""
    calls = [
        Call(
            "producer:alignment.bam",
            "nf-core/star/align@1.11.0",
            "fake/test",
            "builder.tier4.v1",
            "a" * 64,
            None,
        ),
        Call(
            "producer:alignment.bam",
            None,
            "fake/test",
            "builder.tier4.v1",
            "b" * 64,
            "MA0005: 'nf-core/salmon' was not offered",
        ),
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


def test_a_registry_gap_is_reported_apart_from_what_a_run_needs(authoring_case):
    picture = _walked_to_the_end_with_hisat2(authoring_case, show_gaps=False)
    receipt = _receipt(picture)
    provide = receipt.split("To run, provide: ", 1)[1].split(".", 1)[0]
    assert "seq_platform" not in provide
    assert "Registry information is incomplete: " in receipt and "seq_platform" in receipt
    assert "registry/tools/" not in receipt
    assert picture["show_gap_details"] is False


def test_dev_mode_adds_the_file_that_would_fix_each_gap(authoring_case):
    picture = _walked_to_the_end_with_hisat2(authoring_case, show_gaps=True)
    assert "registry/tools/nf-core/hisat2/align/contract.yml" in _receipt(picture)
    assert picture["show_gap_details"] is True


def test_a_setting_with_no_listed_values_is_named_on_its_card(authoring_case):
    from mendel_api_tests.canvas_scenarios import with_hisat2

    session_id = with_hisat2()
    for _ in range(20):
        picture = facade.read(session_id)
        pending = picture["pending_proposal"]
        assert pending is not None, "the walk ended before offering HISAT2's aligner"
        if pending["payload"]["node"] == "hisat2_align":
            assert pending["payload"]["block"]["unresolved_settings"] == ["seq_platform"]
            return
        facade.perform(commands.SettleStep(pending["id"], picture["revision"], "ana"))
    raise AssertionError("the walk did not reach HISAT2's aligner")

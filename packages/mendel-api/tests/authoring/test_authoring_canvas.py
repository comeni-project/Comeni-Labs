"""The visible authored graph and its metadata arrive together without extra SQL."""

import pytest
from mendel_api.db import session_scope
from mendel_api.models import PipelineAuthoringSession, PipelineDraft
from mendel_api.services import session as facade
from mendel_api_tests.canvas_scenarios import captured_sql, placed_quietly
from mendel_api_tests.database import reachable
from mendel_authoring import commands
from mendel_compiler import orchestrate

pytestmark = pytest.mark.skipif(not reachable(), reason="run make test-db")

# Statements `session.read` issued for each case before it carried a frame: the frame adds none.
# The three structural-intent families (A1) added one statement each per decisions read — four
# reads paced together, five stopping where needed: 50 → 62 and 62 → 77. Part I.2's not-offered
# notes add one statement per read (`decisions.read_asked`): 62 → 63; stop-where-needed fits in 77.
BASELINE = {"together": 63, "stop_where_needed": 77}


@pytest.mark.parametrize("pacing", ["together", "stop_where_needed"])
def test_pending_aligner_uses_its_upstream_index(authoring_case, pacing, monkeypatch):
    monkeypatch.setenv("COMENI_BUILD_PACING", pacing)
    # Quietly paced, a tier-3 aligner is placed without stopping, so its wiring is checked
    # on the placed graph rather than on an offer.
    session_id = authoring_case.session_id if pacing == "together" else placed_quietly()
    with captured_sql() as sql:
        picture = facade.read(session_id)
    frame = picture.get("canvas")
    assert isinstance(frame, dict), "session has no coherent authored canvas"
    assert len(sql) <= BASELINE[pacing], sql
    assert all("preview_views" not in statement for statement in sql)
    assert any(
        e["from_node"] == "star_genomegenerate" and e["to_node"] == "star_align"
        for e in frame["graph"]["edges"]
    )
    assert not any(c["type_id"] == "genome.index.star" for c in frame["channels"])
    assert not any(
        c["type_id"] == "fastq.reads" and "trimmed" in c["states"] for c in frame["channels"]
    )
    assert any(c["type_id"] == "annotation.gtf" for c in frame["channels"])
    star = next(s for s in frame["steps"] if s["id"] == "star_align")
    assert star["tier"] == 3
    assert star["settings"] and star["ports"]


def test_reoffering_existing_node_draws_it_once(authoring_case):
    with session_scope() as db:
        row = db.get(PipelineAuthoringSession, authoring_case.session_id)
        draft = db.get(PipelineDraft, row.draft_id)
        graph = dict(draft.graph)
        graph["nodes"] = [
            *graph["nodes"],
            {"id": "star_align", "contract_id": "nf-core/star/align@2.7.11b", "params": []},
        ]
        draft.graph = graph
    frame = facade.read(authoring_case.session_id).get("canvas")
    assert frame is not None
    assert [n["id"] for n in frame["graph"]["nodes"]].count("star_align") == 1


def test_stale_frame_is_marked_without_hiding_the_last_graph(authoring_case):
    with session_scope() as db:
        row = db.get(PipelineAuthoringSession, authoring_case.session_id)
        db.get(PipelineDraft, row.draft_id).projection_current = False
    frame = facade.read(authoring_case.session_id).get("canvas")
    assert frame is not None and not frame["current"]
    assert frame["graph"]["nodes"]


def test_a_drawn_graph_uses_its_actual_contract_and_provenance(authoring_case):
    """Nothing planned yet (#395: a pipeline drawn by hand, its reading not yet confirmed): the
    frame is the graph as drawn."""
    with session_scope() as db:
        row = db.get(PipelineAuthoringSession, authoring_case.session_id)
        row.blueprint = {}
        draft = db.get(PipelineDraft, row.draft_id)
        draft.graph = {
            "nodes": [
                {"id": "star_genomegenerate", "contract_id": "nf-core/fastqc@0.12.1", "params": []}
            ],
            "edges": [],
        }
        draft.provenance = {}
    frame = facade.read(authoring_case.session_id).get("canvas")
    assert frame is not None
    [step] = frame["steps"]
    assert step["contract_id"] == "nf-core/fastqc@0.12.1" and step["tier"] == 4


def test_offer_frame_shows_only_visible_steps_and_entry_scopes(authoring_case, monkeypatch):
    def refuse(*_args, **_kwargs):
        raise AssertionError("an authored read re-resolved the goal")

    monkeypatch.setattr(orchestrate, "build", refuse)
    frame = facade.read(authoring_case.session_id)["canvas"]
    drawn = {n["id"] for n in frame["graph"]["nodes"]}
    assert drawn == {"star_genomegenerate", "trimgalore", "star_align"}
    assert {s["id"] for s in frame["steps"]} == drawn == set(frame["placement"])
    by_type = {c["type_id"]: c for c in frame["channels"]}
    gtf, reads = by_type["annotation.gtf"], by_type["fastq.reads"]
    assert gtf["scope"] == "run" and gtf["count"] is None
    assert sorted(gtf["ports"]) == ["star_align.gtf", "star_genomegenerate.gtf"]
    assert reads["scope"] == "sample" and reads["count"]


def test_a_drawn_graph_keeps_its_recorded_tier(authoring_case):
    with session_scope() as db:
        row = db.get(PipelineAuthoringSession, authoring_case.session_id)
        row.blueprint = {}
        draft = db.get(PipelineDraft, row.draft_id)
        draft.graph = {
            "nodes": [{"id": "qc", "contract_id": "nf-core/fastqc@0.12.1", "params": []}],
            "edges": [],
        }
        draft.provenance = {
            "nodes": [
                {
                    "node": "qc",
                    "selection": {"source": "human", "tier": 1, "reason": "chosen on the canvas"},
                }
            ]
        }
    frame = facade.read(authoring_case.session_id).get("canvas")
    assert frame is not None
    [step] = frame["steps"]
    assert step["contract_id"] == "nf-core/fastqc@0.12.1" and step["tier"] == 1


def test_progress_counts_the_plan_not_the_proposals(authoring_case):
    picture = facade.read(authoring_case.session_id)
    order = [
        "star_genomegenerate",
        "trimgalore",
        "star_align",
        "samtools_sort",
        "subread_featurecounts",
    ]
    active = {"position": 3, "total": len(order), "again": False}
    assert picture["progress"] == {"reviewed": 2, "total": len(order), "active": active,
                                   "upcoming": [{"node": "samtools_sort", "position": 4},
                                                {"node": "subread_featurecounts", "position": 5}]}
    assert picture["pending_proposal"]["payload"]["progress"] == active


def test_a_swap_keeps_the_original_offer_position_in_history(authoring_case):
    facade.perform(
        commands.Amend(authoring_case.proposal_id, authoring_case.option_id, None, "ana")
    )
    picture = facade.read(authoring_case.session_id)
    [swapped] = [h for h in picture["history"] if h["id"] == authoring_case.proposal_id]
    assert swapped["envelope"]["progress"] == {"position": 3, "total": 5, "again": False}
    # HISAT2 brings its own index, offered first; STAR's index review no longer counts.
    assert picture["pending_proposal"]["payload"]["node"] == "hisat2_build"
    assert picture["progress"] == {
        "reviewed": 1,
        "total": 5,
        "active": {"position": 1, "total": 5, "again": False},
        # The aligner chosen in the swap holds its review, so it is not ahead of the person though
        # the plan puts it after the offer; TrimGalore's no longer holds, so it is.
        "upcoming": [{"node": "trimgalore", "position": 2},
                     {"node": "samtools_sort", "position": 4},
                     {"node": "subread_featurecounts", "position": 5}],
    }


def test_a_drawn_graph_has_no_walk_progress(authoring_case):
    with session_scope() as db:
        db.get(PipelineAuthoringSession, authoring_case.session_id).blueprint = {}
    assert facade.read(authoring_case.session_id)["progress"] is None


def test_a_registry_that_lost_a_used_contract_still_reads_the_session(authoring_case, monkeypatch):
    from mendel_api.services import build

    def gone(*_args, **_kwargs):
        raise KeyError("nf-core/star/align@2.7.11b")

    monkeypatch.setattr(build, "step_views", gone)
    picture = facade.read(authoring_case.session_id)
    assert picture["canvas"] is None
    assert picture["pending_proposal"] is not None


def test_dev_mode_off_sends_no_repository_path(authoring_case):
    from mendel_api_tests.canvas_scenarios import with_hisat2

    session_id = with_hisat2()
    for _ in range(20):
        picture = facade.read(session_id)
        pending = picture["pending_proposal"]
        if pending["payload"]["node"] == "hisat2_align":
            break
        facade.perform(commands.SettleStep(pending["id"], picture["revision"], "ana"))
    assert picture["show_gap_details"] is False
    assert "registry/tools/" not in str(picture["pending_proposal"])
    assert "registry/tools/" not in str(picture["history"])
    assert pending["payload"]["block"]["unresolved_settings"] == ["seq_platform"]

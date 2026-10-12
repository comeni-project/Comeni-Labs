"""The visible authored graph and its metadata arrive together without extra SQL."""

import pytest
from mendel_api.db import session_scope
from mendel_api.models import PipelineAuthoringSession, PipelineDraft
from mendel_api.services import session as facade
from mendel_postgres import reachable
from part_g_setup import at_aligner, captured_sql

pytestmark = pytest.mark.skipif(not reachable(), reason="run make test-db")


@pytest.mark.parametrize("pacing", ["together", "stop_where_needed"])
def test_pending_aligner_uses_its_upstream_index(g_case, pacing, monkeypatch):
    monkeypatch.setenv("COMENI_BUILD_PACING", pacing)
    case = g_case if pacing == "together" else at_aligner(pacing)
    with captured_sql() as sql:
        picture = facade.read(case.session_id)
    frame = picture.get("canvas")
    assert isinstance(frame, dict), "session has no coherent authored canvas"
    assert len(sql) <= 50, sql
    assert all("preview_views" not in statement for statement in sql)
    assert any(e["from_node"] == "star_genomegenerate" and e["to_node"] == "star_align"
               for e in frame["graph"]["edges"])
    assert not any(c["type_id"] == "genome.index.star" for c in frame["channels"])
    assert not any(c["type_id"] == "fastq.reads" and "trimmed" in c["states"]
                   for c in frame["channels"])
    assert any(c["type_id"] == "annotation.gtf" for c in frame["channels"])
    star = next(s for s in frame["steps"] if s["id"] == "star_align")
    assert star["tier"] == 3
    assert star["settings"] and star["ports"]


def test_reoffering_existing_node_draws_it_once(g_case):
    with session_scope() as db:
        row = db.get(PipelineAuthoringSession, g_case.session_id)
        draft = db.get(PipelineDraft, row.draft_id)
        graph = dict(draft.graph)
        graph["nodes"] = [*graph["nodes"],
                          {"id": "star_align", "contract_id": "nf-core/star/align@1.11.0",
                           "params": []}]
        draft.graph = graph
    frame = facade.read(g_case.session_id).get("canvas")
    assert frame is not None
    assert [n["id"] for n in frame["graph"]["nodes"]].count("star_align") == 1


def test_stale_frame_is_marked_without_hiding_the_last_graph(g_case):
    with session_scope() as db:
        row = db.get(PipelineAuthoringSession, g_case.session_id)
        db.get(PipelineDraft, row.draft_id).projection_current = False
    frame = facade.read(g_case.session_id).get("canvas")
    assert frame is not None and not frame["current"]
    assert frame["graph"]["nodes"]


def test_manual_same_id_uses_its_actual_contract_and_provenance(g_case):
    with session_scope() as db:
        row = db.get(PipelineAuthoringSession, g_case.session_id)
        draft = db.get(PipelineDraft, row.draft_id)
        draft.ownership = "manual"
        draft.graph = {"nodes": [{"id": "star_genomegenerate",
                                 "contract_id": "nf-core/fastqc@0.12.1", "params": []}],
                       "edges": []}
        draft.provenance = {}
    frame = facade.read(g_case.session_id).get("canvas")
    assert frame is not None
    [step] = frame["steps"]
    assert step["contract_id"] == "nf-core/fastqc@0.12.1" and step["tier"] == 4

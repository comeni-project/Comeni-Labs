"""Saved alternative views: real rows, no model or preview-time resolution."""

from copy import deepcopy

import pytest
from mendel_api.db import session_scope
from mendel_api.models import PipelineAuthoringProposal
from mendel_postgres import reachable
from sqlalchemy import inspect, select
from sqlalchemy.exc import InvalidRequestError

pytestmark = pytest.mark.skipif(not reachable(), reason="run make test-db")


def test_offer_saves_the_complete_alternative(g_case):
    column = getattr(PipelineAuthoringProposal, "preview_views", None)
    with session_scope() as db:
        views = None if column is None else db.scalar(select(column).where(
            PipelineAuthoringProposal.id == g_case.proposal_id))
    assert isinstance(views, dict), "offer discarded its already resolved alternatives"
    saved = views[g_case.option_id]
    frame = saved["frame"]
    ids = {node["id"] for node in frame["graph"]["nodes"]}
    assert {"hisat2_build", "hisat2_align"} <= ids
    assert not {"star_genomegenerate", "star_align"} & ids
    align = next(step for step in frame["steps"] if step["id"] == "hisat2_align")
    assert any(port["type_id"] == "genome.index.hisat2" for port in align["ports"])
    assert any(edge["from_node"] == "hisat2_build" and edge["to_node"] == "hisat2_align"
               for edge in frame["graph"]["edges"])


def test_routine_offer_read_cannot_lazy_load_snapshots(g_case):
    with session_scope() as db:
        proposal = db.get(PipelineAuthoringProposal, g_case.proposal_id)
        assert "preview_views" in inspect(proposal).unloaded
        with pytest.raises(InvalidRequestError):
            _ = proposal.preview_views


@pytest.mark.parametrize("change", ["option", "contract", "context", "proposal"])
def test_snapshot_must_match_its_fixed_offer(g_case, change):
    from sqlalchemy.orm import undefer

    with session_scope() as db:
        proposal = db.scalar(select(PipelineAuthoringProposal).options(
            undefer(PipelineAuthoringProposal.preview_views)
        ).where(PipelineAuthoringProposal.id == g_case.proposal_id))
        views = deepcopy(proposal.preview_views)
        item = views[g_case.option_id]
        if change == "option":
            item["option_id"] = "not_offered"
        elif change == "contract":
            item["contract"] = item["frame"]["steps"][0]["contract_id"]
        elif change == "context":
            item["frame"]["context"]["decision_revision"] += 1
        else:
            item["frame"]["proposal_id"] = "another_proposal"
        with pytest.raises(ValueError):
            proposal.preview_views = views

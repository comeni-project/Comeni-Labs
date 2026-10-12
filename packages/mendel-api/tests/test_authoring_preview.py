"""Saved alternative views: real rows, no model or preview-time resolution."""

from copy import deepcopy

import pytest
from fastapi.testclient import TestClient
from mendel_api.db import session_scope
from mendel_api.main import create_app
from mendel_api.models import PipelineAuthoringProposal
from mendel_api.services import session as facade
from mendel_postgres import reachable
from part_g_setup import captured_sql
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


def preview_request(client, case, *, session=None, option=None, **changes):
    params = dict(expected_revision=case.context.draft_revision,
                  expected_decision_revision=case.context.decision_revision,
                  expected_session_version=case.context.session_version,
                  expected_registry=case.context.registry)
    params.update(changes)
    return client.get(f"/api/pipeline/authoring/{session or case.session_id}/proposals/"
                      f"{case.proposal_id}/alternatives/{option or case.option_id}", params=params)


def test_saved_preview_get_is_one_read_and_changes_nothing(g_case, monkeypatch):
    from mendel_api.services import blueprint

    def forbidden(*_args, **_kwargs):
        raise AssertionError("preview must not re-resolve")

    before = facade.read(g_case.session_id)
    monkeypatch.setattr(blueprint, "resolve", forbidden)
    with captured_sql() as sql:
        response = preview_request(TestClient(create_app()), g_case)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["observed_context"] == g_case.context.model_dump(mode="json")
    assert {"hisat2_align", "hisat2_build"} <= {
        n["id"] for n in body["frame"]["graph"]["nodes"]}
    assert len(sql) == 1, sql
    assert sql[0].lstrip().upper().startswith("SELECT")
    assert facade.read(g_case.session_id) == before


@pytest.mark.parametrize("field", ["expected_revision", "expected_decision_revision",
                                   "expected_session_version", "expected_registry"])
def test_preview_refuses_a_changed_context(g_case, field):
    wrong = "sha256:" + "0" * 64 if field == "expected_registry" else 999
    response = preview_request(TestClient(create_app()), g_case, **{field: wrong})
    assert response.status_code == 422
    assert "MI0201" in response.text


def test_preview_does_not_reveal_another_sessions_offer(g_case):
    assert preview_request(TestClient(create_app()), g_case, session="another").status_code == 404


def test_preview_refuses_unoffered_options(g_case):
    response = preview_request(TestClient(create_app()), g_case, option="keep")
    assert response.status_code == 422 and "MI0205" in response.text


def test_settled_offer_cannot_be_previewed(g_case):
    from mendel_authoring import commands

    facade.perform(commands.SettleStep(g_case.proposal_id, g_case.context.draft_revision, "ana"))
    response = preview_request(TestClient(create_app()), g_case)
    assert response.status_code == 422 and "MI0203" in response.text


def test_older_offer_without_saved_view_stays_acceptible(g_case):
    from mendel_authoring import commands

    with session_scope() as db:
        db.get(PipelineAuthoringProposal, g_case.proposal_id).preview_views = None
    response = preview_request(TestClient(create_app()), g_case)
    assert response.status_code == 422 and "older offer" in response.text
    done = facade.perform(commands.SettleStep(
        g_case.proposal_id, g_case.context.draft_revision, "ana")).result
    assert done.settlement.refusal is None


def test_registry_movement_refuses_preview_without_rewriting_offer(g_case, monkeypatch):
    from mendel_api.services import blueprint

    monkeypatch.setattr(blueprint, "registry_digest", lambda _: "sha256:" + "0" * 64)
    response = preview_request(TestClient(create_app()), g_case)
    assert response.status_code == 422 and "registry" in response.text
    with session_scope() as db:
        assert db.get(PipelineAuthoringProposal, g_case.proposal_id).state == "pending"

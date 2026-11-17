"""Every pipeline has a conversation (one builder, #395): a draft drawn by hand opens with an empty
one, and a draft that has one opens it."""

from concurrent.futures import ThreadPoolExecutor

import pytest
from comeni_core.plan.draft import DraftEdge, DraftGraph, DraftNode
from fastapi.testclient import TestClient
from mendel_api.agent import view
from mendel_api.db import session_scope
from mendel_api.main import create_app
from mendel_api.models import PipelineAuthoringSession
from mendel_api.services import drafts
from mendel_api_tests.building import clean as clean
from mendel_api_tests.database import reachable

pytestmark = pytest.mark.skipif(not reachable(), reason="needs throwaway Postgres")

TRIM = "nf-core/trimgalore@2.3.0"
FASTQC = "nf-core/fastqc@0.12.1"


def _drawn():
    graph = DraftGraph(
        nodes=[DraftNode(id="trim", contract_id=TRIM), DraftNode(id="qc", contract_id=FASTQC)],
        edges=[DraftEdge(from_node="trim", from_port="reads", to_node="qc", to_port="reads")],
    )
    return drafts.create(graph, "drawn", "ana"), graph


def _open(draft_id):
    response = TestClient(create_app()).post(f"/api/pipeline/drafts/{draft_id}/session")
    assert response.status_code == 200, response.text
    return response.json()["session_id"]


def test_opening_a_drawn_draft_starts_an_empty_conversation_that_shows_it(clean):
    draft_id, graph = _drawn()
    picture = view.read(_open(draft_id))
    assert picture["graph"] == graph.model_dump(mode="json")
    assert picture["turns"] == []
    assert picture["canvas"] is not None


def test_opening_a_draft_with_a_session_returns_it(clean):
    draft_id, _ = _drawn()
    first = _open(draft_id)
    assert _open(draft_id) == first


def test_two_opens_at_once_make_one_session(clean):
    """Review Focus 5: two tabs, or a double click."""
    draft_id, _ = _drawn()
    with ThreadPoolExecutor(2) as pool:
        ids = list(pool.map(_open, [draft_id, draft_id]))
    assert ids[0] == ids[1]
    with session_scope() as db:
        assert db.query(PipelineAuthoringSession).filter_by(draft_id=draft_id).count() == 1


def test_an_open_that_loses_the_race_answers_with_the_winner(clean, monkeypatch):
    """The other open commits between this one's look and its insert: the unique index refuses
    the second insert, and it is answered with the session that won."""
    from mendel_api.agent import loop

    draft_id, _ = _drawn()
    winner = _open(draft_id)
    real, looks = loop._existing, []

    def first_look_misses(db, draft):
        looks.append(draft)
        return None if len(looks) == 1 else real(db, draft)

    monkeypatch.setattr(loop, "_existing", first_look_misses)
    assert _open(draft_id) == winner

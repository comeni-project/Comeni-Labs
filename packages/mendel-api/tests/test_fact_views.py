"""The browser restores authoritative facts, scoped history and honest actors."""

from fastapi.testclient import TestClient
from mendel_api.db import session_scope
from mendel_api.main import create_app
from mendel_api.models import PipelineAuthoringProposal, PipelineAuthoringSession
from mendel_api.services import decisions, session
from mendel_authoring import commands as c
from test_authoring_samples import _gathering, _pending_for
from test_authoring_samples import clean as clean
from test_fact_disagreements import _conflict


def test_authoring_get_restores_disagreement_and_current_context(clean):
    sid = _conflict()
    response = TestClient(create_app()).get(f"/api/pipeline/authoring/{sid}")
    assert response.status_code == 200
    view = response.json()
    assert view["pending_proposal"]["kind"] == "disagreement"
    assert view["decision_revision"] > 0 and view["projection_current"] is False
    assert view["ownership"] == "authored" and view["forked_from"] is None
    assert view["inputs"] and view["review_applicability"] == {}


def test_history_scopes_to_session_and_distinguishes_unselected_observations(clean):
    sid = _conflict()
    client = TestClient(create_app())
    response = client.get(f"/api/pipeline/authoring/{sid}/facts/paired/history")
    assert response.status_code == 200
    entries = response.json()["entries"]
    assert any(e["selected"] and e["current"] and e["value"] is False for e in entries)
    assert any(not e["selected"] and e["value"] is True for e in entries)
    assert client.get("/api/pipeline/authoring/missing/facts/paired/history").status_code == 404


def test_a_person_named_resolver_keeps_person_attribution(clean):
    sid = _gathering(["counts.matrix"])
    pid = _pending_for(sid, "paired")
    session.perform(c.AnswerGap(pid, "no", None, "resolver"))
    response = TestClient(create_app()).get(f"/api/pipeline/authoring/{sid}")
    assert response.status_code == 200
    history = response.json()["history"]
    answer = next(d for d in history if d["id"] == pid)
    assert answer["by"] == "resolver" and answer["actor_kind"] == "person"
    with session_scope() as db:
        assert db.get(PipelineAuthoringProposal, pid).actor_kind == "person"
        draft_id = db.get(PipelineAuthoringSession, sid).draft_id
    assert decisions.read(draft_id)


def test_vocabulary_exposes_declarations_for_correction_editors(clean):
    response = TestClient(create_app()).get("/api/pipeline/authoring/vocabulary")
    assert response.status_code == 200
    declaration = response.json()["measurements"]["read_length"]
    assert declaration["kind"] == "integer" and declaration["minimum"] is not None


def test_input_history_preserves_selected_presence_and_retraction(clean):
    from mendel_authoring.decisions import FactOrigin, InputDecision

    sid = _gathering(["counts.matrix"])
    draft_id = session.read(sid)["draft_id"]
    decisions.set_input(draft_id, InputDecision(key="reads", type_id="fastq.reads"), who="ana")
    decisions.set_input(
        draft_id,
        InputDecision(key="reads", type_id="fastq.reads", present=False, origin=FactOrigin.OPEN),
        who="ana",
    )
    response = TestClient(create_app()).get(f"/api/pipeline/authoring/{sid}/facts/reads/history")
    assert response.status_code == 200
    entries = response.json()["entries"]
    assert entries[0]["value"] is True and not entries[0]["current"]
    assert entries[1]["value"] is None and entries[1]["current"]


def test_a_historical_typed_answer_does_not_change_when_the_current_fact_changes(clean):
    sid = _gathering(["counts.matrix"])
    pid = _pending_for(sid, "read_length")
    session.perform(c.AnswerGap(pid, "value", 150, "ana"))
    draft_id = session.read(sid)["draft_id"]
    decisions.set_fact(draft_id, "read_length", 50, who="ana")
    answer = next(d for d in session.read(sid)["history"] if d["id"] == pid)
    assert answer["answer"] == "150"

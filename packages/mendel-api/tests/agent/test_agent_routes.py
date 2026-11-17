"""The agent chat's API (#463): start, say, answer, retry, review; the scripted routes are gone."""

import pytest
from comeni_ai.agent import AgentReply, ScriptedAgentTransport, ToolCall
from fastapi.testclient import TestClient
from mendel_api import jobs
from mendel_api.agent import loop
from mendel_api.main import create_app
from mendel_api_tests.building import clean as clean
from mendel_api_tests.database import reachable

pytestmark = pytest.mark.skipif(not reachable(), reason="no database")

BASE = "/api/pipeline/authoring"
HISAT2 = "nf-core/hisat2/align@2.2.2"


@pytest.fixture
def queued(monkeypatch):
    seen: list[tuple] = []

    async def enqueue(name, *args, job_id=None, queue=jobs.DEFAULT_QUEUE, expires=None):
        seen.append((name, args, job_id, queue))
        return True

    monkeypatch.setattr(jobs, "enqueue", enqueue)
    return seen


async def _queued() -> bool:
    return True


def _answer(monkeypatch, replies, session_id, seq):
    monkeypatch.setattr(loop, "model_access", lambda: object())
    loop.run_turn(session_id, seq, transport=ScriptedAgentTransport(replies))


def test_starting_writes_the_persons_turn_and_queues_the_agent(clean, queued):
    started = TestClient(create_app()).post(BASE, json={"prompt": "gene counts from RNA-seq"})
    assert started.status_code == 201, started.text
    body = started.json()
    session = body["session"]
    assert [(t["role"], t["state"]) for t in session["turns"]] == [
        ("person", "answered"), ("assistant", "pending")]
    assert session["working"] is True
    [(name, args, job_id, queue)] = queued
    assert name == "run_builder_turn" and args == (session["id"], 1) and queue == jobs.AI_QUEUE
    assert job_id == f"builder:agent:{session['id']}:1"


def test_answering_a_question_queues_the_next_turn(clean, queued, monkeypatch):
    client = TestClient(create_app())
    session = client.post(BASE, json={"prompt": "counts"}).json()["session"]
    _answer(monkeypatch, [AgentReply(calls=[ToolCall(id="c", name="ask", arguments={
        "question": "Paired?", "shape": "yes_no"})])], session["id"], 1)
    read = client.get(f"{BASE}/{session['id']}").json()
    [asked] = [b for t in read["turns"] for b in t["blocks"] if b["kind"] == "ask"]
    answered = client.post(f"{BASE}/{session['id']}/questions/{asked['question_id']}",
                           json={"value": "yes"})
    assert answered.status_code == 202, answered.text
    assert queued[-1][1] == (session["id"], 3)
    turns = client.get(f"{BASE}/{session['id']}").json()["turns"]
    assert turns[2]["role"] == "person" and "yes" in turns[2]["text"].lower()


def test_retry_requeues_only_a_failed_turn(clean, queued, monkeypatch):
    client = TestClient(create_app())
    session = client.post(BASE, json={"prompt": "counts"}).json()["session"]
    _answer(monkeypatch, [_reply("Done")], session["id"], 1)
    assert client.post(f"{BASE}/{session['id']}/turns/1/retry").status_code == 409

    class Down:
        def converse(self, access, messages, tools, *, tool_choice=None):
            raise TimeoutError("MA0003: no answer")

    seq = client.post(f"{BASE}/{session['id']}/messages", json={"text": "again"}).json()["seq"]
    monkeypatch.setattr(loop, "model_access", lambda: object())
    loop.run_turn(session["id"], seq, transport=Down())
    retried = client.post(f"{BASE}/{session['id']}/turns/{seq}/retry")
    assert retried.status_code == 202, retried.text
    assert queued[-1][1] == (session["id"], seq)
    turn = next(t for t in client.get(f"{BASE}/{session['id']}").json()["turns"]
                if t["seq"] == seq)
    assert turn["state"] == "pending"


def test_reviewing_clears_the_ai_marks(clean, queued, monkeypatch):
    client = TestClient(create_app())
    session = client.post(BASE, json={"prompt": "counts"}).json()["session"]
    from mendel_api.services import decisions
    from mendel_resolver.goal import Goal
    from support.example import example_mapping

    decisions.import_goal(session["draft_id"], Goal.model_validate(example_mapping()), who="ana")
    _answer(monkeypatch, [
        AgentReply(calls=[ToolCall(id="r", name="read_goal", arguments={})]),
        AgentReply(calls=[ToolCall(id="c", name="choose_tool", arguments={
            "type_id": "alignment.bam", "contract": HISAT2, "because": "less memory"})]),
        AgentReply(calls=[ToolCall(id="b", name="resolve", arguments={})]),
        _reply("Built with HISAT2."),
    ], session["id"], 1)
    marked = client.get(f"{BASE}/{session['id']}").json()["ai_unreviewed"]
    assert any(m["node"] == "hisat2_align" for m in marked), marked
    # The card says why, in the AI's words (walk 2026-11-15).
    [hisat] = [m for m in marked if m["node"] == "hisat2_align"]
    assert "less memory" in hisat["because"], hisat
    assert client.post(f"{BASE}/{session['id']}/reviewed", json={"nodes": "all"}).status_code == 200
    assert client.get(f"{BASE}/{session['id']}").json()["ai_unreviewed"] == []


def test_a_turn_that_cannot_be_queued_fails_and_can_be_retried(clean, queued, monkeypatch):
    """#463 review: with the queue down, the agent's turn must not wait for a job that never
    comes; it fails at once, coded, and Retry is offered."""
    async def down(*args, **kwargs):
        raise ConnectionError("redis is down")

    monkeypatch.setattr(jobs, "enqueue", down)
    client = TestClient(create_app())
    started = client.post(BASE, json={"prompt": "counts"})
    assert started.status_code == 201, started.text
    session = started.json()["session"]
    read = client.get(f"{BASE}/{session['id']}").json()
    last = read["turns"][-1]
    assert last["state"] == "failed" and read["working"] is False
    assert [b["code"] for b in last["blocks"] if b["kind"] == "notice"] == ["MI0220"]
    monkeypatch.setattr(jobs, "enqueue", lambda *a, **k: _queued())
    retried = client.post(f"{BASE}/{session['id']}/turns/{last['seq']}/retry")
    assert retried.status_code == 202, retried.text


def test_a_turn_whose_worker_died_is_failed_when_the_page_reads_it(clean, queued, monkeypatch):
    """#463 review: a worker killed mid-turn writes nothing, so the turn would stay pending and
    the page would poll for good. Read after a grace period with no job queued or running, it
    is failed, coded, and Retry is offered."""
    from datetime import timedelta

    from mendel_api.db import session_scope
    from mendel_api.models import PipelineAuthoringTurn
    from sqlalchemy import select

    client = TestClient(create_app())
    session = client.post(BASE, json={"prompt": "counts"}).json()["session"]

    async def gone(job_id, queue=jobs.DEFAULT_QUEUE):
        return False

    monkeypatch.setattr(jobs, "running", gone)
    assert client.get(f"{BASE}/{session['id']}").json()["working"] is True, \
        "a turn just started is given time for its job to begin"
    with session_scope() as db:
        turn = db.scalar(select(PipelineAuthoringTurn).where(
            PipelineAuthoringTurn.session_id == session["id"], PipelineAuthoringTurn.seq == 1))
        turn.at = turn.at - timedelta(minutes=5)
    read = client.get(f"{BASE}/{session['id']}").json()
    assert read["working"] is False and read["turns"][-1]["state"] == "failed"
    assert [b["code"] for b in read["turns"][-1]["blocks"]] == ["MI0220"]


def test_the_scripted_flow_routes_are_gone(clean, queued):
    client = TestClient(create_app())
    session = client.post(BASE, json={"prompt": "counts"}).json()["session"]
    for path in (f"/{session['id']}/proposals/p/decide", f"/{session['id']}/retry",
                 f"/{session['id']}/suggestions/s", f"/{session['id']}/disagreements/p"):
        assert client.post(BASE + path, json={}).status_code in (404, 405), path


def _reply(message):
    return AgentReply(calls=[ToolCall(id="final", name="reply", arguments={"message": message})])

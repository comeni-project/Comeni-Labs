"""A kept pipeline says what the AI chose and whether anyone reviewed it (#463). Review never
blocks keeping."""

import pytest
import yaml
from comeni_ai.agent import AgentReply, ScriptedAgentTransport, ToolCall
from fastapi.testclient import TestClient
from mendel_api import jobs
from mendel_api.agent import loop
from mendel_api.main import create_app
from mendel_api.services import decisions
from mendel_api_tests.building import clean as clean
from mendel_api_tests.database import reachable
from mendel_resolver.goal import Goal
from support.example import example_mapping

pytestmark = pytest.mark.skipif(not reachable(), reason="no database")

BASE = "/api/pipeline/authoring"
HISAT2 = "nf-core/hisat2/align@2.2.2"


@pytest.fixture
def built(clean, monkeypatch):
    """A session whose agent chose HISAT2 over the rule's tool and built the pipeline."""
    async def enqueue(name, *args, job_id=None, queue=jobs.DEFAULT_QUEUE, expires=None):
        return True

    monkeypatch.setattr(jobs, "enqueue", enqueue)
    client = TestClient(create_app())
    session = client.post(BASE, json={"prompt": "counts"}).json()["session"]
    decisions.import_goal(session["draft_id"], Goal.model_validate(example_mapping()), who="ana")
    monkeypatch.setattr(loop, "model_access", lambda: object())
    loop.run_turn(session["id"], 1, transport=ScriptedAgentTransport([
        AgentReply(calls=[ToolCall(id="c", name="choose_tool", arguments={
            "type_id": "alignment.bam", "contract": HISAT2, "because": "less memory"})]),
        AgentReply(calls=[ToolCall(id="b", name="resolve", arguments={})]),
        _reply("Built with HISAT2."),
    ]))
    return client, session


def _kept(client, session) -> dict:
    kept = client.post(f"/api/pipeline/drafts/{session['draft_id']}/keep")
    assert kept.status_code == 200, kept.text
    with open(kept.json()["path"]) as f:
        return yaml.safe_load(f)


def test_keeping_with_unreviewed_ai_choices_works_and_records_them(built):
    client, session = built
    choices = _kept(client, session)["ai_choices"]
    assert choices, "the AI's tool choice is recorded"
    hisat = [c for c in choices if c["node"] == "hisat2_align"]
    assert hisat and hisat[0]["what"] == f"chose {HISAT2}"
    assert hisat[0]["reviewed"] is False
    assert choices == sorted(choices, key=lambda c: (c["node"], c["what"]))


def test_looks_right_marks_every_choice_reviewed(built):
    client, session = built
    assert client.post(f"{BASE}/{session['id']}/reviewed", json={"nodes": "all"}).status_code == 200
    choices = _kept(client, session)["ai_choices"]
    assert choices and all(c["reviewed"] is True for c in choices)


def test_a_pipeline_drawn_by_hand_records_no_ai_choices(clean):
    client = TestClient(create_app())
    draft = client.post("/api/pipeline/drafts", json={"name": "by hand", "graph": {
        "nodes": [{"id": "fastqc", "contract_id": "nf-core/fastqc@0.12.1", "params": []}],
        "edges": []}})
    assert draft.status_code in (200, 201), draft.text
    kept = client.post(f"/api/pipeline/drafts/{draft.json()['id']}/keep")
    assert kept.status_code == 200, kept.text
    with open(kept.json()["path"]) as f:
        assert "ai_choices" not in yaml.safe_load(f)


def _reply(message):
    return AgentReply(calls=[ToolCall(id="final", name="reply", arguments={"message": message})])

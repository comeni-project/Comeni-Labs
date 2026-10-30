"""Adaptations over HTTP: started from the catalogue, moved only by a person's commands (§6)."""

import pytest
import sqlalchemy as sa
from fastapi.testclient import TestClient
from mendel_api.db import session_scope
from mendel_api.main import create_app
from mendel_api.services import catalogue
from mendel_api_tests.catalogue import FakeSource
from mendel_api_tests.database import reachable

pytestmark = pytest.mark.skipif(not reachable(), reason="no database")


@pytest.fixture
def client() -> TestClient:
    with session_scope() as db:
        for table in ("forge_message", "forge_revision", "forge_item", "forge_adaptation",
                      "catalogue_module", "catalogue_sync"):
            db.execute(sa.text(f"DELETE FROM {table}"))
    catalogue.run_sync(FakeSource(["star/align", "bwa/mem"]))
    return TestClient(create_app())


def _start(client, path="bwa/mem", **extra) -> dict:
    answer = client.post("/api/forge/adaptations",
                         json={"source": "nf-core", "path": path, **extra})
    assert answer.status_code == 201, answer.text
    return answer.json()


def _command(client, id, **body):
    return client.post(f"/api/forge/adaptations/{id}/commands", json=body)


def test_start_creates_an_adaptation_for_the_module(client):
    started = _start(client)
    assert started["path"] == "bwa/mem" and started["version"] == "0.7.19"
    assert started["next_piece"] == "questions"
    listed = client.get("/api/forge/adaptations").json()
    assert [a["id"] for a in listed["adaptations"]] == [started["id"]]


def test_a_reforge_starts_from_the_registry_contract_as_proposals(client):
    started = _start(client, "star/align", reforge="nf-core/star/align@2.7.11b")
    items = {i["key"]: i for i in started["items"]}
    assert items["contract:input:reads"]["status"] == "proposed"
    assert items["contract:input:reads"]["revisions"][0]["actor"] == "registry"


def test_a_person_command_appends_a_revision(client):
    started = _start(client)
    answer = _command(client, started["id"], move="answer", item="questions:role",
                      value={"choice": "alignment"})
    assert answer.status_code == 200, answer.text
    item = next(i for i in answer.json()["items"] if i["key"] == "questions:role")
    assert item["status"] == "approved"
    assert item["revisions"][0]["by"], "the person is recorded"


def test_a_body_cannot_claim_to_be_the_ai(client):
    """The API sets the actor; a body naming one is refused and changes nothing."""
    started = _start(client)
    answer = _command(client, started["id"], move="answer", item="questions:role",
                      value={"choice": "alignment"}, actor="ai")
    assert answer.status_code == 422
    assert client.get(f"/api/forge/adaptations/{started['id']}").json()["items"] == []


def test_a_person_cannot_issue_an_ai_move(client):
    started = _start(client)
    answer = _command(client, started["id"], move="draft", item="questions:role", value={})
    assert answer.status_code == 422
    assert answer.json()["detail"].startswith("MF0506")


def test_two_commands_against_one_revision_the_second_is_refused(client):
    started = _start(client, "star/align", reforge="nf-core/star/align@2.7.11b")
    first = _command(client, started["id"], move="reject", item="contract:input:reads",
                     expected=1)
    assert first.status_code == 200, first.text
    second = _command(client, started["id"], move="reject", item="contract:input:reads",
                      expected=1)
    assert second.status_code == 422
    assert second.json()["detail"].startswith("MF0506")


def test_abandon_keeps_the_rows(client):
    started = _start(client)
    _command(client, started["id"], move="answer", item="questions:role",
             value={"choice": "alignment"})
    assert client.delete(f"/api/forge/adaptations/{started['id']}").status_code == 204
    assert client.get("/api/forge/adaptations").json()["adaptations"] == []
    kept = client.get(f"/api/forge/adaptations/{started['id']}").json()
    assert kept["abandoned_at"] is not None and kept["items"]


def test_an_unknown_adaptation_is_MF0510(client):
    answer = client.get("/api/forge/adaptations/nope")
    assert answer.status_code == 404
    assert answer.json()["detail"].startswith("MF0510")


def test_a_message_is_stored_and_queued(client, monkeypatch):
    from mendel_api import jobs

    queued = []

    async def fake(name, *args, **kwargs):
        queued.append((name, args))
        return True

    monkeypatch.setattr(jobs, "enqueue", fake)
    started = _start(client)
    answer = client.post(f"/api/forge/adaptations/{started['id']}/messages",
                         json={"content": "Why bwa?", "item": None})
    assert answer.status_code == 202, answer.text
    assert queued and queued[0][0] == "answer_forge_message"
    messages = client.get(f"/api/forge/adaptations/{started['id']}").json()["messages"]
    assert [m["content"] for m in messages] == ["Why bwa?"]

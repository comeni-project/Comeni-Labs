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
        for table in ("forge_review", "forge_pull_request", "forge_test_run", "forge_step",
                      "forge_message", "forge_revision",
                      "forge_item",
                      "forge_adaptation",
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


def test_constructor_fields_come_from_command_models_and_source_channels(
    client, tmp_path, monkeypatch,
):
    import shutil

    from mendel_api.services import forge_constructors
    from mendel_api.settings import settings
    from mendel_api_tests.catalogue import FIXTURES
    from mendel_forge.forging.values import Answer, value_model
    from pydantic import TypeAdapter

    monkeypatch.setattr(settings, "forge_cache", tmp_path)
    shutil.copytree(FIXTURES / "bwa/mem",
                    tmp_path / "nf-core-modules/modules/nf-core/bwa/mem")
    started = _start(client)
    response = client.get(f"/api/forge/adaptations/{started['id']}/constructors")
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["inputs"] and data["outputs"]
    assert "reads" in data["inputs"]
    assert "bam" in data["outputs"]
    constructors = {entry["family"]: entry for entry in data["kinds"]}
    assert set(constructors) >= {family for family, _, _ in forge_constructors.KINDS}
    for family, _, _ in forge_constructors.KINDS:
        model = Answer if family.startswith("questions:") else value_model(family)
        assert constructors[family]["fields"] == TypeAdapter(model).json_schema()
    assert client.get("/api/forge/adaptations/absent/constructors").status_code == 404


def test_constructor_fixture_tracks_the_fields_the_browser_renders():
    import json

    from mendel_api.services.forge_constructors import kinds
    from support.paths import ROOT

    fixture = ROOT / "frontend/src/registry/forging/constructors.fixture.json"
    assert json.loads(fixture.read_text())["kinds"] == [k.model_dump(mode="json") for k in kinds()]


def test_forging_progress_excludes_removed_items(client):
    started = _start(client)
    adaptation_id = started["id"]
    for key, choice in (("questions:role", "alignment"),
                        ("questions:input_type:reads", "fastq.reads")):
        response = _command(client, adaptation_id, move="answer", item=key,
                            value={"choice": choice})
        assert response.status_code == 200, response.text
    response = _command(client, adaptation_id, move="remove", item="questions:input_type:reads",
                        expected=1)
    assert response.status_code == 200, response.text
    summary = client.get("/api/forge/adaptations").json()["adaptations"][0]
    assert summary["approved"] == summary["total"] == 1
    assert summary["waiting"] == 0


def test_constructor_options_obey_the_required_test_piece():
    from mendel_api.services.forge_constructors import kinds

    families = {kind.family for kind in kinds()}
    assert "tests:test" in families
    assert "tests:none" not in families
    assert {"parameters:none", "vocabulary:none", "rules:none"} <= families


def test_constructor_source_hints_are_empty_when_source_is_unavailable(
    client, tmp_path, monkeypatch,
):
    from mendel_api.settings import settings

    monkeypatch.setattr(settings, "forge_cache", tmp_path)
    started = _start(client)
    response = client.get(f"/api/forge/adaptations/{started['id']}/constructors")
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["kinds"]
    assert data["inputs"] == data["outputs"] == []

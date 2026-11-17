"""What the person does directly beside the agent (#463): a change, a canvas edit, an upload."""

import pytest
from fastapi.testclient import TestClient
from mendel_api import jobs
from mendel_api.main import create_app
from mendel_api.services import decisions
from mendel_api_tests.building import clean as clean
from mendel_api_tests.database import reachable
from mendel_resolver.goal import Goal
from support.example import example_mapping
from support.paths import ROOT

pytestmark = pytest.mark.skipif(not reachable(), reason="no database")

BASE = "/api/pipeline/authoring"
FIX = ROOT / "registry/measurers/formats/fastq/piece/fixtures"


@pytest.fixture
def started(monkeypatch):
    async def enqueue(name, *args, job_id=None, queue=jobs.DEFAULT_QUEUE, expires=None):
        return True

    monkeypatch.setattr(jobs, "enqueue", enqueue)
    client = TestClient(create_app())
    session = client.post(BASE, json={"prompt": "gene counts"}).json()["session"]
    decisions.import_goal(session["draft_id"], Goal.model_validate(example_mapping()), who="ana")
    return client, session


def test_a_persons_change_rebuilds_the_pipeline(clean, started):
    client, session = started
    changed = client.post(f"{BASE}/{session['id']}/changes", json={"change": {
        "kind": "parameter", "subject": "min_mqs", "value": 10}})
    assert changed.status_code == 200, changed.text
    body = changed.json()
    assert body["moved"] is True
    assert body["session"]["canvas"] is not None, "the canvas follows the change"
    [value] = [p for p in decisions.read(session["draft_id"]).parameters if p.name == "min_mqs"]
    assert (value.value, value.by) == (10, "person")


def test_a_change_against_a_moved_revision_is_refused(clean, started):
    client, session = started
    stale = client.post(f"{BASE}/{session['id']}/changes", json={
        "change": {"kind": "parameter", "subject": "min_mqs", "value": 10},
        "expected_decision_revision": 0})
    assert stale.status_code == 422 and "MI0201" in stale.text


def test_a_value_typed_on_the_canvas_is_the_persons(clean, started):
    client, session = started
    built = client.post(f"{BASE}/{session['id']}/changes", json={"change": {
        "kind": "parameter", "subject": "min_mqs", "value": 10}}).json()["session"]
    graph = built["graph"]
    counts = next(n for n in graph["nodes"] if n["id"] == "subread_featurecounts")
    counts["params"] = [{"name": "min_mqs", "value": 20}]
    edited = client.post(f"{BASE}/{session['id']}/edits",
                         json={"graph": graph, "expected_revision": built["revision"]})
    assert edited.status_code == 200, edited.text
    [value] = [p for p in decisions.read(session["draft_id"]).parameters if p.name == "min_mqs"]
    assert value.value == 20

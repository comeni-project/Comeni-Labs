"""A canvas edit cannot overwrite the revision another browser tab just saved."""

from copy import deepcopy

from fastapi.testclient import TestClient
from mendel_api.main import create_app
from mendel_api.services import session
from test_correction_forks import _manual
from test_correction_forks import clean as clean


def test_a_public_edit_requires_the_revision_it_was_based_on(clean):
    sid = _manual()
    before = session.read(sid)
    response = TestClient(create_app()).post(
        f"/api/pipeline/authoring/{sid}/edits", json={"graph": before["graph"]}
    )
    assert response.status_code == 422
    assert session.read(sid) == before


def test_the_second_tab_cannot_overwrite_a_newer_authoring_edit(clean):
    sid = _manual()
    before = session.read(sid)
    graph = deepcopy(before["graph"])
    graph["nodes"] = graph["nodes"][:-1]
    ids = {node["id"] for node in graph["nodes"]}
    graph["edges"] = [e for e in graph["edges"] if e["from_node"] in ids and e["to_node"] in ids]
    client = TestClient(create_app())
    saved = client.post(f"/api/pipeline/authoring/{sid}/edits", json={
        "graph": graph, "expected_revision": before["revision"],
    })
    assert saved.status_code == 200, saved.text
    after = session.read(sid)
    stale = client.post(f"/api/pipeline/authoring/{sid}/edits", json={
        "graph": before["graph"], "expected_revision": before["revision"],
    })
    assert stale.status_code == 422 and stale.json()["detail"].startswith("MI0201")
    assert session.read(sid) == after

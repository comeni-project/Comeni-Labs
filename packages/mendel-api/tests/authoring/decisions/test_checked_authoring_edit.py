"""A canvas edit cannot overwrite the revision another browser tab just saved."""

from copy import deepcopy

from fastapi.testclient import TestClient
from mendel_api.main import create_app
from mendel_api.services import session
from mendel_api_tests.building import _answer_all, _resolving, authoring_setup
from mendel_api_tests.building import clean as clean


def _manual():
    """A walked session, edited by hand from here on."""
    sid = _resolving()
    _answer_all(sid, authoring_setup.start_building(sid))
    return sid


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
    # A typed value is the edit that saves at once (#395); a structural one only offers.
    graph = deepcopy(before["graph"])
    star = next(n for n in graph["nodes"] if n["id"] == "star_align")
    star["params"] = [*star["params"], {"name": "seq_platform", "value": "ILLUMINA"}]
    client = TestClient(create_app())
    saved = client.post(
        f"/api/pipeline/authoring/{sid}/edits",
        json={
            "graph": graph,
            "expected_revision": before["revision"],
        },
    )
    assert saved.status_code == 200, saved.text
    after = session.read(sid)
    stale = client.post(
        f"/api/pipeline/authoring/{sid}/edits",
        json={
            "graph": before["graph"],
            "expected_revision": before["revision"],
        },
    )
    assert stale.status_code == 422 and stale.json()["detail"].startswith("MI0201")
    assert session.read(sid) == after

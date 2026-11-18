"""The data routes keep their blocking work off the event loop (#560).

The API is one process with one event loop, so a database query, a file read or an inspection
subprocess run on it makes every other request wait, the page's 1.5 s polls included. Each
blocking call these routes make is wrapped here to fail when it runs on the loop thread."""

import asyncio

import pytest
from mendel_api.routes import data as data_routes
from mendel_api.services import decisions, inspect
from mendel_api_tests.building import clean as clean
from mendel_api_tests.data import draft, pairs, tick
from mendel_api_tests.database import reachable

pytestmark = pytest.mark.skipif(not reachable(), reason="no database")


def _off_the_loop(real, name, ran):
    def guarded(*args, **kwargs):
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            ran.append(name)
            return real(*args, **kwargs)
        raise AssertionError(f"{name} ran on the event loop")
    return guarded


@pytest.fixture
def watched(monkeypatch):
    ran: list[str] = []
    for owner, name in ((data_routes, "session_scope"), (decisions, "data_changed"),
                        (inspect, "inspect_sample"), (data_routes.roots, "inside_roots"),
                        (data_routes.roots, "inside_folder")):
        monkeypatch.setattr(owner, name, _off_the_loop(getattr(owner, name), name, ran))
    return ran


def test_the_data_routes_do_their_blocking_work_off_the_event_loop(clean, client, root, watched):
    d = draft(client)
    folder = pairs(root / "liver", "L01")
    (folder / "genome.fasta").write_text(">chrI\nACGT\n")
    calls = [
        lambda: tick(client, d, folder),
        lambda: client.put(f"/api/data/{d}/rule", json={"pattern": None}),
        lambda: client.post(f"/api/data/{d}/rescan"),
        lambda: client.post(f"/api/data/{d}/references", json={
            "path": str(folder / "genome.fasta"), "type_id": "genome.fasta"}),
        lambda: client.delete(f"/api/data/{d}/references/0"),
    ]
    for call in calls:
        answered = call()
        assert answered.status_code == 200, answered.text
    assert {"session_scope", "data_changed", "inspect_sample", "inside_roots",
            "inside_folder"} <= set(watched), "a wrapped call never ran: this proves nothing"

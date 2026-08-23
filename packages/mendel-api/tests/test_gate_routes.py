"""Starting a gate and polling it, over HTTP.

Two thin routes. What is tested here is the wiring, the boundary rule, and that the work
actually leaves the request — the gate's own logic has its own tests, without HTTP.
"""

from datetime import UTC, datetime

from comeni_core.artifact.gates import Gate
from fastapi.testclient import TestClient
from mendel_api import jobs
from mendel_api.main import create_app
from mendel_api.routes import build as build_routes
from mendel_api.services.gates import GateView

QUEUED = GateView(
    id="run-1",
    gate=Gate.LINT,
    state="queued",
    output="",
    queued_at=datetime(2026, 8, 23, tzinfo=UTC),
    finished_at=None,
)


def _client(monkeypatch, sent):
    async def _capture(name, *args):
        sent.append((name, args))

    monkeypatch.setattr(jobs, "enqueue", _capture)
    monkeypatch.setattr(
        build_routes.gate_service, "request", lambda draft_id, gate, who: "run-1"
    )
    monkeypatch.setattr(build_routes.gate_service, "read", lambda run_id: QUEUED)
    return TestClient(create_app(), raise_server_exceptions=False)


def test_starting_a_gate_returns_a_queued_run_and_enqueues_exactly_once(monkeypatch):
    """The route writes a row and hands the work away. It must not run a gate itself: a stub
    gate is up to 900s cold, and `worker.py`'s docstring already says where that belongs.

    `jobs.enqueue` is patched rather than Redis, for the reason `services/drafts.py` records
    about its own seams — CI has neither Redis nor Postgres.
    """
    sent = []
    response = _client(monkeypatch, sent).post(
        "/api/pipeline/drafts/abc/gate", json={"gate": "lint"}
    )

    assert response.status_code == 200
    assert response.json()["state"] == "queued"
    assert sent == [("run_gate_job", ("run-1",))], "the job was not queued exactly once"


def test_the_gate_request_carries_a_gate_and_nothing_else(monkeypatch):
    """Invariant 15, and `docs/design/execution-boundary.md` §3: the test for whether something
    is a *run* rather than a *gate* is whether it takes a samplesheet.

    `tests/test_mount.py` holds the general rule that no request body carries a path. This is
    the specific one — a gate names a DRAFT by opaque id, and the day this schema grows a
    second field somebody should have to look at this test.
    """
    schema = _client(monkeypatch, []).get("/openapi.json").json()
    props = schema["components"]["schemas"]["GateIn"]["properties"]
    assert set(props) == {"gate"}, f"GateIn carries more than a gate: {set(props)}"


def test_an_unknown_run_is_a_404_rather_than_a_500(monkeypatch):
    def missing(run_id):
        raise KeyError(run_id)

    monkeypatch.setattr(build_routes.gate_service, "read", missing)
    client = TestClient(create_app(), raise_server_exceptions=False)
    assert client.get("/api/pipeline/gates/nope").status_code == 404

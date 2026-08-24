"""The live socket. §7.2's handoff, from the subscriber's side."""

import json as _json
from pathlib import Path

import pytest
from starlette.websockets import WebSocketDisconnect

FIXTURE = Path(__file__).parents[3] / "tests/fixtures/weblog/failing-run.jsonl"


def _bodies() -> list[dict]:
    return [_json.loads(line) for line in FIXTURE.read_text().splitlines() if line.strip()]


@pytest.fixture
def a_run_with_events(client, a_bundle, session):
    """A run whose record and tail both hold the whole capture."""
    from wiener_api.services import projection

    artifact = client.post("/api/artifacts", files={"bundle": ("p.zip", a_bundle)}).json()
    run_id = client.post("/api/runs", json={"artifact_id": artifact["artifact_id"],
                                            "params": {"input": "x", "fasta": "y"}}
                         ).json()["run_id"]
    for body in _bodies():
        projection.record(session, "local", run_id, body)
    session.commit()
    return run_id


def test_a_socket_resumes_from_the_id_it_is_given(client, a_run_with_events, tail):
    """Resuming from an id must not replay what came before it — otherwise the console draws
    the page it already has, twice."""
    from wiener_api.services import stream

    first_id = tail.xrange(stream.key(a_run_with_events), count=1)[0][0]
    with client.websocket_connect(
        f"/api/runs/{a_run_with_events}/stream?from={first_id}"
    ) as socket:
        first = _json.loads(socket.receive_text())
        assert first["seq"] == 1, f"resumed at seq {first['seq']}, replaying the first event"


def test_a_socket_for_an_unknown_run_closes_rather_than_hanging(client):
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect("/api/runs/nope/stream") as socket:
            socket.receive_text()


def test_a_finished_run_drains_and_then_closes(client, a_run_with_events):
    """**Not on the first terminal event** — §4.3 finding 3: `error` arrived after
    `completed`. A socket that hangs up on the first one shows a failed run as successful.

    So it reads to the end, hands over both terminal events, and only then closes.
    """
    received = []
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect(f"/api/runs/{a_run_with_events}/stream?from=0-0") as s:
            while True:
                received.append(_json.loads(s.receive_text()))

    kinds = [event["kind"] for event in received]
    assert len(received) == len(_bodies()), f"drained {len(received)} of {len(_bodies())}"
    assert kinds[-1] == "error" and "completed" in kinds, (
        f"the socket closed before the record was drained: {kinds[-3:]}"
    )

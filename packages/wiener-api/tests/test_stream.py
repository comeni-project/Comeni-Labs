"""The live tail, and the handoff a console depends on. §7.2."""

import json

import pytest
from fakeredis import FakeRedis
from wiener_core.events import heartbeat


@pytest.fixture
def fake_redis() -> FakeRedis:
    """`fakeredis` rather than a container: CI has no Redis, and a guard that only runs on a
    developer's machine is a guard nobody runs. Same argument as the SQLite session."""
    return FakeRedis(decode_responses=True)


@pytest.fixture
def an_event():
    return heartbeat(run_id="r1", at_ms=1_787_517_650_000, seq=1)


def test_publishing_caps_the_stream(fake_redis, an_event):
    """A days-long run must not grow without bound. Lossy on purpose — Postgres is the record
    and Redis is the tail."""
    from wiener_api.services import stream

    for _ in range(20):
        stream.publish("r1", an_event, redis=fake_redis, maxlen=5)
    assert fake_redis.xlen(stream.key("r1")) <= 5


def test_what_is_published_is_the_admitted_event_and_not_the_raw_body(fake_redis, an_event):
    """A subscriber and a reloader must see the same thing, or the console changes when you
    refresh it. Both sides carry `RunEvent`, so the tail cannot drift from the record."""
    from wiener_api.services import stream

    stream.publish("r1", an_event, redis=fake_redis)
    _, fields = fake_redis.xrange(stream.key("r1"))[0]
    assert json.loads(fields["json"])["seq"] == an_event.seq
    assert fields["kind"] == an_event.kind


def test_last_id_is_where_a_subscriber_resumes(fake_redis, an_event):
    from wiener_api.services import stream

    assert stream.last_id("r1", redis=fake_redis) == "0-0", "an empty tail starts at 0-0"
    published = stream.publish("r1", an_event, redis=fake_redis)
    assert stream.last_id("r1", redis=fake_redis) == published


def test_a_failed_publish_does_not_lose_the_event(session, a_run, monkeypatch, caplog):
    """**The record is not lossy.** If Redis is gone the event must still be recorded — and
    must not pass quietly, because a dead tail is a console that stops updating for a reason
    nothing on screen explains."""
    import json as _json
    from pathlib import Path

    from redis.exceptions import ConnectionError as RedisConnectionError
    from wiener_api.services import projection, stream

    monkeypatch.setattr(stream, "publish", lambda *a, **k: (_ for _ in ()).throw(
        RedisConnectionError("no redis")))

    fixture = Path(__file__).parents[3] / "tests/fixtures/weblog/failing-run.jsonl"
    body = _json.loads(fixture.read_text().splitlines()[0])

    with caplog.at_level("WARNING"):
        state = projection.record(session, a_run.lab_id, a_run.id, body)

    assert state.started_at_ms, "the event was folded"
    assert projection.state_of(session, a_run.lab_id, a_run.id).started_at_ms, "and recorded"
    assert "not published" in caplog.text


def test_the_events_page_hands_over_a_stream_id_to_resume_from(client, a_bundle, session,
                                                               tail):
    """The only ordering subtlety in the console, stated as a field rather than a convention.

    §7.2 says it here so Task 12 does not discover it: page from the record, then subscribe
    from the id the page ended at.
    """
    import json as _json
    from pathlib import Path

    from wiener_api.services import projection

    artifact = client.post("/api/artifacts", files={"bundle": ("p.zip", a_bundle)}).json()
    run_id = client.post("/api/runs", json={"artifact_id": artifact["artifact_id"],
                                            "params": {"input": "x", "fasta": "y"}}
                         ).json()["run_id"]

    fixture = Path(__file__).parents[3] / "tests/fixtures/weblog/failing-run.jsonl"
    bodies = [_json.loads(line) for line in fixture.read_text().splitlines() if line.strip()]
    for body in bodies:
        projection.record(session, "local", run_id, body)
    session.commit()

    page = client.get(f"/api/runs/{run_id}/events").json()
    assert len(page["events"]) == len(bodies)
    assert page["cursor"] == len(bodies) - 1
    assert page["stream_id"] != "0-0", "the tail was published to and the page says where"

    # And the second page starts after the first, which is what `after` is for.
    assert client.get(f"/api/runs/{run_id}/events?after={page['cursor']}").json()["events"] == []


def test_an_empty_run_still_hands_over_something_usable(client, a_bundle):
    """A console that opens on a queued run must have somewhere to subscribe from."""
    artifact = client.post("/api/artifacts", files={"bundle": ("p.zip", a_bundle)}).json()
    run_id = client.post("/api/runs", json={"artifact_id": artifact["artifact_id"],
                                            "params": {"input": "x", "fasta": "y"}}
                         ).json()["run_id"]
    page = client.get(f"/api/runs/{run_id}/events").json()
    assert page == {"events": [], "cursor": -1, "stream_id": "0-0"}

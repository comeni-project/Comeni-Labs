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


def test_the_timer_beats_only_unfinished_runs(session, a_run, tail):
    """A175 gave the heartbeat a type and a constructor and no author, so `RunPhase.LOST` was a
    phase nothing could produce. This is the author — and it must not append to runs that are
    over, or a finished run's record grows forever."""
    import asyncio

    from wiener_api import repository
    from wiener_api.services.projection import state_of
    from wiener_api.worker import heartbeat_job

    assert asyncio.run(heartbeat_job({})) == 1
    assert state_of(session, a_run.lab_id, a_run.id).last_seq == 0

    repository.run(session, a_run.lab_id, a_run.id).phase = "succeeded"
    session.commit()
    assert asyncio.run(heartbeat_job({})) == 0, "a finished run was beaten"


def test_a_beat_is_recorded_but_does_not_look_like_life(session, a_run, tail):
    import asyncio

    from wiener_api.services.projection import state_of
    from wiener_api.worker import heartbeat_job

    asyncio.run(heartbeat_job({}))
    state = state_of(session, a_run.lab_id, a_run.id)
    assert state.last_seq == 0, "the beat is in the record"
    assert state.last_activity_ms is None, "and Nextflow has still said nothing"


def test_a_run_nextflow_has_gone_quiet_on_is_called_lost(session, a_run, tail, monkeypatch):
    """**The end of the chain A175 left half-built.** The heartbeat was authored, `decide()`
    could see the silence, and nothing joined the two — so `RunPhase.LOST` stayed a phase
    nothing could reach, which is the consumer-with-no-producer shape this project has shipped
    twice before (`AiProvenance.available`, `OpenQuestion.suggested`).
    """
    import asyncio
    import json as _json
    from pathlib import Path

    from wiener_api import repository
    from wiener_api.services import projection
    from wiener_api.settings import settings
    from wiener_api.worker import heartbeat_job

    # A run Nextflow started and then said nothing more about.
    fixture = Path(__file__).parents[3] / "tests/fixtures/weblog/failing-run.jsonl"
    started = _json.loads(fixture.read_text().splitlines()[0])
    projection.record(session, a_run.lab_id, a_run.id, started)
    session.commit()
    assert repository.run(session, a_run.lab_id, a_run.id).phase == "running"

    monkeypatch.setattr(settings, "lost_after_ms", 1)   # the window, made small
    asyncio.run(heartbeat_job({}))
    assert repository.run(session, a_run.lab_id, a_run.id).phase == "lost"


def test_a_lost_run_that_speaks_again_is_not_lost(session, a_run, tail, monkeypatch):
    """`lost` is a guess about a window, so it must not be sticky: `append` writes the phase
    from the fold, and an event arriving after the verdict overturns it."""
    import asyncio
    import json as _json
    from pathlib import Path

    from wiener_api import repository
    from wiener_api.services import projection
    from wiener_api.settings import settings
    from wiener_api.worker import heartbeat_job

    fixture = Path(__file__).parents[3] / "tests/fixtures/weblog/failing-run.jsonl"
    bodies = [_json.loads(line) for line in fixture.read_text().splitlines() if line.strip()]
    projection.record(session, a_run.lab_id, a_run.id, bodies[0])
    session.commit()

    monkeypatch.setattr(settings, "lost_after_ms", 1)
    asyncio.run(heartbeat_job({}))
    assert repository.run(session, a_run.lab_id, a_run.id).phase == "lost"

    projection.record(session, a_run.lab_id, a_run.id, bodies[1])   # it was only quiet
    assert repository.run(session, a_run.lab_id, a_run.id).phase == "running"

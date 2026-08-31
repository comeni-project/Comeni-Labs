"""The series is a **query over the projection**, never a fold in the request — `rn-blocked`.

A191 settled this shape for the Tasks tab and the same argument decides it here: a 5,000-task
run is 15,000 events to replay and one indexed `SELECT` to read. What makes it a rule rather
than a preference is that both spellings return the same numbers, so nothing but a guard
notices when the expensive one comes back.
"""

import json
from pathlib import Path

import pytest
from wiener_api.services import projection
from wiener_api.settings import settings
from wiener_core.events import RunEvent

SPINE = Path(__file__).parents[3] / "tests/fixtures/weblog/spine-run.events.jsonl"


def _replay_into(session, run_id: str) -> None:
    for line in SPINE.read_text().splitlines():
        if line.strip():
            event = RunEvent.model_validate({**json.loads(line), "run_id": run_id})
            projection.append(session, settings.lab_id, run_id, event)


def test_the_series_never_folds_the_event_stream(client, session, a_run, monkeypatch):
    """**`state_of` raises, and the answer is still right.**

    Patching the fold to explode is the only way to tell the two implementations apart: both
    produce the same curves, so a route that quietly replayed every event would be green on
    every other assertion in this file.

    **The first version of this guard was inert**, and it is the gotcha `CLAUDE.md` names by
    hand: `runs.py` does `from …projection import state_of`, so patching the attribute on the
    `projection` module binds past the name the route actually calls. It passed against a route
    reverted to fold. Both spellings are patched here, so neither import style escapes.
    """
    from wiener_api.routes import runs as runs_route
    _replay_into(session, a_run.id)

    def _refuse(*args, **kwargs):
        raise AssertionError("the series folded the event stream")

    monkeypatch.setattr(projection, "state_of", _refuse)
    monkeypatch.setattr(runs_route, "state_of", _refuse)

    answer = client.get(f"/api/runs/{a_run.id}/series")
    assert answer.status_code == 200
    body = answer.json()
    assert body["curves"], "and it answered from the projection alone"
    assert body["reported_resources"] is True


def test_the_bin_is_sized_off_the_run_and_not_off_a_constant(client, session, a_run):
    """A 40-second stub run collapses to one point under a bin picked for a four-hour job."""
    _replay_into(session, a_run.id)
    body = client.get(f"/api/runs/{a_run.id}/series").json()

    span = body["to_ms"] - body["from_ms"]
    assert span > 0
    assert 0 < body["bin_ms"] <= span, "a bin wider than the run is one bucket"
    assert span / body["bin_ms"] >= 50, "and it must leave enough buckets to have a shape"


def test_a_run_with_no_tasks_is_an_empty_series_and_not_a_404(client, a_run):
    """A run that has recorded nothing has an honest answer: no curves. `curves: []` says the
    record is empty; a 404 would say the run is."""
    body = client.get(f"/api/runs/{a_run.id}/series").json()
    assert body["curves"] == [] and body["reported_resources"] is False


def test_an_unknown_run_is_a_404(client):
    assert client.get("/api/runs/nope/series").status_code == 404


@pytest.mark.parametrize("name", ["peak", "rss"])
def test_the_endpoint_offers_no_memory_over_time_curve(client, session, a_run, name):
    """The absence travels. `wiener-core` refuses to build the curve and this asserts the route
    did not add one on the way past — the number everybody asks for is the one that describes
    an instant that never happened."""
    _replay_into(session, a_run.id)
    body = client.get(f"/api/runs/{a_run.id}/series").json()
    assert not any(name in curve["name"] for curve in body["curves"])

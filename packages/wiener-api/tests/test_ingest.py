# packages/wiener-api/tests/test_ingest.py
import json
from pathlib import Path

FIXTURE = Path(__file__).parents[3] / "tests/fixtures/weblog/failing-run.jsonl"


def _paths(app) -> set[str]:
    """Every path an app serves, through both shapes FastAPI 0.141 uses.

    `include_router` leaves an `_IncludedRouter` in `app.routes` — no `.path`, no `.routes` —
    so the plan's `{r.path for r in app.routes}` raises on the ingest app and, written
    defensively with a `getattr`, would have found **nothing** and passed while proving
    nothing. That is the shape Plan 3A phase 6's audit caught: a boundary check that iterated
    `app.routes`, found zero request bodies and would have passed vacuously.
    """
    found = set()
    for route in app.routes:
        if (path := getattr(route, "path", None)) is not None:
            found.add(path)
        inner = getattr(route, "original_router", None) or route
        for sub in getattr(inner, "routes", ()):
            if (path := getattr(sub, "path", None)) is not None:
                found.add(path)
    return found


def test_the_route_scan_sees_something():
    """A67 again: a scan that reaches nothing reports nothing. If FastAPI changes shape a
    third time, this fails rather than the two tests below quietly becoming decorative."""
    from wiener_api.main import create_app, create_ingest_app

    assert "/api/health" in _paths(create_app())
    assert _paths(create_ingest_app()), "no path found on the ingest app — _paths is blind"


def test_the_ingest_app_is_not_the_public_app(a_run):
    """§13.1. An ingest route mounted on the public app for convenience is the defect Plan 3A
    phase 6 found — an unauthenticated request reaching a filesystem path — one release later.

    Asserted **behaviourally as well as structurally**: the public app is asked for the route
    with a valid run id and the real secret, and must not have it."""
    from fastapi.testclient import TestClient
    from wiener_api.main import create_app, create_ingest_app

    assert not any(p.startswith("/events") for p in _paths(create_app()))
    assert any(p.startswith("/events") for p in _paths(create_ingest_app()))

    body = json.loads(FIXTURE.read_text().splitlines()[0])
    served = TestClient(create_app()).post(
        f"/events/{a_run.id}/{a_run.ingest_secret}", json=body
    )
    assert served.status_code == 404, "the public app served an ingest POST"


def test_a_wrong_secret_is_refused(ingest_client, a_run):
    body = json.loads(FIXTURE.read_text().splitlines()[0])
    assert ingest_client.post(f"/events/{a_run.id}/not-the-secret", json=body).status_code == 404


def test_replaying_the_capture_through_http_gives_the_folded_state(ingest_client, a_run, session):
    """The projection must agree with the fold — §7.1."""
    from wiener_api.models import Run

    for line in FIXTURE.read_text().splitlines():
        if line.strip():
            r = ingest_client.post(f"/events/{a_run.id}/{a_run.ingest_secret}",
                                   json=json.loads(line))
            assert r.status_code == 204
    assert session.get(Run, a_run.id).phase == "failed"


def test_projection_matches_replay(ingest_client, a_run, session):
    """§7.1: `run_task` and `run.phase` are a **cache with a rebuild path**, and this is the
    test that says the cache agrees with the fold.

    As the plan wrote it, this only called `state_of` — which *is* the replay — and checked
    two counts, so it would have passed with the projection tables empty or wrong. It now
    compares what was cached against what the record folds to.
    """
    from wiener_api import repository
    from wiener_api.services.projection import state_of

    for line in FIXTURE.read_text().splitlines():
        if line.strip():
            ingest_client.post(f"/events/{a_run.id}/{a_run.ingest_secret}", json=json.loads(line))

    folded = state_of(session, a_run.lab_id, a_run.id)
    assert folded.counts.succeeded == 2 and folded.counts.failed == 1

    cached_run = repository.run(session, a_run.lab_id, a_run.id)
    assert cached_run.phase == folded.phase, (
        f"run.phase is {cached_run.phase!r} and the record folds to {folded.phase!r}"
    )
    for task in folded.tasks.values():
        row = repository.task(session, a_run.lab_id, a_run.id, task.task_id)
        assert row is not None, f"task {task.task_id} is in the fold and not in run_task"
        assert (row.status, row.latest_exit) == (task.status, task.latest_exit), (
            f"run_task {task.task_id} cached {row.status!r}/{row.latest_exit!r}; "
            f"the record folds to {task.status!r}/{task.latest_exit!r}"
        )
        assert [a["n"] for a in row.attempts] == [a.n for a in task.attempts]

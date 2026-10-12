"""Wiener's sweep: a run's working files go by outcome and age, results stay, and a live run is
never touched (Part H spec §5.2)."""

from datetime import UTC, datetime, timedelta

import pytest
import wiener_rows
from wiener_api import repository
from wiener_api.models import RetentionSweep
from wiener_api.services import launcher, retention
from wiener_api.settings import settings

NOW = datetime(2026, 10, 12, 4, 0, tzinfo=UTC)


@pytest.fixture
def work(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "work_root", tmp_path / "work")
    monkeypatch.setattr(settings, "artifact_root", tmp_path / "artifacts")


def _ended(session, phase, days_ago):
    run = wiener_rows.a_run(session, phase=phase, ended_at=NOW - timedelta(days=days_ago))
    (launcher.work_dir(run.id) / "work").mkdir(parents=True)
    (launcher.work_dir(run.id) / "results").mkdir(parents=True)
    return run


def test_working_files_go_by_outcome_and_results_stay(session, work):
    ok = _ended(session, "succeeded", 0)
    failed_young = _ended(session, "failed", 6)
    failed_old = _ended(session, "failed", 8)
    removed = retention.sweep(NOW)
    assert not (launcher.work_dir(ok.id) / "work").exists()
    assert (launcher.work_dir(ok.id) / "results").exists()
    assert (launcher.work_dir(failed_young.id) / "work").exists()
    assert not (launcher.work_dir(failed_old.id) / "work").exists()
    session.expire_all()
    assert repository.run(session, settings.lab_id, failed_old.id).work_cleared_at is not None
    assert removed == {"work_succeeded": 1, "work_failed": 1, "runs": 0}


def test_a_live_run_s_files_are_never_touched(session, work):
    """By phase, not only by `ended_at`: a run called lost that spoke again is running, and
    keeps the `ended_at` its loss wrote."""
    run = wiener_rows.a_run(session, phase="running", ended_at=NOW - timedelta(days=30))
    (launcher.work_dir(run.id) / "work").mkdir(parents=True)
    retention.sweep(NOW)
    assert (launcher.work_dir(run.id) / "work").exists()


def test_runs_are_deleted_whole_only_once_a_limit_is_set(session, work, monkeypatch):
    old = _ended(session, "succeeded", 400)
    retention.sweep(NOW)
    session.expire_all()
    assert repository.run(session, settings.lab_id, old.id) is not None
    monkeypatch.setenv("WIENER_RETENTION_RUNS_DAYS", "365")
    assert retention.sweep(NOW)["runs"] == 1
    session.expire_all()
    assert repository.run(session, settings.lab_id, old.id) is None


def test_a_pass_with_nothing_to_do_still_says_it_ran(session, work):
    retention.sweep(NOW)
    rows = session.query(RetentionSweep).all()
    assert {r.category for r in rows} == {"work_succeeded", "work_failed", "runs"}
    assert all(r.removed == 0 for r in rows)


def test_the_last_sweep_is_served_and_a_cleared_run_says_so(client, session, work):
    assert client.get("/api/wiener/retention/last").json() is None
    run = _ended(session, "succeeded", 1)
    retention.sweep(NOW)
    last = client.get("/api/wiener/retention/last").json()
    assert last["removed"]["work_succeeded"] == 1
    assert client.get(f"/api/runs/{run.id}").json()["work_cleared"] is True

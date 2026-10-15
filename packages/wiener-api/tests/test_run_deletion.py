"""Deleting a finished run takes its rows, its directory and its stream; its pipeline goes with
its last run (Part H spec §5.1)."""

from datetime import UTC, datetime

import pytest
import wiener_rows
from wiener_api import repository
from wiener_api.models import RunArtifact, RunIntent
from wiener_api.services import deletion, launcher, stream
from wiener_api.settings import settings
from wiener_core.policy import IntentKind, Outcome, Reason

LIVE = ("queued", "launching", "running")


@pytest.fixture
def roots(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "work_root", tmp_path / "work")
    monkeypatch.setattr(settings, "artifact_root", tmp_path / "artifacts")


def test_a_finished_run_leaves_nothing_behind(session, roots, tail):
    run = wiener_rows.a_run(session, phase="succeeded")
    (launcher.work_dir(run.id) / "work").mkdir(parents=True)
    tail.xadd(stream.key(run.id), {"seq": 0})
    session.add(RunIntent(id="intent-1", lab_id=settings.lab_id, run_id=run.id,
                          kind=IntentKind.CANCEL, because=Reason.OPERATOR_REQUEST, who="t",
                          at=datetime.now(UTC), prior_phase="running",
                          outcome=Outcome.SIGNALLED))
    session.commit()
    deletion.delete_run(run.id)
    session.expire_all()
    assert repository.run(session, settings.lab_id, run.id) is None
    assert repository.events(session, settings.lab_id, run.id) == []
    assert repository.tasks(session, settings.lab_id, run.id) == []
    assert not launcher.work_dir(run.id).exists()
    assert not tail.exists(stream.key(run.id))
    assert session.get(RunIntent, "intent-1") is None


@pytest.mark.parametrize("phase", LIVE)
def test_a_live_run_is_refused(session, roots, phase):
    run = wiener_rows.a_run(session, phase=phase)
    with pytest.raises(deletion.Refused, match="cancel it first"):
        deletion.delete_run(run.id)
    assert repository.run(session, settings.lab_id, run.id) is not None


def test_its_pipeline_stays_while_another_run_uses_it(session, roots):
    """Review Focus 3."""
    first = wiener_rows.a_run(session, phase="failed")
    second = wiener_rows.a_run(session, phase="succeeded", artifact_id=first.artifact_id)
    (settings.artifact_root / first.artifact_id).mkdir(parents=True)
    deletion.delete_run(first.id)
    session.expire_all()
    assert repository.artifact(session, settings.lab_id, second.artifact_id) is not None
    assert (settings.artifact_root / first.artifact_id).exists()
    deletion.delete_run(second.id)
    session.expire_all()
    assert session.get(RunArtifact, first.artifact_id) is None
    assert not (settings.artifact_root / first.artifact_id).exists()


def test_the_route_answers_204_then_404_and_409_for_a_live_run(client, session):
    done = wiener_rows.a_run(session, phase="cancelled")
    live = wiener_rows.a_run(session, phase="running")
    assert client.delete(f"/api/runs/{done.id}").status_code == 204
    assert client.delete(f"/api/runs/{done.id}").status_code == 404
    refused = client.delete(f"/api/runs/{live.id}")
    assert refused.status_code == 409 and "cancel" in refused.json()["detail"]

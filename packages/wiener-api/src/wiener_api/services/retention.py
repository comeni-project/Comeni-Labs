"""Wiener's daily sweep (Part H spec §5.2): a run's working files by outcome and age, and whole
runs once a limit is set. Results and records stay unless the run itself goes. Limits are read
from Wiener's settings on every pass, so a change on the menu reaches the next one.
"""

import shutil
from datetime import UTC, datetime, timedelta

from comeni_core.settings import catalogue
from comeni_core.settings.retention import days
from pydantic import BaseModel, ConfigDict
from wiener_core.state import RunPhase

from wiener_api import db, repository
from wiener_api.services import deletion, launcher
from wiener_api.services.installation import installation
from wiener_api.settings import settings

SUCCEEDED = {RunPhase.SUCCEEDED.value}
STOPPED = {RunPhase.FAILED.value, RunPhase.CANCELLED.value, RunPhase.LOST.value}


class LastSweep(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    ran_at: datetime
    removed: dict[str, int]


def _limit(setting) -> int | None:
    return days(str(installation().get(setting)))


def _clear_work(now: datetime, phases: set[str], limit: int | None) -> int:
    if limit is None:
        return 0
    with db.session_scope() as session:
        runs = repository.finished_before(session, settings.lab_id, phases,
                                          now - timedelta(days=limit), uncleared=True)
        for run in runs:
            shutil.rmtree(launcher.work_dir(run.id) / "work", ignore_errors=True)
            run.work_cleared_at = now
        return len(runs)


def sweep(now: datetime) -> dict[str, int]:
    removed = {
        "work_succeeded": _clear_work(now, SUCCEEDED,
                                      _limit(catalogue.WORK_SUCCEEDED)),
        "work_failed": _clear_work(now, STOPPED, _limit(catalogue.WORK_FAILED)),
        "runs": 0,
    }
    if (limit := _limit(catalogue.RUNS)) is not None:
        with db.session_scope() as session:
            ids = [r.id for r in repository.finished_before(
                session, settings.lab_id, SUCCEEDED | STOPPED, now - timedelta(days=limit))]
        for run_id in ids:
            deletion.delete_run(run_id)
            removed["runs"] += 1
    with db.session_scope() as session:
        repository.record_sweep(session, settings.lab_id, now, removed)
    return removed


def last() -> LastSweep | None:
    with db.session_scope() as session:
        found = repository.last_sweep(session, settings.lab_id)
    return None if found is None else LastSweep(ran_at=found[0], removed=found[1])


async def retention_sweep(ctx: dict) -> dict[str, int]:
    """The cron entry point. The clock is read here, never inside `sweep`."""
    return sweep(datetime.now(UTC))

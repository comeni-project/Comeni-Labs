"""Background work. Launching a head process does not belong in a request — it outlives one.

The same shape `mendel-api` takes for gates: the route writes a row and returns in single-digit
milliseconds, and the work that can take three days happens somewhere a browser is not waiting.
"""

from datetime import UTC, datetime

from arq import cron
from arq.connections import RedisSettings

from wiener_api import db, repository
from wiener_api.services.launcher import launch
from wiener_api.services.projection import beat
from wiener_api.settings import settings


async def launch_job(ctx: dict, run_id: str, params: dict | None = None) -> str:
    """The run's parameters travel here rather than in a column — §7.1 forbids the column, and
    a job argument is transient by nature, which is the right lifetime for run data."""
    launch(run_id, params)
    return run_id


async def heartbeat_job(ctx: dict) -> int:
    """Append a heartbeat to every unfinished run. **The clock lives here and nowhere else.**

    `wiener-core` may not read one (§6.1), so the passage of time reaches the fold as an event
    — and this is the thing that appends it. Without it `RunPhase.LOST` is a phase nothing can
    ever produce and `decide()`'s give-up branch is unreachable, which is what A175 left behind
    when it gave the heartbeat a type and a constructor and no author.

    A heartbeat is deliberately **not** a sign of life: `fold` leaves `last_activity_ms` alone
    for it, so a run that Nextflow has gone quiet on is distinguishable from one Wiener is
    merely still watching.
    """
    now_ms = int(datetime.now(UTC).timestamp() * 1000)
    with db.session_scope() as session:
        runs = repository.unfinished(session, settings.lab_id)
        for run in runs:
            beat(session, settings.lab_id, run.id, now_ms)
    return len(runs)


class WorkerSettings:
    functions = [launch_job]
    cron_jobs = [
        # Every five minutes. The interval only has to be finer than the coarsest thing that
        # reads it, and §17's `LOST` window is deliberately blunt — it must exceed the slowest
        # single task, and a six-hour STAR align emits nothing while it runs.
        cron(heartbeat_job, minute={0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55}),
    ]
    redis_settings = RedisSettings.from_dsn(settings.redis_url)

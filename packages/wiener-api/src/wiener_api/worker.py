"""Background work. Launching a head process does not belong in a request — it outlives one.

The same shape `mendel-api` takes for gates: the route writes a row and returns in single-digit
milliseconds, and the work that can take three days happens somewhere a browser is not waiting.
"""

import logging
from datetime import UTC, datetime

from arq import cron
from arq.connections import RedisSettings
from redis.exceptions import RedisError
from wiener_core.policy import IntentKind, Policy, Reason, decide
from wiener_core.state import RunPhase

from wiener_api import db, main, repository
from wiener_api.services import retention, stream
from wiener_api.services.launcher import launch
from wiener_api.services.projection import beat
from wiener_api.settings import settings


async def launch_job(ctx: dict, run_id: str) -> str:
    """The run id only. Its parameters wait in its own directory (`launcher.params_path`), never
    in a table (invariant 15) and no longer in this job, so a Redis that loses the job loses a
    delay, not the run (#273)."""
    launch(run_id)
    return run_id


async def requeue_queued(ctx: dict) -> int:
    """Every run still `queued` is queued again when the worker starts. Safe because `launch`
    claims a run before it does anything and skips one already claimed (#273)."""
    with db.session_scope() as session:
        ids = [run.id for run in repository.queued(session, settings.lab_id)]
    for run_id in ids:
        await ctx["redis"].enqueue_job("launch_job", run_id)
    return len(ids)


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
    policy = Policy(lost_after_ms=settings.lost_after_ms)

    with db.session_scope() as session:
        runs = repository.unfinished(session, settings.lab_id)
        for run in runs:
            state = beat(session, settings.lab_id, run.id, now_ms)
            if _given_up_on(state, policy, now_ms):
                # **An observation, not a verb.** `lost` is a fact about a run in the same way
                # `failed` is; cancelling and relaunching are verbs and they wait for W4 and an
                # approval. Nothing here touches the world — the head process, wherever it is,
                # is not signalled.
                #
                # And it is not sticky: `append` writes `run.phase` from the fold, so an event
                # arriving after this puts the run back where the record says it is. A run that
                # was merely quiet un-loses itself, which is the right behaviour for a window
                # that §17 admits is a guess.
                run.phase = RunPhase.LOST
                # No event will come to let its tail go, so the verdict does (issue 274). The
                # tail is lossy and the record is not: a Redis that cannot hear this is logged.
                try:
                    stream.retire(run.id)
                except RedisError as exc:
                    logging.getLogger(__name__).warning("run %s: tail not retired: %s",
                                                        run.id, exc)
    return len(runs)


def _given_up_on(state, policy: Policy, now_ms: int) -> bool:
    return any(
        intent.kind is IntentKind.GIVE_UP and intent.because is Reason.NO_EVENTS
        for intent in decide(state, policy, now_ms)
    )


async def warn_about_the_pairing(ctx: dict) -> None:
    """**The container that holds the socket is the one that can see it.**

    `main.create_app` checks this too and, in the compose topology, always finds nothing: the
    socket is mounted on the worker and not on the API, so that warning could never fire where
    it matters. A check that cannot fire is worse than no check, because it reads as one.

    Either half is a choice. The pair — an API anyone can reach and a worker that can start
    containers on the host — is how a laboratory tool becomes a way into a laboratory's
    machine.
    """
    if main.socket_is_mounted() and not settings.api_token:
        logging.getLogger(__name__).warning(
            "This worker can start containers on the host (the Docker socket is mounted) and "
            "WIENER_API_TOKEN is unset, so the API in front of it accepts every request. "
            "ANYONE WHO CAN REACH THAT API CAN REACH THIS HOST. Set WIENER_API_TOKEN before "
            "exposing it beyond localhost — docs/design/wiener.md §12.1.",
        )


async def on_startup(ctx: dict) -> None:
    await warn_about_the_pairing(ctx)
    await requeue_queued(ctx)


class WorkerSettings:
    functions = [launch_job]
    on_startup = on_startup
    cron_jobs = [
        # Every five minutes. The interval only has to be finer than the coarsest thing that
        # reads it, and §17's `LOST` window is deliberately blunt — it must exceed the slowest
        # single task, and a six-hour STAR align emits nothing while it runs.
        cron(heartbeat_job, minute={0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55}),
        # Part H: once a day, what is past its retention limit.
        cron(retention.retention_sweep, hour=4, minute=0),
    ]
    redis_settings = RedisSettings.from_dsn(settings.redis_url)

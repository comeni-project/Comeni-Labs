"""Background work that is not a model call. Nothing long-running may sit in a request.

A gate (the stub and test runs of a kept draft) takes up to 900s cold, and the retention sweep
walks every stored row, so both run here under ARQ.
"""

import logging

from arq import cron
from arq.connections import RedisSettings
from arq.worker import func

from mendel_api.services import gates as gate_service
from mendel_api.services import retention
from mendel_api.settings import settings

log = logging.getLogger(__name__)


async def run_gate_job(ctx: dict, run_id: str) -> str:
    """Gate a kept draft. **Not a pipeline run**: a gate checks a draft; Wiener runs pipelines."""
    await gate_service.execute(run_id)
    return run_id


async def sweep_lost_gates(ctx: dict) -> int:
    """Fail every gate whose worker never finished it (issue 278). Returns how many.

    **On a timer, unlike the AI worker's reclaim**, which runs only at startup because a model
    call has no known length. A gate does: Nextflow is stopped at its limit, so a row live long
    past it is lost, not slow. A queue that lost the job would otherwise wait for a restart.
    """
    swept = gate_service.sweep()
    if swept:
        log.warning("failed %d gate(s) that never came back: %s", len(swept), swept)
    return len(swept)


class WorkerSettings:
    functions = [
        # **Its own limit, and one try** (issue 278). arq's default (300s) cancelled the stub
        # and test gates. A retry would re-run an hour-long gate unasked, into the directory the
        # first one was writing.
        func(run_gate_job, timeout=gate_service.JOB_TIMEOUT, max_tries=1),
        sweep_lost_gates,
    ]
    """**Everything that is not a model call.** The split from `AIWorkerSettings` is about
    starvation: a model call is measured in minutes and must not hold up a gate.
    `test_the_two_worker_function_lists_are_disjoint` holds them apart, because a job on both
    lists would land on whichever queue the caller happened to pick."""
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
    cron_jobs = [
        cron(sweep_lost_gates, minute={0, 15, 30, 45}, run_at_startup=True),
        # Part H: once a day, what is past its retention limit.
        cron(retention.retention_sweep, hour=4, minute=0),
    ]
    """**`unique=True` is arq's default and is load-bearing**: two worker replicas would
    otherwise each start the same sweep at the same minute."""

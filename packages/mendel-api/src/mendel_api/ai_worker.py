"""The worker that is allowed to call a provider, and nothing else.

**A separate process rather than a second function list, and the reason is starvation.** The
forge measured a model fill at 227s for one module. A source sync is seconds and somebody is
watching for its answer; on one queue with a shared concurrency budget, that sync waits behind
whatever generation happens to be in flight. Two queues means the slow thing cannot block the
fast one, and it costs one container.

**Concurrency one by default.** A local Ollama serves one request at a time and a second
concurrent call makes both slower rather than either faster; a hosted provider has a rate limit
that a worker cannot see. One is the setting that is correct in both places, and
`MENDEL_AI_MAX_JOBS` is there for the operator who knows their own limit. It is not a
performance ceiling worth raising blind: the queue is where work waits, and work waiting in a
queue is visible.

**Recovery at startup, not on a timer.** A worker that died mid-job leaves an adaptation in a
state it holds, and rule 7 says that must not last forever. The moment a *new* worker starts is
the moment the old one is definitely gone — a timer would have to guess a duration that
distinguishes *the process died* from *the model is slow*, and those look identical from the
row. `reclaim_lost_jobs` runs once, on startup, and writes a `reclaimed` event so the sweep is
visible rather than silent.
"""

import logging

from arq.connections import RedisSettings

from mendel_api.jobs import AI_QUEUE
from mendel_api.services import forge_jobs
from mendel_api.settings import settings

log = logging.getLogger(__name__)


async def reclaim_lost_jobs(ctx: dict) -> int:
    """Fail every adaptation a worker was holding when it died. Returns how many.

    **Runs on the AI worker only**, because the states it sweeps are the ones this worker
    holds. When Task 12 gives the ordinary worker its own reclaim for `scaffolding` and
    `publishing`, it will be a second call to the same service verb with a different set —
    not a second implementation.

    A reclaimed adaptation goes to `failed` rather than back to `queued`. Retrying
    automatically is how a job that kills its worker kills every worker in turn, and `retry` is
    a verb a person has: the row carries `failed_stage`, so the retry resumes where it stopped.
    """
    reclaimed = await forge_jobs.reclaim(after=settings.ai_job_timeout_seconds)
    if reclaimed:
        log.warning("reclaimed %d adaptation(s) whose worker did not come back", len(reclaimed))
    return len(reclaimed)


class AIWorkerSettings:
    """The AI lane. **Its function list is the allowlist of what may reach a provider.**

    Nothing here is shared with `WorkerSettings`: a job on both lists could be enqueued to
    either queue, and which one it landed on would depend on the caller rather than on what the
    job does. `test_ai_worker.py` holds the two lists disjoint.
    """

    functions = [forge_jobs.generate_forge_revision, forge_jobs.answer_forge_review_message]
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
    queue_name = AI_QUEUE
    max_jobs = settings.ai_max_jobs
    job_timeout = settings.ai_job_timeout_seconds
    """A hard ceiling on one job, in seconds.

    ARQ cancels the coroutine when this passes, which leaves the *database* row still claimed —
    the cancellation is in this process and the row is in Postgres. That is what
    `reclaim_lost_jobs` is for, and it is why the timeout and the reclaim threshold are the
    same setting rather than two numbers somebody has to keep in a sensible relation.
    """
    on_startup = reclaim_lost_jobs
    """**Not `cron_jobs`.** A sweep on a schedule has to guess a duration that tells *the
    process died* from *the model is slow*, and the row shows neither. A worker starting is
    proof the previous one is gone."""

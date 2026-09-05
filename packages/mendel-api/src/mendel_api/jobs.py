"""Handing work to a worker, and saying which one.

**One seam, because a route that reached Redis directly would make every route test need one.**
`services/drafts.py` records the same argument for its storage seam, and `services/gates.py`
for its subprocess.

**Two queues since Task 7, and the split is about starvation rather than tidiness.** A model
call is measured at 227s for one module; a source sync is seconds and a person is waiting on the
answer. One queue with a shared concurrency budget means the sync sits behind whatever
generation happens to be in flight — so the AI worker is a separate process on `arq:queue:ai`
with a concurrency of one, and everything else keeps the default queue it has always used.

**Every enqueue may name its job id, and the forge's always do.** ARQ delivers at least once:
a redeploy mid-job re-delivers it, and two workers then start two model calls for one
adaptation. A job id derived from what the work is *about* — adaptation, revision, purpose —
makes the duplicate a no-op at the queue rather than a race at the database. The database
refusal stays as well, and the two are not the redundancy the journal keeps warning about:
this one prevents the second call, and `forge_state.claim` is what holds when the first job has
already finished and the id has aged out of Redis.
"""

import asyncio

from arq import create_pool
from arq.connections import ArqRedis, RedisSettings

from mendel_api.settings import settings

DEFAULT_QUEUE = "arq:queue"
"""ARQ's own default, spelled out.

Named rather than left implicit because the AI queue is named, and a pair where one side is a
literal and the other is a library default is a pair that drifts the first time the library
changes its mind.
"""

AI_QUEUE = "arq:queue:ai"
"""Where anything that calls a provider goes. One consumer, `ai_worker.AIWorkerSettings`."""

_pools: dict[str, ArqRedis] = {}
_lock = asyncio.Lock()


async def _pool(queue: str) -> ArqRedis:
    """One pool per queue, created once and kept.

    `create_pool` opens a connection, and doing that per request is a connection per click.
    **Locked**, because two concurrent first requests would each see nothing and open one, and
    the loser is then never closed. The lock is contended once per queue per process.
    """
    if queue not in _pools:
        async with _lock:
            if queue not in _pools:
                _pools[queue] = await create_pool(
                    RedisSettings.from_dsn(settings.redis_url), default_queue_name=queue
                )
    return _pools[queue]


async def enqueue(
    name: str,
    *args: object,
    job_id: str | None = None,
    queue: str = DEFAULT_QUEUE,
) -> bool:
    """Queue a job by its worker function name. `False` when the id was already queued.

    **The return value is the whole point of `job_id`.** ARQ refuses a duplicate id and returns
    `None` from `enqueue_job` rather than raising, which is easy to discard — and discarding it
    turns *this was already queued* into *this was queued*, so a caller reports work started
    that will never run twice. Callers that do not care may ignore it; callers that report to a
    person must not.
    """
    pool = await _pool(queue)
    return await pool.enqueue_job(name, *args, _job_id=job_id) is not None


def job_id_for(*parts: str) -> str:
    """A stable id for one piece of work: `forge:generate:<adaptation>:<revision>`.

    **Derived from what the work is about, never from a clock or a token.** An id containing
    `uuid4()` is unique, which is the opposite of what is wanted here — two deliveries of one
    job must collide, and only an id computed from the same inputs does that.

    Joined with `:` because that is Redis's own convention and these keys are read in
    `redis-cli` when something is stuck.
    """
    if not parts or any(not part or ":" in part for part in parts):
        raise ValueError(
            f"a job id is built from non-empty parts that contain no colon: {parts}. "
            "A part carrying one makes two different jobs share an id, which is worse than "
            "having none — the second is silently dropped."
        )
    return ":".join(parts)


async def close() -> None:
    """Release every pool. Called on shutdown, and by tests between cases."""
    for pool in _pools.values():
        await pool.aclose()
    _pools.clear()

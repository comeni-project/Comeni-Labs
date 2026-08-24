"""Handing work to the worker.

**One seam, because a route that reached Redis directly would make every route test need one.**
`services/drafts.py` records the same argument for its storage seam, and `services/gates.py`
for its subprocess.

This is the first thing in the repository that enqueues anything: the worker has run a single
cron job since Plan 3A phase 8, and nothing has ever put work on the queue by hand.
"""

import asyncio

from arq import create_pool
from arq.connections import ArqRedis, RedisSettings

from mendel_api.settings import settings

_pool: ArqRedis | None = None
_lock = asyncio.Lock()


async def enqueue(name: str, *args: object) -> None:
    """Queue a job by its worker function name.

    The pool is created once and kept: `create_pool` opens a connection, and doing that per
    request is a connection per click. **Locked**, because two concurrent first requests would
    each see `None` and open one, and the loser is then never closed. The lock is contended
    once per process.
    """
    global _pool
    if _pool is None:
        async with _lock:
            if _pool is None:
                _pool = await create_pool(RedisSettings.from_dsn(settings.redis_url))
    await _pool.enqueue_job(name, *args)

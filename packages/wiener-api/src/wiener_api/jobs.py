"""Handing work to the worker.

One seam, for the reason `mendel_api.jobs` records: a route that reached Redis directly would
make every route test need one.
"""

import asyncio

from arq import create_pool
from arq.connections import ArqRedis, RedisSettings

from wiener_api.settings import settings

_pool: ArqRedis | None = None
_lock = asyncio.Lock()


async def enqueue(name: str, *args: object) -> None:
    """Queue a job by its worker function name. The pool is created once and kept."""
    global _pool
    if _pool is None:
        async with _lock:
            if _pool is None:
                _pool = await create_pool(RedisSettings.from_dsn(settings.redis_url))
    await _pool.enqueue_job(name, *args)

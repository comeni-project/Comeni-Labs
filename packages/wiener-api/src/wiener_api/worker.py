"""Background work. Launching a head process does not belong in a request — it outlives one.

The same shape `mendel-api` takes for gates: the route writes a row and returns in single-digit
milliseconds, and the work that can take three days happens somewhere a browser is not waiting.
"""

from arq.connections import RedisSettings

from wiener_api.services.launcher import launch
from wiener_api.settings import settings


async def launch_job(ctx: dict, run_id: str, samplesheet: str = "-") -> str:
    """The samplesheet travels here rather than in a column — §7.1 forbids the column, and a
    job argument is transient by nature, which is the right lifetime for it."""
    launch(run_id, samplesheet)
    return run_id


class WorkerSettings:
    functions = [launch_job]
    redis_settings = RedisSettings.from_dsn(settings.redis_url)

"""Background work. Nothing long-running may sit in a request.

`ops.check` walks every contract against its source; the forge's own measurements put a
model fill at 227s for one module and a stub gate at up to 900s cold. None of that belongs
in a request, and ARQ is where it goes.
"""

from datetime import UTC, datetime

from arq import cron
from arq.connections import RedisSettings
from mendel_forge import ops

from mendel_api.db import session_scope
from mendel_api.models import SourceCheck
from mendel_api.services import forge_jobs
from mendel_api.services import gates as gate_service
from mendel_api.settings import settings


async def check_sources(ctx: dict) -> dict[str, int]:
    """Compare the registry against its vendored sources, and remember that it happened.

    **Vendored, not upstream.** `ops.check` reads `source_root`, which is the vendored copy
    — issue #64 is the missing half, and until it lands nothing here can say *a newer
    version is available*. The UI must not imply otherwise.
    """
    result = ops.check(
        ops.CheckRequest(
            registry_root=settings.registry_root,
            source_root=settings.registry_root,
        )
    )
    with session_scope() as session:
        session.add(
            SourceCheck(
                ran_at=datetime.now(UTC),
                checked=result.checked,
                drifted=len(result.drift),
                skipped=len(result.skipped),
            )
        )
    return {"checked": result.checked, "drifted": len(result.drift)}


async def run_gate_job(ctx: dict, run_id: str) -> str:
    """Gate a kept draft. **Not a pipeline run** — `docs/design/execution-boundary.md` §3.

    This is the job this module's docstring was written for and never got: it named a stub gate
    at up to 900s as the thing that does not belong in a request, and then shipped with
    `check_sources` alone.
    """
    await gate_service.execute(run_id)
    return run_id


class WorkerSettings:
    functions = [check_sources, run_gate_job, forge_jobs.sync_forge_sources]
    """**Everything that is not a model call.** The split from `AIWorkerSettings` is about
    starvation: a catalogue sync is seconds and somebody is waiting on it, and a generation is
    measured at 227s. `test_the_two_worker_function_lists_are_disjoint` holds them apart, because
    a job on both lists would land on whichever queue the caller happened to pick."""
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
    cron_jobs = [cron(check_sources, hour=3, minute=0)]
    """03:00 daily, which is what the queue's strip promises when it says *next nightly*.

    **Not `run_at_startup`.** A container restart is not a check-worthy event, and a strip
    reading *checked 4 seconds ago* after every deploy would be measuring deploys. The cadence
    is also what the cost affords: `ops.check` walks every contract against its source, 0.48s
    over twelve and roughly three minutes at the 5,800 the design talks about."""

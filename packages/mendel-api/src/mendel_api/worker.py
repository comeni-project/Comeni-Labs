"""Background work. Nothing long-running may sit in a request.

`ops.check` walks every contract against its source; the forge's own measurements put a
model fill at 227s for one module and a stub gate at up to 900s cold. None of that belongs
in a request, and ARQ is where it goes.
"""

import logging
from datetime import UTC, datetime

from arq import cron
from arq.connections import RedisSettings
from mendel_forge import ops

from mendel_api.db import session_scope
from mendel_api.models import SourceCheck
from mendel_api.services import forge_jobs
from mendel_api.services import gates as gate_service
from mendel_api.settings import settings

log = logging.getLogger(__name__)


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


async def sync_every_source(ctx: dict) -> dict[str, int]:
    """Refresh every registered catalogue. Hourly, and once on startup.

    **Derived from `sources.adapters()`, never a written-out list.** A source registered there
    and missing from a schedule here would be a source that silently never refreshes, and the
    symptom — a catalogue that is quietly months old — is one nobody reports.

    **Hourly is affordable because the sync is two requests, and usually one.** The adapter
    resolves the branch head first and returns `unchanged` when the commit has not moved, so a
    quiet hour costs a single API call per source; a moved commit costs one more and ten
    seconds. Before the archive rewrite this cadence would have been absurd — a walk was ~2,400
    requests against a 5,000-per-hour budget, which is what made the catalogue something you
    pressed a button for and then never did.

    **`run_at_startup` is deliberate here and deliberately absent on `check_sources`.** They
    answer different questions. A drift check asks *has the registry moved away from its
    sources*, and running it on every deploy would measure deploys. This asks *what exists
    upstream*, and a stack that comes up with an empty or stale catalogue shows a board that is
    wrong on its first screen — which is exactly how the forge shipped, with `—` where a total
    belongs.

    A failure on one source does not stop the others: they are independent catalogues and one
    unreachable host must not hide the rest. Each failure is already recorded as a snapshot row
    by `sync_forge_sources` itself, so this returns counts and lets the refusal be visible where
    a curator looks for it.
    """
    from mendel_forge import sources

    counts: dict[str, int] = {}
    for name in sorted(sources.adapters()):
        try:
            counts[name] = await forge_jobs.sync_forge_sources(ctx, name)
        except Exception as failure:  # noqa: BLE001 - one bad source may not stop the rest
            log.warning("scheduled sync of %s failed: %r", name, failure)
            counts[name] = -1
    return counts


async def run_gate_job(ctx: dict, run_id: str) -> str:
    """Gate a kept draft. **Not a pipeline run** — `docs/design/execution-boundary.md` §3.

    This is the job this module's docstring was written for and never got: it named a stub gate
    at up to 900s as the thing that does not belong in a request, and then shipped with
    `check_sources` alone.
    """
    await gate_service.execute(run_id)
    return run_id


class WorkerSettings:
    functions = [
        check_sources,
        run_gate_job,
        forge_jobs.sync_forge_sources,
        forge_jobs.scaffold_forge_adaptation,
        forge_jobs.publish_forge_adaptation,
    ]
    """**Everything that is not a model call.** The split from `AIWorkerSettings` is about
    starvation: a catalogue sync is seconds and somebody is waiting on it, and a generation is
    measured at 227s. `test_the_two_worker_function_lists_are_disjoint` holds them apart, because
    a job on both lists would land on whichever queue the caller happened to pick."""
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
    cron_jobs = [
        cron(check_sources, hour=3, minute=0),
        cron(sync_every_source, minute=7, run_at_startup=True),
    ]
    """`check_sources` at 03:00 daily; `sync_every_source` hourly and on startup.

    **Two schedules because they are two questions.** A drift check asks whether the registry
    has moved away from its sources and costs a full walk of every contract — 0.48s over twelve
    and roughly three minutes at the 5,800 the design talks about — so it is nightly, and it is
    *not* `run_at_startup`: a container restart is not a check-worthy event, and a strip reading
    *checked 4 seconds ago* after every deploy would be measuring deploys.

    A catalogue sync asks what exists upstream, costs one request when nothing moved, and is
    what a curator sees on the first screen. An empty or stale catalogue after a deploy is a
    board that is wrong before anybody touches it, which is how the forge shipped.

    **`minute=7` rather than `minute=0`.** Every scheduler in the world fires on the hour, and
    a public API is measurably happier a few minutes off it. The specific number is arbitrary
    and only needs to be stable.

    **`unique=True` is arq's default and is load-bearing here.** Two worker replicas would
    otherwise each start a sync at the same minute, and two concurrent walks of one catalogue is
    exactly what exhausted an hour's rate-limit budget on 2026-09-06."""

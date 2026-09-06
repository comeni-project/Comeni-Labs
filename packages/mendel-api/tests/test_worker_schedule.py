"""What the worker runs on its own.

`cron_jobs` was `[]` with a docstring naming this phase: *"the nightly schedule lands with
Compose, where there is a Redis to run it"*. There are two now, and they answer two different
questions — which is why every assertion here is **per job** rather than over the list.

The first version asserted `cron_jobs == [check_sources]` and *nothing* runs at startup. Both
were true and both were about the only job that existed; adding a second broke them without
either property being wrong. A test that says "these are all the jobs" has to be edited by
whoever adds one, which is the point of the first assertion below — but a test that says "no
job anywhere runs at startup" is a claim about a policy nobody made.
"""

import asyncio

import pytest
from mendel_api import worker
from mendel_api.worker import WorkerSettings, check_sources, sync_every_source
from mendel_forge import sources


def _by_name() -> dict:
    return {job.coroutine.__name__: job for job in WorkerSettings.cron_jobs}


def test_these_are_the_scheduled_jobs():
    """Named literally, so adding one means editing this test — which is where somebody
    notices that a new job needs a cadence argued for rather than copied."""
    assert WorkerSettings.cron_jobs, "nothing is scheduled"
    assert sorted(_by_name()) == ["check_sources", "sync_every_source"]


def test_the_drift_check_runs_nightly_and_not_at_startup():
    """`ops.check` walks every contract against its source — 0.48s over twelve, and roughly
    three minutes at the 5,800 the design talks about. Nightly is the cadence the strip
    promises and the one the cost affords.

    Not at startup: a container restart is not a check-worthy event, and a strip reading
    *checked 4 seconds ago* after every deploy is measuring deploys rather than sources.
    """
    job = _by_name()["check_sources"]
    assert job.coroutine is check_sources
    assert (job.hour, job.minute) == (3, 0)
    assert job.run_at_startup is False


def test_the_catalogue_syncs_hourly_and_on_startup():
    """**The opposite cadence, because it answers the opposite question.**

    A drift check asks whether the registry has moved away from its sources. This asks what
    exists upstream — and a stack that comes up with an empty or stale catalogue shows a board
    that is wrong on its first screen, which is how the forge shipped.

    Hourly is affordable only because a sync is two requests and usually one: the adapter
    resolves the branch head and returns `unchanged` when the commit has not moved. Before the
    archive rewrite a walk was ~2,400 requests against a 5,000-per-hour budget, and this
    cadence would have been absurd.
    """
    job = _by_name()["sync_every_source"]
    assert job.coroutine is sync_every_source
    assert job.hour is None, "hourly, not daily"
    assert job.minute == 7, "deliberately off the hour, where every other scheduler fires"
    assert job.run_at_startup is True
    assert job.unique is True, (
        "two replicas would each start a walk of the same catalogue, which is exactly what "
        "exhausted an hour's rate-limit budget on 2026-09-06"
    )


def test_every_registered_source_is_on_the_schedule(monkeypatch):
    """**Derived from the adapters, so registering a source is enough to have it synced.**

    A written-out list here would be a second place that decides which sources exist, and the
    failure mode is silent: a source that is registered, reachable, adaptable and simply never
    refreshed. Nothing on any screen says *this catalogue is four months old*.

    Asserted through the function rather than by reading it, because the point is that the
    schedule covers whatever `adapters()` holds — including one added tomorrow.
    """
    registered = set(sources.adapters())
    assert registered, "no adapters registered; this test would assert nothing"

    synced: list[str] = []

    async def record(_ctx, name):
        synced.append(name)
        return 0

    monkeypatch.setattr(worker.forge_jobs, "sync_forge_sources", record)
    asyncio.run(worker.sync_every_source({}))
    assert set(synced) == registered


def test_one_unreachable_source_does_not_stop_the_others(monkeypatch):
    """Two catalogues are independent, and Docker Hub being down must not hide nf-core.

    The refusal is not swallowed — `sync_forge_sources` records a failed snapshot row before it
    raises, which is where a curator sees it. What this holds is only that the loop continues.
    """
    registered = sorted(sources.adapters())
    if len(registered) < 2:
        pytest.skip("with one source this test would assert nothing")

    async def one_fails(_ctx, name):
        if name == registered[0]:
            raise RuntimeError("upstream is down")
        return 7

    monkeypatch.setattr(worker.forge_jobs, "sync_forge_sources", one_fails)
    counts = asyncio.run(worker.sync_every_source({}))

    assert counts[registered[0]] == -1
    assert all(counts[name] == 7 for name in registered[1:])

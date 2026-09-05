"""Queueing forge work, claiming it, and recovering it when a worker does not come back.

**Redis is faked and Postgres is real.** The queue's behaviour that matters here is *does a
duplicate id enqueue twice*, which is one line of bookkeeping; the database's behaviour that
matters is *does a compare-and-swap actually exclude the second worker*, which nothing but a
database can answer. So the pool is a stand-in and the rows are not.
"""

from datetime import UTC, datetime, timedelta

import httpx
import pytest
from mendel_api import jobs
from mendel_api.db import session_scope
from mendel_api.models import ForgeAdaptation, ForgeCatalogueItem, ForgeEvent, ForgeSourceSnapshot
from mendel_api.services import forge_jobs, forge_state
from mendel_forge.workflow import RUNNING, AdaptationState, EventKind
from sqlalchemy import select, text


def _database_is_reachable() -> bool:
    try:
        with session_scope() as session:
            session.execute(text("SELECT 1"))
    except Exception:
        return False
    return True


needs_db = pytest.mark.skipif(
    not _database_is_reachable(), reason="no database — run `docker compose up -d postgres`"
)


class FakePool:
    """ARQ's `enqueue_job` contract, reduced to the part that matters.

    **It returns `None` for an id it has already seen**, which is what ARQ does and what the
    whole job-id scheme rests on. A fake that always returned a job would make every duplicate
    test pass against nothing.
    """

    def __init__(self) -> None:
        self.seen: set[str] = set()
        self.calls: list[tuple[str, tuple, str | None, str]] = []
        self.queue = jobs.DEFAULT_QUEUE

    async def enqueue_job(self, name, *args, _job_id=None):
        self.calls.append((name, args, _job_id, self.queue))
        if _job_id is not None and _job_id in self.seen:
            return None
        if _job_id is not None:
            self.seen.add(_job_id)
        return object()


@pytest.fixture
def pool(monkeypatch) -> FakePool:
    fake = FakePool()

    async def _pool(queue: str) -> FakePool:
        fake.queue = queue
        return fake

    monkeypatch.setattr(jobs, "_pool", _pool)
    return fake


# ── job ids ───────────────────────────────────────────────────────────────────────────


def test_a_job_id_is_built_from_what_the_work_is_about():
    """**Never from a clock or a token.** An id containing `uuid4()` is unique, which is the
    opposite of what is wanted: two deliveries of one job must collide, and only an id computed
    from the same inputs does that."""
    assert jobs.job_id_for("forge", "generate", "abc", "1") == "forge:generate:abc:1"


def test_a_part_carrying_a_colon_is_refused():
    """`a:b` + `c` and `a` + `b:c` join to the same string. Two different jobs sharing an id is
    worse than no id at all — the second is silently dropped, and the drop looks like success."""
    with pytest.raises(ValueError, match="contain no colon"):
        jobs.job_id_for("forge", "generate:extra", "abc")
    with pytest.raises(ValueError, match="non-empty"):
        jobs.job_id_for("forge", "", "abc")


# ── which queue, and duplicates ───────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_generation_goes_to_the_ai_queue(pool):
    """A 227s model call on the default queue makes a catalogue sync wait behind it."""
    await forge_jobs.enqueue_generation("a" * 32)
    (name, args, job_id, queue) = pool.calls[-1]
    assert name == forge_jobs.GENERATE
    assert queue == jobs.AI_QUEUE
    assert job_id == f"forge:generate:{'a' * 32}:1"


@pytest.mark.asyncio
async def test_a_duplicate_delivery_does_not_queue_twice(pool):
    """ARQ delivers at least once, and a redeploy mid-job re-delivers. Without the id, two
    workers start two model calls for one adaptation."""
    assert await forge_jobs.enqueue_generation("a" * 32) is True
    assert await forge_jobs.enqueue_generation("a" * 32) is False


@pytest.mark.asyncio
async def test_the_second_question_in_a_thread_is_not_a_duplicate_of_the_first(pool):
    """A chat answer is keyed on the *message*, not the adaptation. Keying on the adaptation
    would make every turn after the first a duplicate and drop it silently."""
    adaptation = "a" * 32
    assert await forge_jobs.enqueue_answer(adaptation, "m1") is True
    assert await forge_jobs.enqueue_answer(adaptation, "m2") is True
    assert await forge_jobs.enqueue_answer(adaptation, "m1") is False


@pytest.mark.asyncio
async def test_an_enqueue_reports_whether_it_actually_queued(pool):
    """**The return value is the whole point of the id.** ARQ returns `None` for a duplicate
    rather than raising, which is easy to discard — and discarding it turns *this was already
    queued* into *this was queued*, so a caller reports work that will never run."""
    assert await jobs.enqueue("x", job_id="one") is True
    assert await jobs.enqueue("x", job_id="one") is False
    assert await jobs.enqueue("x") is True, "an unkeyed job is never a duplicate"


@pytest.mark.asyncio
async def test_the_three_ordinary_jobs_stay_on_the_default_queue(pool):
    """**The routing is the decision this task settles**, and it is expensive to change later —
    a job that has been landing on one queue in production does not move without a drain.

    Sync reads GitHub and a container registry: network, but not a model. Scaffolding is pure
    derivation. Publishing calls `land.py`. None of the three should wait behind a 227s
    generation.
    """
    await forge_jobs.enqueue_sync("nf-core")
    assert pool.calls[-1][3] == jobs.DEFAULT_QUEUE
    await forge_jobs.enqueue_scaffold("a" * 32)
    assert pool.calls[-1][3] == jobs.DEFAULT_QUEUE
    await forge_jobs.enqueue_publish("a" * 32, "r1")
    assert pool.calls[-1][3] == jobs.DEFAULT_QUEUE


@pytest.mark.asyncio
async def test_publishing_is_keyed_on_the_revision_and_syncing_on_the_source(pool):
    """Publishing an adaptation at two revisions is two different acts; only the second attempt
    at *one* revision is a duplicate. A sync has no version — it either reflects upstream now or
    it is superseded — so pressing the button twice is one walk of sixteen hundred tools."""
    assert await forge_jobs.enqueue_publish("a" * 32, "r1") is True
    assert await forge_jobs.enqueue_publish("a" * 32, "r2") is True
    assert await forge_jobs.enqueue_publish("a" * 32, "r1") is False

    assert await forge_jobs.enqueue_sync("nf-core") is True
    assert await forge_jobs.enqueue_sync("nf-core") is False
    assert await forge_jobs.enqueue_sync("pegi3s") is True


# ── syncing a catalogue ───────────────────────────────────────────────────────────────


class _Adapter:
    """One source adapter, reduced to `sync()`.

    A real adapter walks GitHub and a container registry; nothing here is about whether it
    walks them correctly — `test_source_nfcore.py` and `test_source_pegi3s.py` are. What is
    under test is what the *job* does with a snapshot and with a failure.
    """

    name = "fake"

    def __init__(self, client, *, snapshot=None, blow_up=None):
        self.client = client
        self._snapshot = snapshot
        self._blow_up = blow_up

    async def sync(self, previous=None):
        if self._blow_up is not None:
            raise self._blow_up
        return self._snapshot


def _snapshot(*refs: str):
    from mendel_forge.catalogue import CatalogueItem, SourceSnapshot

    now = datetime.now(UTC)
    return SourceSnapshot(
        source="fake",
        source_revision="abc123",
        synced_at=now,
        items=tuple(
            CatalogueItem(
                id=f"{n:064d}",
                source="fake",
                ref=ref,
                display_name=ref,
                content_digest=f"{n:064d}",
            )
            for n, ref in enumerate(refs, start=1)
        ),
    )


@pytest.fixture
def adapter(monkeypatch):
    """Install a fake adapter under the name `fake`, through the same table the job reads."""

    def install(**kwargs):
        def build(client):
            return _Adapter(client, **kwargs)

        monkeypatch.setattr(forge_jobs, "_adapters", lambda: {"fake": build})

    return install


@needs_db
@pytest.mark.asyncio
async def test_a_sync_stores_what_it_walked(clean_forge, adapter):
    adapter(snapshot=_snapshot("samtools/sort", "fastqc"))
    assert await forge_jobs.sync_forge_sources({}, "fake") == 2
    with session_scope() as session:
        assert session.query(ForgeCatalogueItem).count() == 2


@needs_db
@pytest.mark.asyncio
async def test_a_failed_sync_marks_nothing_absent(clean_forge, adapter):
    """**The defect this guards is silent and large.** A sync marks every item it did not see as
    absent, so a walk that fails halfway — or returns nothing because a token expired — is
    indistinguishable from a source that genuinely removed everything. The second reading
    retires sixteen hundred tools and nobody notices until a build cannot route.
    """
    adapter(snapshot=_snapshot("samtools/sort", "fastqc"))
    await forge_jobs.sync_forge_sources({}, "fake")

    adapter(blow_up=httpx.ConnectError("upstream is down"))
    with pytest.raises(httpx.ConnectError):
        await forge_jobs.sync_forge_sources({}, "fake")

    with session_scope() as session:
        present = session.query(ForgeCatalogueItem).filter_by(present=True).count()
        assert present == 2, "a failed sync must not retire the catalogue"


@needs_db
@pytest.mark.asyncio
async def test_a_failed_sync_is_recorded_rather_than_swallowed(clean_forge, adapter):
    """A swallowed exception leaves a gap in the snapshot record that reads as *nobody has
    synced since Tuesday*, which is a different problem with a different fix."""
    from mendel_api.models import ForgeSourceSnapshot

    adapter(blow_up=httpx.ConnectError("upstream is down"))
    with pytest.raises(httpx.ConnectError):
        await forge_jobs.sync_forge_sources({}, "fake")

    with session_scope() as session:
        recorded = session.scalars(
            select(ForgeSourceSnapshot).where(ForgeSourceSnapshot.source == "fake")
        ).one()
        assert recorded.ok is False
        assert "MI0104" in (recorded.error or "")


@needs_db
@pytest.mark.asyncio
async def test_a_failed_sync_does_not_carry_the_upstream_message(clean_forge, adapter):
    """`MI0102`'s rule, one subsystem over: a registry error names an endpoint and sometimes a
    token, and this string is rendered on a page."""
    from mendel_api.models import ForgeSourceSnapshot

    adapter(blow_up=httpx.ConnectError("https://ghcr.io/v2/ token=ghp_secret123 refused"))
    with pytest.raises(httpx.ConnectError):
        await forge_jobs.sync_forge_sources({}, "fake")

    with session_scope() as session:
        recorded = session.scalars(
            select(ForgeSourceSnapshot).where(ForgeSourceSnapshot.source == "fake")
        ).one()
        assert "ghp_secret" not in (recorded.error or "")
        assert "ghcr.io" not in (recorded.error or "")


@pytest.mark.asyncio
async def test_an_unknown_source_names_the_ones_that_exist():
    """A typo in a source name is the ordinary case, and a bare `KeyError` makes somebody go
    and read a registration table to find out what they meant."""
    with pytest.raises(KeyError, match="known:"):
        await forge_jobs.sync_forge_sources({}, "nf-corr")


def test_the_job_reads_the_adapter_table_rather_than_its_own():
    """A source registered in `sources.adapters()` and missing from a table here would be a
    source the API cannot sync, silently."""
    from mendel_forge import sources

    assert set(forge_jobs._adapters()) == set(sources.adapters())
    assert forge_jobs._adapters(), "an empty table would make that comparison vacuous"


def test_no_job_on_a_worker_list_is_an_unimplemented_stub():
    """A function raising `NotImplementedError` on a worker's list is worse than an absent one:
    it is enqueueable, so the failure arrives at run time on a real adaptation rather than at
    the call site. The three ordinary job bodies are absent for exactly this reason."""
    from mendel_api.ai_worker import AIWorkerSettings
    from mendel_api.worker import WorkerSettings

    listed = [*AIWorkerSettings.functions, *WorkerSettings.functions]
    assert listed, "an empty list would make this assert nothing"
    for function in listed:
        source = (function.__doc__ or "") + repr(function.__code__.co_consts)
        assert "NotImplementedError" not in source, f"{function.__name__} is a stub on a queue"


def test_source_sync_is_not_an_ai_job():
    """It reads GitHub and a container registry — network, but not a model. On the AI queue a
    catalogue refresh would wait behind a generation for no reason."""
    assert forge_jobs.SYNC not in forge_jobs.AI_JOBS
    assert {forge_jobs.GENERATE, forge_jobs.ANSWER} == forge_jobs.AI_JOBS


def test_the_two_worker_function_lists_are_disjoint():
    """A job on both lists could be enqueued to either queue, and which one it landed on would
    depend on the caller rather than on what the job does."""
    from mendel_api.ai_worker import AIWorkerSettings
    from mendel_api.worker import WorkerSettings

    ai = {f.__name__ for f in AIWorkerSettings.functions}
    ordinary = {f.__name__ for f in WorkerSettings.functions}
    assert ai, "an empty list would make the check below assert nothing"
    assert ai & ordinary == set()
    assert ai == forge_jobs.AI_JOBS


def test_the_ai_worker_runs_one_job_at_a_time_by_default():
    """A local Ollama serves one request at a time, so a second concurrent call makes both
    slower rather than either faster; a hosted provider has a rate limit the worker cannot see.
    One is correct in both places."""
    from mendel_api.ai_worker import AIWorkerSettings

    assert AIWorkerSettings.max_jobs == 1
    assert AIWorkerSettings.queue_name == "arq:queue:ai"


def test_the_job_timeout_and_the_reclaim_threshold_are_one_setting():
    """Two numbers would have to be kept in a sensible relation by whoever edits them, and a
    reclaim threshold below the job timeout sweeps rows that are still being worked on."""
    from mendel_api.ai_worker import AIWorkerSettings
    from mendel_api.settings import settings

    assert AIWorkerSettings.job_timeout == settings.ai_job_timeout_seconds


# ── the halves of RUNNING ─────────────────────────────────────────────────────────────


def test_the_held_halves_cover_running():
    """A worker-held state in neither half is a state no sweep reclaims — rule 7 failing
    quietly. `ORDINARY_HELD` is derived, so adding a state to `RUNNING` puts it in exactly one
    half rather than in none."""
    assert forge_state.AI_HELD | forge_state.ORDINARY_HELD == RUNNING
    assert frozenset() == forge_state.AI_HELD & forge_state.ORDINARY_HELD


# ── claiming, and recovering ──────────────────────────────────────────────────────────


@pytest.fixture
def item(clean_forge) -> str:
    now = datetime.now(UTC)
    with session_scope() as session:
        session.add(
            ForgeSourceSnapshot(
                id="s" * 32, source="nf-core", started_at=now, finished_at=now, ok=True
            )
        )
        session.flush()
        session.add(
            ForgeCatalogueItem(
                id="i" * 64,
                snapshot_id="s" * 32,
                source="nf-core",
                ref="samtools/sort",
                display_name="samtools sort",
                metadata_json={},
                content_digest="d" * 64,
                first_seen_at=now,
                last_seen_at=now,
            )
        )
    return "i" * 64


def _queued(item: str) -> str:
    adaptation = forge_state.begin(item, who="rafael")
    forge_state.move(
        adaptation,
        AdaptationState.QUEUED,
        expect=AdaptationState.SCAFFOLDING,
        row_version=1,
        actor="rafael",
        kind=EventKind.QUEUED,
    )
    return adaptation


def _state(adaptation_id: str) -> AdaptationState:
    with session_scope() as session:
        return AdaptationState(session.get(ForgeAdaptation, adaptation_id).state)


@needs_db
@pytest.mark.asyncio
async def test_a_claim_moves_a_queued_adaptation_to_generating(item):
    adaptation = _queued(item)
    ended = await forge_jobs.generate_forge_revision({"job_id": "j1"}, adaptation)
    assert ended == AdaptationState.GENERATING.value
    assert _state(adaptation) is AdaptationState.GENERATING


@needs_db
@pytest.mark.asyncio
async def test_a_duplicate_delivery_that_reaches_the_worker_is_skipped_not_failed(item):
    """The id has aged out of Redis, or the job was re-delivered after finishing. The row is no
    longer `queued`, and **that is the mechanism working** — raising would mark the job failed
    and ARQ would retry it, which is the same duplicate with a delay in front of it."""
    adaptation = _queued(item)
    await forge_jobs.generate_forge_revision({"job_id": "j1"}, adaptation)
    again = await forge_jobs.generate_forge_revision({"job_id": "j1"}, adaptation)
    assert again == AdaptationState.GENERATING.value
    assert _state(adaptation) is AdaptationState.GENERATING


@needs_db
@pytest.mark.asyncio
async def test_the_claim_is_attributed_to_the_job_that_made_it(item):
    """`worker` alone would attribute every claim to the same actor, and a reviewer looking at
    a stuck adaptation needs the job id to find it in a log."""
    adaptation = _queued(item)
    await forge_jobs.generate_forge_revision({"job_id": "abc123"}, adaptation)
    with session_scope() as session:
        claimed = session.scalars(
            select(ForgeEvent).where(
                ForgeEvent.adaptation_id == adaptation,
                ForgeEvent.kind == EventKind.CLAIMED.value,
            )
        ).one()
        assert claimed.actor == "ai-worker:abc123"
        assert claimed.from_state == AdaptationState.QUEUED.value


@needs_db
@pytest.mark.asyncio
async def test_a_worker_that_never_came_back_is_failed_at_the_stage_it_held(item):
    """Rule 7. The row keeps `failed_stage`, so a person's `retry` resumes where it stopped
    rather than starting over."""
    adaptation = _queued(item)
    await forge_jobs.generate_forge_revision({"job_id": "j1"}, adaptation)

    reclaimed = await forge_jobs.reclaim(after=-1)
    assert reclaimed == [adaptation]
    assert _state(adaptation) is AdaptationState.FAILED

    resumed = forge_state.retry(adaptation, row_version=4, actor="rafael")
    assert resumed.state is AdaptationState.QUEUED


@needs_db
@pytest.mark.asyncio
async def test_a_reclaim_says_why_in_a_code_a_page_can_render(item):
    """`MI0103`. The event is `failed` rather than `reclaimed`, because what a reader needs
    first is *this failed and why* — a separate kind would compete with `failed` in every
    count and hide that it did."""
    adaptation = _queued(item)
    await forge_jobs.generate_forge_revision({"job_id": "j1"}, adaptation)
    await forge_jobs.reclaim(after=-1)
    with session_scope() as session:
        failed = session.scalars(
            select(ForgeEvent).where(
                ForgeEvent.adaptation_id == adaptation,
                ForgeEvent.kind == EventKind.FAILED.value,
            )
        ).one()
        assert "MI0103" in failed.detail
        assert failed.from_state == AdaptationState.GENERATING.value


@needs_db
@pytest.mark.asyncio
async def test_a_job_still_inside_its_timeout_is_not_reclaimed(item):
    """*The worker died* and *the model is slow* look identical from the row, so the only thing
    separating them is time — and sweeping too early fails a call that is about to succeed."""
    adaptation = _queued(item)
    await forge_jobs.generate_forge_revision({"job_id": "j1"}, adaptation)
    assert await forge_jobs.reclaim(after=3600) == []
    assert _state(adaptation) is AdaptationState.GENERATING


@needs_db
@pytest.mark.asyncio
async def test_a_reclaim_that_loses_a_race_skips_rather_than_raising(item):
    """The worker was slow rather than gone, and it finished between the sweep and the write.
    Losing that race is the correct outcome: the sweep's job is to catch what is abandoned."""
    adaptation = _queued(item)
    await forge_jobs.generate_forge_revision({"job_id": "j1"}, adaptation)
    forge_state.move(
        adaptation,
        AdaptationState.VALIDATING,
        expect=AdaptationState.GENERATING,
        row_version=3,
        actor="worker",
        kind=EventKind.GENERATED,
    )
    stale_now = datetime.now(UTC) + timedelta(hours=1)
    assert forge_state.stale(stale_now) == [adaptation]
    assert _state(adaptation) is AdaptationState.VALIDATING


@needs_db
def test_the_sweep_reads_the_states_it_is_given(item):
    """`stale()` enumerated `(generating, validating)` inline until 2026-09-05 — a second answer
    to a question `workflow.RUNNING` already answered, and the two disagreed the moment
    `RUNNING` gained `scaffolding` and `publishing`."""
    forge_state.begin(item, who="rafael")
    future = datetime.now(UTC) + timedelta(hours=1)
    assert forge_state.stale(future) == [], "scaffolding is not the AI worker's to sweep"
    assert forge_state.stale(future, states=forge_state.ORDINARY_HELD) != []


def test_a_provider_failure_reaches_the_page_as_a_code_and_not_as_a_stack():
    """`forge_event.detail` is rendered to a curator, and a provider error carries an endpoint,
    sometimes a key prefix, and always a stack. `GateFailure` learned this once already."""
    failure = TimeoutError("connect to http://10.0.0.4:11434 failed, key sk-abc123...")
    detail = forge_jobs.sanitised(failure, where="generation")
    assert "MI0102" in detail
    assert "TimeoutError" in detail, "the *kind* of failure is a different story for a curator"
    assert "10.0.0.4" not in detail
    assert "sk-abc" not in detail

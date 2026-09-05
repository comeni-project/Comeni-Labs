"""The five jobs, and what each one claims before it does anything.

**Every job claims its row before it works, and the claim is a compare-and-swap.** ARQ delivers
at least once: a redeploy mid-job re-delivers it, and two workers then start two model calls for
one adaptation. `jobs.job_id_for` makes the duplicate a no-op at the queue, and the claim here
is what holds when the first job has already finished and the id has aged out of Redis. Two
mechanisms, and they are not the pair the journal keeps warning about — delete the job id and a
redeploy costs two model calls; delete the claim and the *second* one overwrites the first's
revision. Different defects, both real.

**A provider failure becomes a coded diagnostic and the detail goes to the log.** `forge_event`
is rendered on a page a curator reads, and a provider's error carries an endpoint, sometimes a
key prefix, and always a stack. `GateFailure` learned this once already: the category is parsed
and the output stays on the machine that produced it. `MI0102` is the code, and the log line
beside it is where somebody debugging actually looks.

**Nothing here calls a model directly.** `mendel_forge.ai.generate.run` does, behind a `Client`
this module builds — so the orchestration is testable with a scripted transport and this file
stays about *claiming, recording and failing*.
"""

import asyncio
import logging
from datetime import UTC, datetime, timedelta

import httpx
from comeni_core.diagnostics import coded
from mendel_forge.workflow import AdaptationState, EventKind

from mendel_api import jobs
from mendel_api.db import session_scope
from mendel_api.models import ForgeAdaptation, ForgeCatalogueItem
from mendel_api.services import forge_catalogue, forge_state
from mendel_api.settings import settings

log = logging.getLogger(__name__)

GENERATE = "generate_forge_revision"
ANSWER = "answer_forge_review_message"
SCAFFOLD = "scaffold_forge_adaptation"
PUBLISH = "publish_forge_adaptation"
SYNC = "sync_forge_sources"

AI_JOBS = frozenset({GENERATE, ANSWER})
"""The two that reach a provider. **Source sync is deliberately not one of them** — it reads
GitHub and a container registry, which is network but not a model, and putting it on the AI
queue would make a catalogue refresh wait behind a 227s generation for no reason."""


def _read(adaptation_id: str) -> tuple[AdaptationState, int]:
    """The current state and version, for a caller that is about to compare against them."""
    with session_scope() as session:
        row = session.get(ForgeAdaptation, adaptation_id)
        if row is None:
            raise KeyError(adaptation_id)
        return AdaptationState(row.state), row.row_version


async def enqueue_generation(adaptation_id: str, *, revision: str = "1") -> bool:
    """Queue one generation. `False` when it was already queued.

    The id is `forge:generate:<adaptation>:<revision>` — **what the work is about, never a
    token**. An id containing `uuid4()` is unique, which is the opposite of what is wanted: two
    deliveries of one job must collide.
    """
    return await jobs.enqueue(
        GENERATE,
        adaptation_id,
        job_id=jobs.job_id_for("forge", "generate", adaptation_id, revision),
        queue=jobs.AI_QUEUE,
    )


async def enqueue_answer(adaptation_id: str, message_id: str) -> bool:
    """Queue one review-chat answer, keyed on the message rather than the adaptation.

    A conversation has many turns and each is its own piece of work; keying on the adaptation
    would make the second question in a thread a duplicate of the first and silently drop it.
    """
    return await jobs.enqueue(
        ANSWER,
        adaptation_id,
        message_id,
        job_id=jobs.job_id_for("forge", "answer", adaptation_id, message_id),
        queue=jobs.AI_QUEUE,
    )


async def generate_forge_revision(ctx: dict, adaptation_id: str) -> str:
    """Claim a queued adaptation for this worker. Returns the state it ended in.

    **The claim is all this does today, and that is stated rather than implied.** What follows
    it — load the bundle, compose the dossier, call `mendel_forge.ai.generate.run`, render the
    proposal, write the revision, walk to `validating` and then `review` — is the integration
    where Task 6's `Validate` seam meets this worker, and it needs the workspace read path and a
    configured model lane. Building it inside this function would put the whole of that behind a
    signature whose failure mode is a state machine, which is the wrong place to discover it.

    The claim on its own is not decoration: it is what makes ARQ's at-least-once delivery safe,
    and every test in `test_forge_jobs.py` about duplicates and recovery is about this call.

    Returning the state rather than `None` so ARQ's own result record says something a person
    can read without joining it to anything.
    """
    state, version = await asyncio.to_thread(_read, adaptation_id)
    if state is not AdaptationState.QUEUED:
        # **Not an error.** A duplicate delivery whose first copy already claimed the row lands
        # here, and it is the mechanism working. Raising would mark the job failed and ARQ
        # would retry it, which is the same duplicate again with a delay in front of it.
        log.info("generation skipped: %s is %s, not queued", adaptation_id, state)
        return state.value

    await asyncio.to_thread(
        forge_state.claim, adaptation_id, row_version=version, worker=_worker(ctx)
    )
    return AdaptationState.GENERATING.value


async def answer_forge_review_message(ctx: dict, adaptation_id: str, message_id: str) -> str:
    """Answer one review-chat turn.

    **Moves no adaptation state**, which is why it takes no version: a conversation about a
    candidate does not change where the candidate is in its lifecycle, and a chat that could
    move an adaptation would be a chat that can approve one. That is not a simplification —
    it is the reason this job is safe to run beside a generation on the same adaptation.

    Like `generate_forge_revision`, the body that composes a `ForgeReviewRequest` and calls a
    provider is the integration piece, not this. What is settled and load-bearing here is the
    routing: it is on the AI queue, its job id is keyed on the *message* rather than the
    adaptation, and door 5 is what it crosses.
    """
    log.info("answering review message %s on %s", message_id, adaptation_id)
    return message_id


def _worker(ctx: dict) -> str:
    """Who to attribute a transition to.

    ARQ puts a job id in the context; that is the most specific true thing available, and it is
    what a reviewer needs in order to find the job in a log. `worker` alone would attribute
    every claim to the same actor.

    **It said `ai-worker:` until the scaffold job arrived**, which was true of both callers at
    the time and false the moment a job on the ordinary queue used it. A prefix naming a worker
    a transition did not come from is worse than no prefix: it sends whoever is reading the
    audit to the wrong log.
    """
    return f"worker:{ctx.get('job_id', 'unknown')}"


def sanitised(failure: Exception, *, where: str) -> str:
    """A provider failure as something `forge_event.detail` may carry.

    **The exception's own text does not go in.** A provider error carries an endpoint, sometimes
    a key prefix, and always a stack — and `detail` is rendered on the adaptation page. The type
    name is kept because *a timeout* and *a refusal* are different stories for a curator, and
    the rest goes to the log at the call site.
    """
    return coded("MI0102", f"the model could not be reached during {where}") + (
        f"\n  the worker recorded a {type(failure).__name__}; the detail is in its log"
    )


async def enqueue_sync(source: str) -> bool:
    """Refresh one source's catalogue. **The ordinary queue**, not the AI one.

    Keyed on the source name, so pressing *sync* twice while one is running is a no-op rather
    than two walks of sixteen hundred tools. There is no revision or attempt in the id because
    a catalogue sync has no version — it either reflects upstream now or it is superseded.
    """
    return await jobs.enqueue(SYNC, source, job_id=jobs.job_id_for("forge", "sync", source))


async def enqueue_scaffold(adaptation_id: str) -> bool:
    """Build the deterministic bundle for a new adaptation. Ordinary queue — no model."""
    return await jobs.enqueue(
        SCAFFOLD, adaptation_id, job_id=jobs.job_id_for("forge", "scaffold", adaptation_id)
    )


async def enqueue_publish(adaptation_id: str, revision_id: str) -> bool:
    """Land an approved revision. Keyed on the *revision*, because publishing an adaptation
    twice at two revisions is two different acts and only the second is a duplicate of itself."""
    return await jobs.enqueue(
        PUBLISH,
        adaptation_id,
        revision_id,
        job_id=jobs.job_id_for("forge", "publish", adaptation_id, revision_id),
    )


async def sync_forge_sources(ctx: dict, source: str) -> int:
    """Walk one upstream catalogue and reconcile the stored items against it. Returns the count.

    **Touches no adaptation, so there is nothing to claim.** A sync is about the catalogue, and
    an adaptation already in flight keeps the snapshot it was started from — which is why this
    is the one forge job with no compare-and-swap in it, and why it is safe beside anything.

    **A failure is recorded, not swallowed.** `record_failure` writes a snapshot row and touches
    no item, so *the sync broke* and *upstream removed everything* stay distinguishable. Without
    it they are the same empty catalogue, and the second one silently marks sixteen hundred
    tools absent.

    The exception is re-raised after recording, because ARQ's retry is the right response to a
    transient upstream and this job is safe to run again — unlike a generation, it costs a
    catalogue walk rather than a model call.
    """
    started = datetime.now(UTC)
    adapter_for = _adapters().get(source)
    if adapter_for is None:
        raise KeyError(f"no source adapter named {source!r}; known: {sorted(_adapters())}")

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            snapshot = await adapter_for(client).sync()
    except Exception as failure:
        log.warning("sync of %s failed: %r", source, failure)
        await asyncio.to_thread(
            forge_catalogue.record_failure,
            source,
            error=coded("MI0104", f"the {source} catalogue could not be read"),
            started_at=started,
        )
        raise

    await asyncio.to_thread(forge_catalogue.record, snapshot, started_at=started)
    return len(snapshot.items)


def _adapters() -> dict[str, type]:
    """Imported inside the call so `httpx` is not pulled in by importing this module.

    `sources.adapters()` makes the same argument for the same reason, and this is a second
    call to it rather than a second table — a source registered there and missing here would be
    a source the API cannot sync, silently.
    """
    from mendel_forge import sources

    return sources.adapters()


def _item_and_state(adaptation_id: str) -> tuple[object, AdaptationState, int]:
    """The catalogue item this adaptation is about, plus the row's state and version.

    One session rather than three calls, because the three facts have to be consistent: reading
    the state, then the item, then the version leaves two windows in which the row can move, and
    the compare-and-swap that follows would then be against a version from a different moment.
    """
    from mendel_forge.catalogue import CatalogueItem

    with session_scope() as session:
        row = session.get(ForgeAdaptation, adaptation_id)
        if row is None:
            raise KeyError(adaptation_id)
        item_row = session.get(ForgeCatalogueItem, row.catalogue_item_id)
        if item_row is None:
            raise KeyError(row.catalogue_item_id)
        return (
            CatalogueItem.model_validate(item_row.metadata_json),
            AdaptationState(row.state),
            row.row_version,
        )


async def scaffold_forge_adaptation(ctx: dict, adaptation_id: str) -> str:
    """Fetch the source, derive the deterministic bundle, write it, and queue the adaptation.

    **Everything a model is later asked about is decided here, and none of it by a model.** The
    contract skeleton, the holes and their candidate sets, the container reference, the module
    skeleton for a source that ships none — all arithmetic over declared data. That is why the
    job is on the ordinary queue and why its output is byte-identical for identical inputs.

    The registry digest is recorded on the bundle rather than left implicit: two runs that
    disagree are two different registries, which `derive()` says is a fact to record rather than
    a nondeterminism to hide.

    **A failure here fails at `scaffolding`, not at `queued`.** Rule 9, and `retry_target` reads
    it: a scaffold that could not be built is not repaired by queueing a model, so the retry has
    to resume here rather than one stage on.
    """
    item, state, version = await asyncio.to_thread(_item_and_state, adaptation_id)
    if state is not AdaptationState.SCAFFOLDING:
        log.info("scaffold skipped: %s is %s, not scaffolding", adaptation_id, state)
        return state.value

    try:
        await asyncio.to_thread(_derive_and_write, adaptation_id, item)
    except Exception as failure:
        log.warning("scaffold of %s failed: %r", adaptation_id, failure)
        await asyncio.to_thread(
            forge_state.fail,
            adaptation_id,
            stage=AdaptationState.SCAFFOLDING,
            row_version=version,
            actor=_worker(ctx),
            detail=coded("MI0105", "the source could not be read or the scaffold not written"),
        )
        return AdaptationState.FAILED.value

    moved = await asyncio.to_thread(
        forge_state.move,
        adaptation_id,
        AdaptationState.QUEUED,
        expect=AdaptationState.SCAFFOLDING,
        row_version=version,
        actor=_worker(ctx),
        kind=EventKind.SCAFFOLDED,
    )
    return moved.state.value


def _derive_and_write(adaptation_id: str, item) -> None:
    """The deterministic half, off the event loop.

    **Blocking on purpose, and in a thread on purpose.** `layers.load` reads a directory tree and
    `write_bundle` writes one; both are synchronous and neither is fast enough to sit on the
    loop. `asyncio.to_thread` is what keeps one slow scaffold from stalling every other job the
    ordinary worker is running.
    """
    import asyncio as _asyncio

    import httpx
    from comeni_core.artifact.digest import digest_of_directory
    from mendel_forge import bundle
    from mendel_forge.workspace import Workspace
    from mendel_resolver import layers

    async def fetch():
        async with httpx.AsyncClient(timeout=60.0) as client:
            return await _adapters()[item.source](client).bundle(item)

    source = _asyncio.run(fetch())
    stack = layers.load(settings.registry_root)
    derived = bundle.derive(
        source,
        stack,
        adaptation_id=adaptation_id,
        registry_digest=digest_of_directory(settings.registry_root),
    )
    Workspace(root=settings.workspace_root).write_bundle(derived)


# **`publish_forge_adaptation` is still absent, and there is no stub for it.** A function raising
# `NotImplementedError` on a worker's function list is worse than an absent one: it is
# enqueueable, so the failure arrives at run time on a real adaptation instead of at the call
# site. Its `enqueue_publish` helper above is real and settled — which queue, and that the id is
# keyed on the revision — and those are the decisions that get expensive once a job has been
# landing somewhere in production.


async def reclaim(*, after: int) -> list[str]:
    """Fail every adaptation a worker was holding for longer than `after` seconds.

    Rule 7. Reclaimed rather than retried: retrying automatically is how a job that kills its
    worker kills every worker in turn. The row keeps `failed_stage`, so a person's `retry`
    resumes where it stopped.

    **The event written is `failed`, not `reclaimed`**, even though `EventKind.RECLAIMED`
    exists. What a reader needs first is *this failed and why*; a separate kind would say how it
    failed and hide that it did, and it would compete with `failed` in every count on the page.
    The distinction lives in `detail`, which carries `MI0103`, so *show me what was reclaimed*
    is a query for that code.
    """
    cutoff = datetime.now(UTC) - timedelta(seconds=after)
    lost = await asyncio.to_thread(forge_state.stale, cutoff)
    reclaimed = []
    for adaptation_id in lost:
        state, version = await asyncio.to_thread(_read, adaptation_id)
        try:
            await asyncio.to_thread(
                forge_state.fail,
                adaptation_id,
                stage=state,
                row_version=version,
                actor="reclaim",
                detail=coded("MI0103", "the worker holding this job did not come back"),
            )
        except (ValueError, KeyError) as refused:
            # The row moved between the sweep and the write — the worker was slow rather than
            # gone, and it finished. Losing that race is the correct outcome and not worth an
            # exception: the sweep's job is to catch what is abandoned, not to win.
            log.info("reclaim skipped %s: %s", adaptation_id, refused)
            continue
        reclaimed.append(adaptation_id)
    return reclaimed

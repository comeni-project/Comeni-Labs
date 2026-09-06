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
from comeni_core.artifact.pipeline import SCHEMA_VERSION
from comeni_core.diagnostics import coded
from mendel_forge import verify
from mendel_forge.workflow import AdaptationState, EventKind, RevisionState
from sqlalchemy import select

from mendel_api import jobs
from mendel_api.db import session_scope
from mendel_api.models import (
    ForgeAdaptation,
    ForgeCatalogueItem,
    ForgeEvent,
    ForgeMessage,
    ForgeRevision,
)
from mendel_api.services import forge_catalogue, forge_state
from mendel_api.settings import model_access, settings

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
    """Claim a queued adaptation, put its holes to a model, and record what came back.

    The whole walk: claim → compose the dossier → `generate.run` → apply the answers → write a
    revision → `validating` → `review`. Returns the state it ended in, so ARQ's own result
    record says something a person can read without joining it to anything.

    **It ends at `review` whether or not validation passed.** The plan's diagram draws both
    arrows into `review` — *checks pass* and *checks fail but the candidate is inspectable* —
    and that is the honest arrangement: a curator can read a failing candidate and its
    diagnostics, and a candidate that never reaches them is one nobody can learn from. What
    `green` records is whether approval is *possible*, and `approval_refusals` is where that is
    enforced.

    **The failure path fails at `generating`.** Rule 9 again, and the retry then resumes as a
    queued attempt rather than re-scaffolding — the bundle is fine, the attempt was not.
    """
    state, version = await asyncio.to_thread(_read, adaptation_id)
    if state is not AdaptationState.QUEUED:
        # **Not an error.** A duplicate delivery whose first copy already claimed the row lands
        # here, and it is the mechanism working. Raising would mark the job failed and ARQ
        # would retry it, which is the same duplicate again with a delay in front of it.
        log.info("generation skipped: %s is %s, not queued", adaptation_id, state)
        return state.value

    claimed = await asyncio.to_thread(
        forge_state.claim, adaptation_id, row_version=version, worker=_worker(ctx)
    )

    try:
        outcome, holes, verdicts = await asyncio.to_thread(_generate, adaptation_id)
    except Exception as failure:
        log.warning("generation for %s failed: %r", adaptation_id, failure, exc_info=True)
        await asyncio.to_thread(
            forge_state.fail,
            adaptation_id,
            stage=AdaptationState.GENERATING,
            row_version=claimed.row_version,
            actor=_worker(ctx),
            detail=_failure_detail(failure),
        )
        return AdaptationState.FAILED.value

    revision_id = await asyncio.to_thread(
        forge_state.add_revision,
        adaptation_id,
        # **`validated` means the checks FINISHED, not that they passed** — `models.ForgeRevision`
        # says so, and a candidate that fails its rungs is still inspectable, which is a
        # reviewable state. So a run that produced a proposal *and* ran the ladder is
        # `validated`; one that produced a proposal the ladder never saw stays `validating`;
        # and one that never produced a proposal is `failed` — there is no candidate to look
        # at, only attempts.
        state=(
            RevisionState.FAILED
            if not outcome.succeeded()
            else RevisionState.VALIDATED
            if verdicts
            else RevisionState.VALIDATING
        ),
        manifest={
            "attempts": [attempt.model_dump(mode="json") for attempt in outcome.attempts],
            "unresolved": list(outcome.unresolved_holes),
        },
        prompt_versions={attempt.prompt_id: attempt.prompt_digest for attempt in outcome.attempts},
    )
    await asyncio.to_thread(
        _record_verdict,
        revision_id,
        outcome=outcome,
        owed=len(outcome.unresolved_holes),
        verdicts=verdicts,
    )

    validating = await asyncio.to_thread(
        forge_state.move,
        adaptation_id,
        AdaptationState.VALIDATING,
        expect=AdaptationState.GENERATING,
        row_version=claimed.row_version,
        actor=_worker(ctx),
        kind=EventKind.GENERATED,
        revision_id=revision_id,
    )
    reviewed = await asyncio.to_thread(
        forge_state.move,
        adaptation_id,
        AdaptationState.REVIEW,
        expect=AdaptationState.VALIDATING,
        row_version=validating.row_version,
        actor=_worker(ctx),
        kind=EventKind.VALIDATED,
        detail=_verdict_line(outcome, holes),
        revision_id=revision_id,
    )
    return reviewed.state.value


def _failure_detail(failure: Exception) -> str:
    """Which coded refusal a generation failure gets.

    A missing model lane is a *configuration* fact and says so; anything else is treated as the
    provider being unreachable, because from here a refusal, a timeout and a 500 are the same
    row. `sanitised` is what keeps the endpoint and the key out of it.
    """
    if isinstance(failure, NoModelConfigured):
        return str(failure)
    return sanitised(failure, where="generation")


class NoModelConfigured(RuntimeError):
    """`COMENI_AI_MODEL` is empty. **The no-AI lane, not a crash.**

    A laboratory that wants no model calls simply does not configure one, and the adaptation
    should say that on its page rather than leave a worker traceback in a log nobody reads.
    """


def _verdict_line(outcome, holes) -> str:
    """One sentence a curator reads on the timeline.

    Says what the attempt achieved rather than that it happened: how many questions it closed,
    how many it declined with `needed_evidence`, and how many repairs it took to get there.
    """
    if not outcome.succeeded():
        return coded("MI0107", "no proposal validated within the repair budget") + (
            f"\n  {len(outcome.attempts)} attempt(s); the last diagnostics are on the revision"
        )
    answered = len(outcome.proposal.analysis.answers)
    declined = len(outcome.proposal.analysis.unresolved)
    return (
        f"answered {answered} of {len(holes)}, declined {declined} for want of evidence, "
        f"after {len(outcome.attempts) - 1} repair(s)"
    )


async def answer_forge_review_message(ctx: dict, adaptation_id: str, message_id: str) -> str:
    """Answer one review-chat turn. **This is what crosses egress door 5.**

    **Moves no adaptation state**, which is why it takes no version: a conversation about a
    candidate does not change where the candidate is in its lifecycle, and a chat that could
    move an adaptation would be a chat that can approve one. That is also why it is safe to run
    beside a generation on the same adaptation.

    **Grounded on the revision the question was asked about**, not on whatever is current. A
    curator asks about the candidate in front of them; answering from a revision that landed
    while they were typing would be answering a different question convincingly.
    """
    try:
        answer = await asyncio.to_thread(_answer, adaptation_id, message_id)
    except Exception as failure:
        log.warning("chat answer for %s failed: %r", message_id, failure, exc_info=True)
        await asyncio.to_thread(_store_refusal, message_id, detail=_failure_detail(failure))
        return message_id

    await asyncio.to_thread(_store_answer, adaptation_id, message_id, answer=answer)
    return message_id


def _answer(adaptation_id: str, message_id: str):
    """Compose the door-5 payload, render the chat prompt, and validate what comes back.

    The `ForgeReviewRequest` is built and then *rendered into* the prompt rather than sent as
    JSON: the payload type is what declares the boundary and what a guard inspects, and the
    prompt is how a model reads it. Building the payload and not using it would be a declared
    boundary nothing crosses, which is worse than none — it reads as checked.
    """
    from comeni_core.artifact.egress import ForgeReviewRequest, ReviewRole, ReviewTurn
    from mendel_forge import prompts
    from mendel_forge.ai.schemas import ChatAnswer, admit_answer
    from mendel_forge.workspace import Workspace

    client = _client()
    workspace = Workspace(root=settings.workspace_root)
    source = workspace.read_source(adaptation_id)
    draft = workspace.read_draft(adaptation_id)

    question, tail, revision_digest = _conversation(adaptation_id, message_id)
    payload = ForgeReviewRequest(
        revision=revision_digest,
        candidate=draft.scaffold.model_dump_json(indent=2),
        evidence=[numbered.excerpt for numbered in source.evidence],
        turns=[
            ReviewTurn(role=ReviewRole(role), content=content) for role, content in tail
        ],
    )
    rendered = prompts.template(prompts.REVIEW_CHAT).render(
        {
            "record": _record_text(payload),
            "conversation": "\n\n".join(f"{turn.role}: {turn.content}" for turn in payload.turns)
            or "(this is the first question)",
            "question": question,
        }
    )
    answer = client.respond(rendered.text, ChatAnswer)
    if answer is None:
        raise RuntimeError(client.last_refusal or "the model declined")
    return admit_answer(answer, evidence_ids={numbered.id for numbered in source.evidence})


def _record_text(payload) -> str:
    """The door-5 payload as the text the chat prompt embeds.

    Rendered from the declared payload rather than from the sources it was built from, so what
    a guard inspects and what a model reads are the same object.
    """
    lines = [f"revision: {payload.revision}", "", "the candidate:", payload.candidate]
    if payload.validation:
        lines += ["", "what validation said:", *[f"  {code}" for code in payload.validation]]
    if payload.evidence:
        lines += ["", "evidence:"]
        lines += [f"  {e.locator}\n    {e.text}" for e in payload.evidence]
    return "\n".join(lines)


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


UNREACHABLE = ("ModelUnavailableError", "TimeoutError", "ConnectError", "APIConnectionError")
"""Exception type names that mean *the lane is broken*, as opposed to *the answer was refused*.

Matched on the **name** rather than by importing the classes, because they come from three
packages — `comeni_ai`, `httpx` and LiteLLM — and importing a transport's exception hierarchy
into the job module would be reaching across the seam `_client` exists to keep.
"""


def sanitised(failure: Exception, *, where: str) -> str:
    """A provider failure as something `forge_event.detail` may carry.

    **The exception's own text does not go in.** A provider error carries an endpoint, sometimes
    a key prefix, and always a stack — and `detail` is rendered on the adaptation page. The type
    name is kept because *a timeout* and *a refusal* are different stories for a curator, and
    the rest goes to the log at the call site.

    **And those two stories now get two codes.** This said *the model could not be reached* for
    every failure on the model path, including one where the model was reached, answered, and had
    its answer refused for not matching the declared shape — which sends somebody to check a
    network that is fine. Found by asking a real local model a review question on 2026-09-05: the
    guarantee held and the reason given for it was false.
    """
    name = type(failure).__name__
    if name in UNREACHABLE:
        return coded("MI0102", f"the model could not be reached during {where}") + (
            f"\n  the worker recorded a {name}; the detail is in its log"
        )
    return coded("MI0113", f"the model answered during {where} and its answer was refused") + (
        f"\n  the worker recorded a {name}; the detail is in its log"
        "\n  nothing was applied to the candidate — try again, or use a larger model"
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
    if source not in _adapters():
        raise KeyError(f"no source adapter named {source!r}; known: {sorted(_adapters())}")

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            snapshot = await _open(source, client).sync()
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


def _open(source: str, client):
    """One adapter, built the only way an adapter may be built.

    Delegating rather than calling the class keeps the upstream credential on `open_adapter`,
    which is where a test can hold it — see `test_source_auth.py`.
    """
    from mendel_forge import sources

    return sources.open_adapter(source, client)


def _client():
    """A `Client` for the configured lane, or a refusal naming the setting.

    Built here rather than held as a module global: the environment is read at construction, and
    a worker that cached one at import would ignore a changed environment on restart in the one
    place where an operator most expects it to be read.

    **The same three names in every lane.** `COMENI_AI_MODEL` with `COMENI_AI_API_KEY` reaches
    a hosted provider; the same model id with `COMENI_AI_BASE_URL` reaches an Ollama on the
    compose network. Nothing here branches on which — invariant 13, and the reason the local
    lane cannot quietly become the degraded one.
    """
    from comeni_ai import Client
    from comeni_ai.access import BASE_URL, MODEL

    access = model_access()
    if access is None:
        raise NoModelConfigured(
            coded("MI0106", "no model is configured, so nothing can be generated")
            + f"\n  set {MODEL} to a LiteLLM model id — `ollama/qwen2.5-coder:14b`"
            + f"\n  and {BASE_URL} for a local endpoint, or an API key for a provider"
            + "\n  leaving it empty is the no-AI lane and is a legitimate way to run the forge"
        )
    return Client(access)


def _model_id() -> str:
    """What goes in `FilledValue.by` for a value a model answered.

    **The model id, not the string "model".** `land.py` copies `by` verbatim into
    `Provenance.drafted_by`, so this ends up in a registry file that outlives the deployment —
    and *which* model proposed a port type is exactly what somebody re-reading a contract in six
    months needs. `how` already carries that it was a model at all.
    """
    access = model_access()
    return access.model if access else ""


def _vocabularies(stack) -> list:
    """§5.3's section 6, from the registry that is actually loaded.

    **Every legal value, whole.** This is the section `MI0400` refuses to truncate, and the
    argument is on `context.compose`: a model shown nine of eleven does not know it was shown
    nine, and its answer passes every schema check on the way back.
    """
    from mendel_forge.ai import select

    return [
        select.vocabulary(
            name="types",
            values=sorted(stack.vocabulary.types),
            note="every semantic type the registry declares:",
        ),
        select.vocabulary(
            name="roles",
            # **`.names`, and the missing word cost every generation.** `stack.roles` is a
            # `RoleVocabulary`, and iterating a Pydantic model yields `(field, value)` pairs —
            # so this passed `[("names", frozenset({...}))]` to a function that joins strings,
            # and `_generate` died on `sequence item 0: expected str instance, tuple found`
            # before the dossier was composed. **No generation had ever reached a model against
            # a real registry**; every test that exercises this path builds the vocabulary
            # segment from a list of strings by hand.
            #
            # Found by running one, on 2026-09-05. `test_the_dossier_is_built_from_a_real_stack`
            # is what fails now instead.
            values=sorted(stack.roles.names),
            note="every role a contract may take:",
        ),
    ]


def _generate(adaptation_id: str):
    """Compose the dossier, call the model, apply the answers, and save the draft.

    Blocking, and run in a thread by its caller: `layers.load` walks a directory tree and the
    provider call is synchronous. Returning the outcome *and* the holes because the caller
    writes a verdict line that counts both.
    """
    from mendel_forge.ai import generate as ai_generate
    from mendel_forge.ai import render, select
    from mendel_forge.ai.context import Budget
    from mendel_forge.workspace import Draft, Workspace
    from mendel_resolver import layers

    client = _client()
    workspace = Workspace(root=settings.workspace_root)
    source = workspace.read_source(adaptation_id)
    holes = workspace.read_holes(adaptation_id)
    stack = layers.load(settings.registry_root)
    draft = workspace.read_draft(adaptation_id)

    dossier = select.analysis_dossier(
        source=source,
        scaffold_holes=holes,
        registry_digest=draft.scaffold.observation.ref_id,
        schema_version=SCHEMA_VERSION,
        vocabularies=_vocabularies(stack),
        instruction="Answer every hole above, or say what evidence would close it.",
        budget=Budget(tokens=settings.ai_context_tokens).characters(),
    )

    def check(proposal) -> tuple:
        """Run the five rungs over what the model just proposed. Diagnostics feed the repair.

        **This is what `validate` was always for**, and it read `lambda _: ()` — so the repair
        prompt was shown *"(none recorded)"* under *what validation said* and had nothing to
        repair against. A model asked to correct a proposal without being told what was wrong
        is a model asked to try again.

        The proposal is applied to a **copy** and never saved here: `run` may call this on an
        attempt it then discards, and a workspace written from inside the loop would leave the
        losing attempt on disk under the winner's name.
        """
        try:
            candidate = render.apply(draft.scaffold, proposal, holes=holes, by=_model_id())
        except Exception as refusal:
            # `apply` refuses a value outside the candidate set (`MF0003`) and an unknown hole
            # (`MF0402`). That IS a validation result — the strongest one — so it goes back as
            # a diagnostic rather than killing the job.
            return (coded("MI0114", "the proposal could not be applied") + f"\n  {refusal}",)
        module = render.module_text(draft.module, proposal) if draft.module else None
        verdicts = verify.verify(
            candidate,
            registry_root=settings.registry_root,
            source_root=settings.registry_root,
            module=module,
        )
        return tuple(
            str(diagnostic) for verdict in verdicts for diagnostic in verdict.diagnostics
        )

    outcome = ai_generate.run(
        client=client, dossier=dossier, holes=holes, validate=check
    )
    if outcome.succeeded():
        filled = render.apply(
            draft.scaffold, outcome.proposal, holes=holes, by=_model_id()
        )
        module = render.module_text(draft.module, outcome.proposal) if draft.module else None
        workspace.write_draft(Draft(name=adaptation_id, scaffold=filled, module=module))
        return outcome, holes, verify.verify(
            filled,
            registry_root=settings.registry_root,
            source_root=settings.registry_root,
            module=module,
        )
    return outcome, holes, []


def _record_verdict(revision_id: str, *, outcome, owed: int, verdicts=()) -> None:
    """Store what the ladder said, and whether approval is possible.

    **`green` is now a statement about a check that happened**, which is what it always claimed
    to be. It was hardcoded `False` beside `MI0108` — *the validation ladder is not wired to
    this worker yet* — and `approval_refusals` reads exactly this field, so **nothing had ever
    been approvable through the front door.** Wiring `verify.verify` is what changed; the
    honesty of the previous state is why it said so rather than reporting green.

    **Green needs the rungs to have run AND every required hole closed.** `refuses()` answers
    the first; `owed` answers the second, and neither implies the other — a candidate can pass
    every rung it reached and still be missing a port nobody could answer.
    """
    ran = bool(verdicts)
    refused = verify.refuses(list(verdicts)) if ran else True
    with session_scope() as session:
        row = session.get(ForgeRevision, revision_id)
        if row is None:
            raise KeyError(revision_id)
        row.validation = {
            "ran": ran,
            "rungs": [
                {
                    "rung": str(verdict.rung),
                    "refused": verdict.refused,
                    "diagnostics": [str(d) for d in verdict.diagnostics],
                }
                for verdict in verdicts
            ],
            "diagnostics": (
                [str(d) for verdict in verdicts for d in verdict.diagnostics]
                if ran
                else list(outcome.last_diagnostics())
            ),
            **(
                {}
                if ran
                else {"why": coded("MI0108", "no candidate reached the validation ladder")}
            ),
        }
        row.green = ran and not refused and owed == 0
        row.unresolved_required = owed


CHAT_TAIL = 6
"""How many prior turns go into a chat prompt.

§5.8: *only the bounded conversation tail*. Unbounded, a long thread eventually pushes the
record out of the window and the model answers from the conversation alone — which is the one
thing grounding on a revision exists to prevent. Six is three exchanges: enough for *what about
the other port* to make sense, short enough that the candidate stays the largest thing present.
"""


def _conversation(adaptation_id: str, message_id: str) -> tuple[str, list[tuple[str, str]], str]:
    """The question, the bounded tail before it, and the revision it is grounded on.

    Read in one session so the three are consistent: a revision that lands between reading the
    question and reading the tail would ground the answer on a candidate the curator never saw.
    """
    from mendel_forge.workflow import MessageRole

    with session_scope() as session:
        asked = session.get(ForgeMessage, int(message_id))
        if asked is None:
            raise KeyError(message_id)
        prior = (
            session.query(ForgeMessage)
            .filter(ForgeMessage.adaptation_id == adaptation_id, ForgeMessage.id < asked.id)
            .order_by(ForgeMessage.id.desc())
            .limit(CHAT_TAIL)
            .all()
        )
        tail = [
            (
                "curator" if row.role == MessageRole.CURATOR.value else "model",
                row.content,
            )
            for row in reversed(prior)
        ]
        adaptation = session.get(ForgeAdaptation, adaptation_id)
        revision = asked.revision_id or (adaptation.current_revision_id if adaptation else None)
        if not revision:
            raise ValueError(
                coded("MI0109", "this question is not attached to any revision")
                + "\n  a chat answer is grounded on one candidate; there is nothing to ground on"
            )
        # `ForgeRevision.id` is 32 hex characters, and `Digest` wants `sha256:` and 64. The
        # revision id *is* the grounding — this spells it as the door's declared shape rather
        # than widening that shape to admit a shorter string.
        return asked.content, tail, "sha256:" + revision.rjust(64, "0")


def _store_answer(adaptation_id: str, message_id: str, *, answer) -> None:
    """Write the model's turn, and mark the question answered.

    Two rows change together: the question stops being `pending` and the answer arrives as its
    own turn. Split across two calls they can disagree, and a question stuck at `pending` beside
    a visible answer is a page that offers to retry something that already happened.
    """
    from mendel_forge.workflow import MessageRole, MessageState

    with session_scope() as session:
        asked = session.get(ForgeMessage, int(message_id))
        if asked is None:
            raise KeyError(message_id)
        asked.state = MessageState.ANSWERED.value
        session.add(
            ForgeMessage(
                adaptation_id=adaptation_id,
                revision_id=asked.revision_id,
                role=MessageRole.ASSISTANT.value,
                state=MessageState.ANSWERED.value,
                content=answer.answer,
                citations=[c.model_dump(mode="json") for c in answer.citations],
                at=datetime.now(UTC),
            )
        )


def _store_refusal(message_id: str, *, detail: str) -> None:
    """Mark a question failed, with a coded reason a page can render.

    **Failed rather than left pending.** A question that stays `pending` after its job died is
    one the page spins on forever, and the curator has no way to tell *thinking* from *gone*.
    """
    from mendel_forge.workflow import MessageState

    with session_scope() as session:
        asked = session.get(ForgeMessage, int(message_id))
        if asked is None:
            raise KeyError(message_id)
        asked.state = MessageState.FAILED.value
        asked.content = f"{asked.content}\n\n{detail}" if asked.content else detail


async def publish_forge_adaptation(ctx: dict, adaptation_id: str, revision_id: str) -> str:
    """Land an approved revision into the registry.

    **`land.py` is the only thing that writes registry files** — invariant 2 — so this claims
    the row, calls it, and does no writing of its own.

    **A refusal returns to `review`, not to `failed`.** The plan draws that arrow and it is the
    right one: `land` refuses on a dirty checkout, a protected branch, or a draft that still has
    holes, and every one of those is something a person fixes and then approves again. Failing
    would send them through `retry`, which re-runs a generation nobody asked for.
    """
    state, version = await asyncio.to_thread(_read, adaptation_id)
    if state is not AdaptationState.PUBLISHING:
        log.info("publish skipped: %s is %s, not publishing", adaptation_id, state)
        return state.value

    try:
        landed = await asyncio.to_thread(_land, adaptation_id, ctx)
    except Exception as failure:
        log.warning("publish of %s failed: %r", adaptation_id, failure, exc_info=True)
        returned = await asyncio.to_thread(
            forge_state.move,
            adaptation_id,
            AdaptationState.REVIEW,
            expect=AdaptationState.PUBLISHING,
            row_version=version,
            actor=_worker(ctx),
            kind=EventKind.FAILED,
            detail=coded("MI0110", "the registry refused this candidate"),
            revision_id=revision_id,
        )
        return returned.state.value

    published = await asyncio.to_thread(
        forge_state.move,
        adaptation_id,
        AdaptationState.PUBLISHED,
        expect=AdaptationState.PUBLISHING,
        row_version=version,
        actor=_worker(ctx),
        kind=EventKind.PUBLISHED,
        detail=landed,
        revision_id=revision_id,
    )
    return published.state.value


def _approval(adaptation_id: str) -> tuple[str, str, str]:
    """Who approved, when, and against which registry. Read from the row and its audit.

    **The approver is the person, never the worker.** `Provenance.approved_by` ends up in a
    registry file that outlives the deployment, and it read `worker:<job id>` — which is a
    statement about which container happened to pick the job up, in the one field invariant 2
    is about. The `approved` event carries the actual name because `forge_state.approve` writes
    it there, so the audit had the answer all along and the file did not.

    `registry_digest` is the digest the candidate was **validated** against, which is what
    `MF0108` compares. Reading it here rather than re-deriving it is the point: re-deriving
    would produce the digest of the registry as it is now, and the check would compare a number
    against itself.
    """
    with session_scope() as session:
        row = session.get(ForgeAdaptation, adaptation_id)
        if row is None:
            raise KeyError(adaptation_id)
        approval = session.scalars(
            select(ForgeEvent)
            .where(
                ForgeEvent.adaptation_id == adaptation_id,
                ForgeEvent.kind == EventKind.APPROVED.value,
            )
            .order_by(ForgeEvent.id.desc())
            .limit(1)
        ).first()
        # No approval event is not a state this job can be in — `approve` writes one before
        # anything is queued — so falling back to the row's owner is a belt on a brace rather
        # than a plausible path. It is still better than attributing to the worker.
        return (
            approval.actor if approval else row.who,
            (approval.at if approval else row.updated_at).isoformat(),
            row.registry_digest,
        )


def _land(adaptation_id: str, ctx: dict) -> str:
    """Call `land.py` on the stored draft. Returns the branch it landed on.

    **Everything `land` needs to refuse with is passed in.** The vocabulary makes it prove the
    contract loads before git is touched, and `expect_base` makes it refuse a registry that
    moved since validation — `MF0301` asks that question when somebody presses approve, and
    this asks it again at the moment anything is written, because the gap between the two is a
    worker queue.
    """
    from mendel_forge import land as land_module
    from mendel_forge.workspace import Workspace

    from mendel_api.services import registry as registry_service

    draft = Workspace(root=settings.workspace_root).read_draft(adaptation_id)
    approved_by, approved_at, base = _approval(adaptation_id)
    result = land_module.land(
        draft,
        registry=settings.registry_root,
        branch=f"forge/{draft.scaffold.target}",
        approved_by=approved_by,
        approved_at=approved_at,
        vocabulary=registry_service.stack().vocabulary,
        roles=registry_service.stack().roles,
        expect_base=base or None,
    )
    return f"landed on {getattr(result, 'branch', 'a branch')}"


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

    # **`queued` has to mean something is queued, and it did not.** The scaffold job moved the
    # row here and stopped, so an adaptation sat in `queued` until somebody called `retry` — and
    # `retry` reads `failed_stage`, so on a row that had not failed it was the wrong verb for
    # the only thing that worked. Nothing drove the loop; found by driving it.
    #
    # **Only when a model is configured**, which is the no-AI lane staying honest rather than a
    # guard. With nothing to reach a provider with, every generation would fail on `MI0106` the
    # instant its scaffold landed, and an adaptation that reads `failed` because the
    # installation has no model is worse than one that reads `queued` and is waiting — for a
    # model, or for a curator filling holes by hand.
    if model_access() is not None:
        await enqueue_generation(adaptation_id, revision=str(moved.row_version))
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
    from mendel_forge.workspace import Draft, Workspace
    from mendel_resolver import layers

    async def fetch():
        async with httpx.AsyncClient(timeout=60.0) as client:
            return await _open(item.source, client).bundle(item)

    source = _asyncio.run(fetch())
    stack = layers.load(settings.registry_root)
    # **`derive_all`, not `derive`** — it exists for precisely this caller and the job was not
    # using it. `derive` returns only the immutable bundle; the working `Scaffold` and any
    # authored module are what everything downstream needs, and recomputing them later would be
    # a second derivation that has to agree with the recorded one.
    built, derived, module = bundle.derive_all(
        source,
        stack,
        adaptation_id=adaptation_id,
        registry_digest=digest_of_directory(settings.registry_root),
    )
    # **`source=` is not optional in practice**, and shipping without it was a defect that no
    # test could see: `_derive_and_write` is monkeypatched in every test that touches it, so
    # nothing had ever run this line against a real fetch. `write_bundle` stores the source
    # bundle only when it is handed one, and `read_source` is what lets the AI worker build a
    # dossier without going back to the network — which is the whole reason the two queues are
    # split. Without it, every generation fails one layer away from here, reading *no stored
    # source for adaptation …*.
    Workspace(root=settings.workspace_root).write_bundle(
        built,
        source=source,
        draft=Draft(name=adaptation_id, scaffold=derived, module=module),
    )


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

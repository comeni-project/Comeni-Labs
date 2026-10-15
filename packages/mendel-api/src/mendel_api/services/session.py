"""Where an authoring session rests, and the one place it moves (14.7.8.1).

**The diagram is the program.** A session sits on a node of `mendel_authoring.protocol.PROTOCOL`
(`at`); a command is an arrow out of it; entering an acting node runs its handler
(`mendel_api.stages`), whose outcome names the arrow on. Nothing else in the shell writes `at`
or the phase: the phase is read off the node the session reaches.
"""

import logging
from collections.abc import Callable
from contextlib import asynccontextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from typing import Any

from comeni_core.diagnostics import coded
from comeni_core.plan.draft import DraftProvenance
from mendel_authoring import interpret
from mendel_authoring import payloads as p
from mendel_authoring import state as st
from mendel_authoring.forks import Snapshot
from mendel_authoring.protocol import PROTOCOL, Protocol
from sqlalchemy import func, select, update

from mendel_api import db as db_mod
from mendel_api import jobs
from mendel_api.authoring.types import FactSource, Phase, ProposalState, TurnRole, TurnState
from mendel_api.db import session_scope
from mendel_api.models import (
    AiInvocation,
    PipelineAuthoringProposal,
    PipelineAuthoringSession,
    PipelineAuthoringTurn,
    PipelineDraft,
)

log = logging.getLogger(__name__)

_BY_PHASE = {
    Phase.UNDERSTANDING: "say",
    Phase.GATHERING: "list_needs",
    Phase.GOAL_REVIEW: "card",
    Phase.RESOLVING: "resolve",
    Phase.BUILDING: "step_card",
    Phase.COMPLETE: "wrap",
    Phase.FAILED: "failed",
    Phase.STOPPED: "stopped",
}
"""The node a row from before `at` rests on, when nothing pending says more (ruling 4)."""


def changed_version(db, session_id, current):
    """One workflow version per action, shared by recording and movement."""
    stamps = db.info.setdefault("authoring_mutation_stamps", {})
    key = (session_id, db.get_transaction())
    if stamps.get(key) != current:
        current += 1
        stamps[key] = current
    return current


def rests_at(db, row: PipelineAuthoringSession) -> str:
    """The node `row` rests on: stored, or derived from its phase and what is pending."""
    if row.at is not None:
        return row.at
    phase = Phase(row.phase)
    if phase is Phase.CORRECTING:
        raise ValueError(coded("MI0217", "an incomplete correction cannot be resumed"))
    if phase is Phase.UNDERSTANDING:
        turn = db.scalar(
            select(PipelineAuthoringTurn.seq).where(
                PipelineAuthoringTurn.session_id == row.id,
                PipelineAuthoringTurn.role == TurnRole.ASSISTANT,
                PipelineAuthoringTurn.state == TurnState.PENDING.value,
            )
        )
        return "family" if turn is not None else "say"
    pending = db.scalar(
        select(PipelineAuthoringProposal).where(
            PipelineAuthoringProposal.session_id == row.id,
            PipelineAuthoringProposal.state == ProposalState.PENDING.value,
        )
    )
    if phase is Phase.GATHERING and pending is not None and pending.kind == "gap":
        return "reply"
    return _BY_PHASE[phase]


@dataclass(frozen=True)
class Job:
    """One job an action wants queued once it commits. `unqueued`: a command performed when the
    queue refused it or failed, so nothing waits on a job that will never run (issue 241)."""

    name: str
    args: tuple
    job_id: str
    queue: str
    expires: float | None = None
    unqueued: object | None = None


@dataclass
class Ctx:
    """What a recorder and every handler on its way are handed: the session (`None` until a
    recorder addressed by a proposal finds it), the arrow being taken (`None` when resumed), its
    payload, an exception to raise once the action committed (`raised`), and the jobs to queue
    then."""

    session_id: str | None
    command: str | None
    payload: p.Payload = field(default_factory=p.Empty)
    turn_seq: int | None = None
    resolver_client: Any = None
    raised: BaseException | None = None
    jobs: list[Job] = field(default_factory=list)

    def queue(self, job: Job) -> None:
        if all(j.job_id != job.job_id for j in self.jobs):
            self.jobs.append(job)


Handler = Callable[[Ctx], str | None]
HANDLERS: dict[str, Handler] = {}
"""Each acting node's handler, by node id. `test_authoring_binding.py` holds this to the
protocol's acting nodes, both ways."""


def handles(node_id: str) -> Callable[[Handler], Handler]:
    def register(handler: Handler) -> Handler:
        if node_id in HANDLERS:
            raise ValueError(f"{node_id} already has a handler: {HANDLERS[node_id].__name__}")
        HANDLERS[node_id] = handler
        return handler

    return register


def _bound() -> dict[str, Handler]:
    import mendel_api.stages  # noqa: F401 — importing the stage modules registers them

    return HANDLERS


def _where(session_id: str) -> tuple[str, str | None, Phase, Phase | None]:
    with session_scope() as db:
        row = db.get(PipelineAuthoringSession, session_id)
        if row is None:
            raise KeyError(session_id)
        came_from = Phase(row.failed_from) if row.failed_from else None
        return rests_at(db, row), row.at, Phase(row.phase), came_from


def pin(session_id: str) -> str:
    """Write the derived node of a row from before `at`, and return where the session rests.

    **Called before a step records anything** (final review of 1b): a row's derived node reads
    what is pending, and the step about to run settles exactly that, so deriving it afterwards
    would find the session somewhere it never was. Compare-and-swap on `at IS NULL`; the version
    is not moved, since nothing about the session changed."""
    with session_scope() as db:
        row = db.get(PipelineAuthoringSession, session_id)
        if row is None:
            raise KeyError(session_id)
        if row.at is not None:
            return row.at
        derived = rests_at(db, row)
        db.execute(
            update(PipelineAuthoringSession)
            .where(PipelineAuthoringSession.id == session_id, PipelineAuthoringSession.at.is_(None))
            .values(at=derived)
        )
        return derived


def allows(session_id: str, command: str, *, protocol: Protocol = PROTOCOL) -> bool:
    try:
        check(session_id, command, protocol=protocol)
    except interpret.Refused:
        return False
    return True


def check(session_id: str, command: str, *, protocol: Protocol = PROTOCOL) -> None:
    """Refuse (MI0216) a command that names no arrow from where the session rests. Pins a
    derived node first, since the step that checks is about to record."""
    pin(session_id)
    at, _, _, came_from = _where(session_id)
    interpret.follow(protocol, at, command, returning_to=came_from)


def perform_now(
    session_id: str,
    command: str,
    *,
    protocol: Protocol = PROTOCOL,
    handlers: dict[str, Handler] | None = None,
    ctx: Ctx | None = None,
    payload: p.Payload = p.EMPTY,
) -> interpret.Ran:
    """Take `command`'s arrow from where the session rests, run every handler on the way, and
    write where it comes to rest."""
    return _dispatch(session_id, command, p.check(command, payload), protocol, handlers, ctx=ctx)


def resume(
    session_id: str,
    *,
    protocol: Protocol = PROTOCOL,
    handlers: dict[str, Handler] | None = None,
    ctx: Ctx | None = None,
    payload: p.Payload = p.EMPTY,
) -> interpret.Ran:
    """Enter the node the session rests on, as if it had just arrived."""
    return _dispatch(session_id, None, p.check(None, payload), protocol, handlers, ctx=ctx)


def snapshot(protocol: Protocol = PROTOCOL) -> Snapshot:
    """The settings the protocol's forks read, **resolved** — a `.env` lock, a designed option and
    a stale stored value all handled by the settings resolver — never the raw stored rows (spec
    §13.3; the final review of 14.7.8.3a)."""
    from comeni_core.settings import CATALOGUE

    from mendel_api.services.installation import installation

    keys = protocol.fork_keys()
    if not keys:
        return interpret.NO_SNAPSHOT
    found = installation()
    return Snapshot(settings={key: found.get(CATALOGUE.setting(key)) for key in sorted(keys)})


def _dispatch(session_id, command, payload, protocol, handlers, *, ctx=None) -> interpret.Ran:
    """Given a `ctx` (`take`), its `raised` is left for `perform` to raise after the commit;
    without one, raised here, as in 1b."""
    bound = _bound() if handlers is None else handlers
    start, stored, phase, came_from = _where(session_id)
    own = ctx is None
    if own:
        ctx = Ctx(session_id, command, payload)
    else:
        ctx.command, ctx.payload = command, payload
    ran = interpret.run(
        protocol,
        start,
        command,
        lambda node: bound[node](ctx),
        returning_to=came_from,
        snapshot=snapshot(protocol),
    )
    if ctx.session_id != session_id:
        if command != "fork_correction":
            raise RuntimeError("only the drawn correction fork can start another session")
        session_id = ctx.session_id
        start, stored, phase, came_from = _where(session_id)
        if start != "fork_correction":
            raise RuntimeError("a correction fork must enter at its drawn fork node")
    held = (
        PipelineAuthoringSession.at.is_(None)
        if stored is None
        else PipelineAuthoringSession.at == stored
    )
    write = None
    if ran.at != start:
        # **Written last, compare-and-swap on the node read** (ruling 3 of 14.7.8.1b): a session
        # another request moved meanwhile is refused rather than overwritten, and the whole action
        # with it (plan 1c).
        node = next(n for n in protocol.nodes if n.id == ran.at)
        failed = st.failed_from(phase).value if node.phase is Phase.FAILED else None
        write = (
            update(PipelineAuthoringSession)
            .where(PipelineAuthoringSession.id == session_id, held)
            .values(
                at=ran.at,
                phase=node.phase.value,
                failed_from=failed,
                updated_at=datetime.now(UTC),
            )
        )
    elif stored is not None:
        # **Resting where it started still holds the node** (Review Focus 3 of plan 1c): an
        # answer that offers the next question comes back to `reply`, and what it recorded on
        # the way stands only if no other request moved the session meanwhile. Nothing moved, so
        # nothing is bumped; the write is the check, and holds the row to the commit.
        write = (
            update(PipelineAuthoringSession)
            .where(PipelineAuthoringSession.id == session_id, held)
            .values(at=stored)
        )
    if write is not None:
        with session_scope() as db:
            if ran.at != start:
                row = db.get(PipelineAuthoringSession, session_id)
                write = write.values(row_version=changed_version(db, session_id, row.row_version))
            if db.execute(write).rowcount != 1:
                raise ValueError(
                    coded("MI0201", "this session moved while you were looking at it")
                    + f"\n  it was at {start} when {command or 'resuming'} arrived"
                    + "\n  re-read it before acting on it"
                )
    if own and ctx.raised is not None:
        raise ctx.raised
    return ran


@dataclass(frozen=True)
class Performed:
    result: object
    jobs: tuple[Job, ...] = ()
    queued: tuple[bool, ...] = ()


Recorder = Callable[[Ctx, Any], object]
RECORDERS: dict[type, Recorder] = {}
"""Each command's recorder, by its type. `test_authoring_binding.py` holds this to
`mendel_authoring.commands.COMMANDS`, both ways."""


def records(kind: type) -> Callable[[Recorder], Recorder]:
    def register(recorder: Recorder) -> Recorder:
        if kind in RECORDERS:
            raise ValueError(
                f"{kind.__name__} already has a recorder: {RECORDERS[kind].__name__}"
            )
        RECORDERS[kind] = recorder
        return recorder

    return register


def _recorded() -> dict[type, Recorder]:
    import mendel_api.stages  # noqa: F401 — importing the stage modules registers them

    return RECORDERS


def perform(command: object, *, recorders: dict[type, Recorder] | None = None) -> Performed:
    """**One command, one transaction** (spec §11.2). The recorder records what arrived and takes
    its arrows (`take`); an exception rolls all of it back; `ctx.raised` is raised only once the
    action committed. The jobs come back unqueued: `act` queues them."""
    if db_mod.in_transaction():
        raise RuntimeError("a command never performs another: take its arrow (`take`)")
    bound = _recorded() if recorders is None else recorders
    ctx = Ctx(getattr(command, "session_id", None), None)
    with db_mod.transaction() as db:
        from mendel_api.services import draft_mutations

        session_id = ctx.session_id
        proposal_id = getattr(command, "proposal_id", None)
        if session_id is None and proposal_id is not None:
            session_id = db.scalar(select(PipelineAuthoringProposal.session_id).where(
                PipelineAuthoringProposal.id == proposal_id))
        if session_id is not None:
            row = draft_mutations.lock_session(db, session_id)
            if row.retired:
                raise ValueError(coded("MI0217", "this archived session is read-only"))
        result = bound[type(command)](ctx, command)
    if (collecting := _collected.get()) is not None and not _acting.get():
        collecting.extend(ctx.jobs)
    if ctx.raised is not None:
        raise ctx.raised
    return Performed(result, tuple(ctx.jobs))


_collected: ContextVar[list[Job] | None] = ContextVar("authoring_collected", default=None)
"""The jobs a background job's commands asked for, queued when its work ends (`queued_after`)."""
_acting: ContextVar[bool] = ContextVar("authoring_acting", default=False)


async def act(command: object, *, recorders: dict[type, Recorder] | None = None) -> Performed:
    """`perform` off the event loop, then its jobs queued: **after the commit**, so a job never
    reads what is not saved, nor runs for an action that rolled back."""
    from starlette.concurrency import run_in_threadpool

    def performed() -> Performed:
        token = _acting.set(True)
        try:
            return perform(command, recorders=recorders)
        finally:
            _acting.reset(token)

    done = await run_in_threadpool(performed)
    return replace(done, queued=await _queue(done.jobs, recorders))


@asynccontextmanager
async def queued_after(*, recorders: dict[type, Recorder] | None = None):
    """**A background job's commands, queued once its work is done** (plan 1c). A job performs
    each command as it goes, in its own transaction; what they asked for (a question's phrasing,
    a card's read-back) is queued here, after every one of them committed, even if the job's work
    then raised."""
    token = _collected.set([])
    failed = False
    try:
        yield
    except BaseException:
        failed = True
        raise
    finally:
        wanted = _collected.get() or []
        _collected.reset(token)
        try:
            await _queue(tuple(wanted), recorders)
        except Exception:
            if not failed:
                raise
            # **The job's own error is the one raised** (issue 251): an ending that broke while
            # the job was already failing is logged, never put in its place.
            log.exception("queueing after a failed job")


async def _queue(wanted: tuple[Job, ...], recorders) -> tuple[bool, ...]:
    """Each job through the queue; one it refused, or could not take, runs its ending."""
    from starlette.concurrency import run_in_threadpool

    queued = []
    for job in wanted:
        ok = await _enqueue(job)
        if not ok and job.unqueued is not None:
            await run_in_threadpool(lambda j=job: perform(j.unqueued, recorders=recorders))
        queued.append(ok)
    return tuple(queued)


async def _enqueue(job: Job) -> bool:
    """The queue's seam. `False` when the queue refused the id or could not be reached."""
    try:
        return await jobs.enqueue(
            job.name, *job.args, job_id=job.job_id, queue=job.queue, expires=job.expires
        )
    except Exception:
        log.exception("queueing %s failed", job.job_id)
        return False


def take(
    ctx: Ctx, arrow: str, payload: p.Payload = p.EMPTY, *, protocol: Protocol = PROTOCOL
) -> interpret.Ran:
    """Take an arrow with its frozen typed value in the recorder's transaction."""
    return _dispatch(ctx.session_id, arrow, p.check(arrow, payload), protocol, None, ctx=ctx)


# ── the read model: what a browser and a job read (plan 1c) ──────────────────────────────


def read(session_id: str) -> dict:
    """Everything a browser needs to draw the session, in one read.

    **The checkpoint's shape.** Task 3 asks that restarting the API between writing and reading
    changes nothing, and that is only checkable if one call returns the whole picture: phase,
    transcript, the pending proposal, the confirmed goal, and the draft's revision. Assembling it
    from four endpoints would make the checkpoint a statement about four caches.
    """
    # Not moved yet (plan 1c, Tasks 5, 7, 8): imported here, which keeps it from being circular.
    from comeni_core.plan.draft import DraftGraph
    from mendel_authoring.blueprint import Blueprint
    from mendel_authoring.progress import progress_of

    from mendel_api.authoring import envelopes
    from mendel_api.services import authoring_canvas, authoring_decisions, decisions, registry
    from mendel_api.services import suggestions as _suggestions
    from mendel_api.stages.building import _placement, hand_edits
    from mendel_api.stages.gathering import _answer_of
    from mendel_api.stages.samples import _aged

    with session_scope() as db:
        row = db.get(PipelineAuthoringSession, session_id)
        if row is None:
            raise KeyError(session_id)
        draft = db.get(PipelineDraft, row.draft_id)
        current_facts = [f.model_dump(mode="json") for f in authoring_decisions.facts(row.draft_id)]
        current_goal = (authoring_decisions.goal(row).model_dump(mode="json")
                        if authoring_decisions.confirmed(row.draft_id) else None)

        turns = db.scalars(
            select(PipelineAuthoringTurn)
            .where(PipelineAuthoringTurn.session_id == session_id)
            .order_by(PipelineAuthoringTurn.seq)
        ).all()
        pending = db.scalar(
            select(PipelineAuthoringProposal).where(
                PipelineAuthoringProposal.session_id == session_id,
                PipelineAuthoringProposal.state == ProposalState.PENDING.value,
            )
        )
        spent = db.execute(
            select(
                func.coalesce(func.sum(AiInvocation.input_tokens), 0),
                func.coalesce(func.sum(AiInvocation.output_tokens), 0),
                func.coalesce(func.sum(AiInvocation.cached_tokens), 0),
                func.count(AiInvocation.id),
            ).where(AiInvocation.session_id == session_id)
        ).one()
        historical_answers = decisions.answers_in(db, row.draft_id)
        selected = decisions.read(row.draft_id)
        review_rows = db.scalars(select(decisions.PipelineReviewRevision).where(
            decisions.PipelineReviewRevision.draft_id == row.draft_id
        ).order_by(decisions.PipelineReviewRevision.seq)).all()
        review_status = {r.proposal_id: ("retained" if r.status == "reviewed" else r.status)
                         for r in review_rows if r.proposal_id}
        node_status = {r.node: ("retained" if r.status == "reviewed" else r.status)
                       for r in review_rows}
        original_session = (db.scalar(select(PipelineAuthoringSession.id).where(
            PipelineAuthoringSession.draft_id == draft.forked_from)) if draft.forked_from else None)
        evidence_subjects = db.scalars(select(decisions.PipelineObservation.subject).join(
            decisions.PipelineEvidenceAccess,
            decisions.PipelineEvidenceAccess.observation_id == decisions.PipelineObservation.id
        ).where(decisions.PipelineEvidenceAccess.draft_id == row.draft_id).distinct()).all()
        placement = _placement(row, draft, pending)
        blueprint = Blueprint.model_validate(row.blueprint) if row.blueprint else None
        step = pending if pending is not None and pending.kind == "step" else None
        offered = step.payload["node"] if step is not None else None
        # **A drawing never makes the session unreadable.** The frame and progress are read off the
        # registry as it stands; one that moved under a recorded contract or port (or a pending
        # step outside the plan) leaves them absent, and history, polling and forks still work.
        try:
            # Each node's latest review, reduced in sequence order from the rows already loaded.
            progress = (None if blueprint is None or draft.ownership == "manual" else progress_of(
                list(blueprint.order),
                frozenset(n for n, status in node_status.items() if status == "retained"),
                frozenset(node_status), offered))
        except ValueError:
            progress = None
        try:
            canvas = authoring_canvas.frame_of(
                blueprint=blueprint,
                graph=DraftGraph.model_validate(draft.graph or {}),
                provenance=DraftProvenance.model_validate(draft.provenance or {}),
                pending=envelopes.parse(step.payload, kind=step.kind) if step is not None else None,
                proposal_id=step.id if step is not None else None,
                context=envelopes.OfferContext(draft_revision=draft.revision,
                    decision_revision=draft.decision_revision, session_version=row.row_version,
                    registry=row.registry_digest or ""),
                current=draft.projection_current, ownership=draft.ownership,
                placement=placement, layers=registry.stack(),
            )
        except (KeyError, ValueError):
            canvas = None
        details = bool(row.show_gaps)
        return {
            "canvas": canvas.model_dump(mode="json") if canvas is not None else None,
            "progress": progress.model_dump(mode="json") if progress is not None else None,
            "show_gap_details": details,
            "fact_subjects": sorted(set(evidence_subjects) | {f.subject for f in selected.facts}),
            "decision_revision": draft.decision_revision,
            "projection_current": draft.projection_current,
            "ownership": draft.ownership,
            "retired": row.retired,
            "forked_from": draft.forked_from,
            "forked_from_session": original_session,
            "inputs": [i.model_dump(mode="json") for i in selected.inputs],
            "review_applicability": node_status,
            # **The token total rides the read every poll already makes** (#191; the operator's
            # constraint for 14.7.4: nothing chatty). A provider that reported no usage counts
            # as zero here and stays null on its row.
            "usage": {
                "input": int(spent[0]),
                "output": int(spent[1]),
                "cached": int(spent[2]),
                "calls": int(spent[3]),
                "in_flight": any(t.state == TurnState.PENDING.value for t in turns)
                or _words_coming(pending),
            },
            "id": row.id,
            "draft_id": row.draft_id,
            "phase": row.phase,
            "failed_from": row.failed_from,
            "goal": current_goal,
            "facts": current_facts,
            "row_version": row.row_version,
            "revision": draft.revision if draft else 0,
            "graph": draft.graph if draft else {},
            "placement": placement,
            "hand_edits": hand_edits(row, draft),
            # **A count, not the plan.** How many steps the blueprint holds lets the header say
            # `4 of 7`; which steps they are stays private until each is offered.
            "steps_total": len((row.blueprint or {}).get("order") or []),
            "turns": [
                {
                    "seq": t.seq,
                    "role": t.role,
                    "state": t.state,
                    "text": t.text,
                    "blocks": t.blocks,
                    "base_revision": t.base_revision,
                    "at": t.at.isoformat(),
                }
                for t in turns
            ],
            "name": draft.name if draft else "",
            "history": [
                {
                    "id": p.id,
                    "envelope": _gaps_shown(envelopes.historical(p.payload, kind=p.kind)
                                            .model_dump(mode="json"), details),
                    "kind": p.kind,
                    "state": p.state,
                    "block": _gaps_shown(p.payload.get("block"), details),
                    "by": p.by,
                    "actor_kind": p.actor_kind or "unknown",
                    "applicability": review_status.get(p.id),
                    "chosen_option": p.chosen_option,
                    "chosen_contract": (p.payload.get("options") or {}).get(p.chosen_option or ""),
                    "answer": _answer_of(p, historical_answers.get(p.id, [])),
                    "at": (p.settled_at or p.created_at).isoformat(),
                }
                for p in db.scalars(
                    select(PipelineAuthoringProposal)
                    .where(
                        PipelineAuthoringProposal.session_id == session_id,
                        PipelineAuthoringProposal.state != ProposalState.PENDING.value,
                    )
                    .order_by(PipelineAuthoringProposal.created_at)
                ).all()
            ],
            "suggestions": [
                {"id": view.id, "says": view.says, "heard": view.heard,
                 "quote": view.change.heard, "kind": view.change.kind,
                 "subject": view.change.subject}
                for view in _suggestions.pending(session_id)
            ],
            "pending_proposal": (
                None
                if pending is None
                else {
                    "id": pending.id,
                    "kind": pending.kind,
                    "payload": _gaps_shown(_aged(envelopes.parse(pending.payload, kind=pending.kind)
                                                 .model_dump(mode="json")), details),
                    "draft_revision": pending.draft_revision,
                }
            ),
        }


def _gaps_shown(value, details: bool):
    """Registry gaps with their kinds and repository paths go out only under Dev mode (Part G spec
    §8, for API consumers as well as the screen): otherwise every `gaps` list is emptied, and a
    step's `unresolved_settings` still names, in plain words, what stays unset."""
    if details:
        return value
    if isinstance(value, dict):
        return {k: ([] if k == "gaps" and isinstance(v, list) else _gaps_shown(v, details))
                for k, v in value.items()}
    if isinstance(value, list):
        return [_gaps_shown(v, details) for v in value]
    return value


def _words_coming(pending) -> bool:
    """Whether the proposal on offer is still waiting for a model's words: a question being
    phrased (#167) or a card's read-back (#176). Read from the row already loaded."""
    from mendel_api.stages.samples import _reading

    if pending is None:
        return False
    block = pending.payload.get("block") or {}
    reading = _reading(block) or {}
    return (
        block.get("phrasing") == "pending"
        or bool(block.get("readback_pending"))
        or reading.get("state") == "pending"
    )


def calls(session_id: str) -> list[dict]:
    """The session's model calls, oldest first, with each reply (#182, #191).

    Fetched only when the page opens its call panel, never on the poll.
    """
    with session_scope() as db:
        if db.get(PipelineAuthoringSession, session_id) is None:
            raise KeyError(session_id)
        rows = db.scalars(
            select(AiInvocation)
            .where(AiInvocation.session_id == session_id)
            .order_by(AiInvocation.started_at)
        ).all()
        return [
            {
                "id": r.id,
                "purpose": r.purpose,
                "model": r.model,
                "input": r.input_tokens,
                "output": r.output_tokens,
                "cached": r.cached_tokens,
                "duration_ms": r.duration_ms,
                "state": r.state,
                "response": r.response,
                "cleared": r.response_cleared,
                "reply_format": r.reply_format,
                "at": r.started_at.isoformat(),
            }
            for r in rows
        ]


def current_phase(session_id: str) -> Phase:
    with session_scope() as db:
        row = db.get(PipelineAuthoringSession, session_id)
        if row is None:
            raise KeyError(session_id)
        return Phase(row.phase)


def pending_id(session_id: str) -> str | None:
    with session_scope() as db:
        return db.scalar(
            select(PipelineAuthoringProposal.id).where(
                PipelineAuthoringProposal.session_id == session_id,
                PipelineAuthoringProposal.state == ProposalState.PENDING.value,
            )
        )


def ai_for(provenance: DraftProvenance, *, characterised: bool = False):
    """What AI points this installation offers, and which this draft used. For `pipeline.yml`.

    **One function for the preview and for Keep**, so the two cannot disagree about the `ai`
    block — which would make the preview and the kept file differ for a reason nobody edited.
    `available` follows the installation, never the mode (Task 12); `used` is read from the
    sidecar, because it answers which points this draft actually exercised.
    """
    from comeni_core.artifact.pipeline import AiPoint, AiProvenance
    from comeni_core.plan.tiers import ValueSource

    from mendel_api.settings import model_access

    if model_access() is None:
        return AiProvenance(available=[], used=[])
    modelled = any(
        entry.selection is not None and entry.selection.source is ValueSource.MODEL
        for entry in provenance.nodes
    ) or any(entry.settled.source is ValueSource.MODEL for entry in provenance.params)
    # The characteriser (14.7.7): available where a model may read a sample here; used when a
    # fact the session gathered was read by it (`characterised`, from the session's facts).
    from mendel_api.stages.gathering import _characterisable

    reads = _characterisable()
    return AiProvenance(
        available=[AiPoint.PROMPT, AiPoint.TIER_4] + ([AiPoint.CHARACTERISE] if reads else []),
        used=[AiPoint.PROMPT]
        + ([AiPoint.TIER_4] if modelled else [])
        + ([AiPoint.CHARACTERISE] if reads and characterised else []),
    )


def characterised(facts: list[dict] | None) -> bool:
    """Whether any fact a session gathered was read by the AI (14.7.7)."""
    return any(f.get("source") == FactSource.MODEL_READ.value for f in facts or [])


def ai_for_draft(draft_id: str):
    """`ai_for` for a draft an authoring session owns, or `None` for a hand-drawn one."""
    from mendel_api.services import authoring_decisions

    with session_scope() as db:
        owned = db.scalar(
            select(PipelineAuthoringSession).where(
                PipelineAuthoringSession.draft_id == draft_id
            )
        )
        if owned is None:
            return None
        draft = db.get(PipelineDraft, draft_id)
        return ai_for(
            DraftProvenance.model_validate(draft.provenance or {}),
            characterised=characterised([f.model_dump(mode="json") for f in
                authoring_decisions.facts(draft_id)]),
        )


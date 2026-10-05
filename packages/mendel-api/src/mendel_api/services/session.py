"""Where an authoring session rests, and the one place it moves (14.7.8.1).

**The diagram is the program.** A session sits on a node of `mendel_authoring.protocol.PROTOCOL`
(`at`); a command is an arrow out of it; entering an acting node runs its handler
(`mendel_api.stages`), whose outcome names the arrow on. Nothing else in the shell writes `at`
or the phase: the phase is read off the node the session reaches.
"""

import logging
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from typing import Any

from comeni_core.diagnostics import coded
from mendel_authoring import interpret
from mendel_authoring import state as st
from mendel_authoring.protocol import PROTOCOL, Protocol
from sqlalchemy import func, select, update

from mendel_api import db as db_mod
from mendel_api import jobs
from mendel_api.authoring.types import Mode, Phase, ProposalState, TurnState
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
    Phase.BUILDING: "offer",
    Phase.COMPLETE: "done",
    Phase.FAILED: "failed",
    Phase.STOPPED: "stopped",
}
"""The node a row from before `at` rests on, when nothing pending says more (ruling 4)."""

_BY_TIER = {1: "step_settled", 2: "step_settled", 3: "step_rule", 4: "step_choice"}


def rests_at(db, row: PipelineAuthoringSession) -> str:
    """The node `row` rests on: stored, or derived from its phase and what is pending."""
    if row.at is not None:
        return row.at
    phase = Phase(row.phase)
    if phase is Phase.UNDERSTANDING:
        turn = db.scalar(
            select(PipelineAuthoringTurn.seq).where(
                PipelineAuthoringTurn.session_id == row.id,
                PipelineAuthoringTurn.role == "assistant",
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
    if phase is Phase.BUILDING and pending is not None and pending.kind == "step":
        return _BY_TIER[int(pending.payload["block"]["tier"])]
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
    payload: dict = field(default_factory=dict)
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
    **payload: object,
) -> interpret.Ran:
    """Take `command`'s arrow from where the session rests, run every handler on the way, and
    write where it comes to rest."""
    return _dispatch(session_id, command, payload, protocol, handlers, ctx=ctx)


def resume(
    session_id: str,
    *,
    protocol: Protocol = PROTOCOL,
    handlers: dict[str, Handler] | None = None,
    ctx: Ctx | None = None,
    **payload: object,
) -> interpret.Ran:
    """Enter the node the session rests on, as if it had just arrived."""
    return _dispatch(session_id, None, payload, protocol, handlers, ctx=ctx)


def _dispatch(session_id, command, payload, protocol, handlers, *, ctx=None) -> interpret.Ran:
    """Given a `ctx` (`take`), its `raised` is left for `perform` to raise after the commit;
    without one, raised here, as in 1b."""
    bound = _bound() if handlers is None else handlers
    start, stored, phase, came_from = _where(session_id)
    own = ctx is None
    if own:
        ctx = Ctx(session_id, command, dict(payload))
    ran = interpret.run(
        protocol, start, command, lambda node: bound[node](ctx), returning_to=came_from
    )
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
                row_version=PipelineAuthoringSession.row_version + 1,
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
    with db_mod.transaction():
        result = bound[type(command)](ctx, command)
    if ctx.raised is not None:
        raise ctx.raised
    return Performed(result, tuple(ctx.jobs))


async def act(command: object, *, recorders: dict[type, Recorder] | None = None) -> Performed:
    """`perform` off the event loop, then its jobs queued: **after the commit**, so a job never
    reads what is not saved, nor runs for an action that rolled back."""
    from starlette.concurrency import run_in_threadpool

    done = await run_in_threadpool(lambda: perform(command, recorders=recorders))
    queued = []
    for job in done.jobs:
        ok = await _enqueue(job)
        if not ok and job.unqueued is not None:
            await run_in_threadpool(lambda j=job: perform(j.unqueued, recorders=recorders))
        queued.append(ok)
    return replace(done, queued=tuple(queued))


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
    ctx: Ctx, arrow: str, *, protocol: Protocol = PROTOCOL, **payload: object
) -> interpret.Ran:
    """Inside a recorder: take `arrow` from where `ctx.session_id` rests, every handler on the way
    sharing `ctx`."""
    ctx.command, ctx.payload = arrow, dict(payload)
    return _dispatch(ctx.session_id, arrow, payload, protocol, None, ctx=ctx)


# ── the read model: what a browser and a job read (plan 1c) ──────────────────────────────


def read(session_id: str) -> dict:
    """Everything a browser needs to draw the session, in one read.

    **The checkpoint's shape.** Task 3 asks that restarting the API between writing and reading
    changes nothing, and that is only checkable if one call returns the whole picture: phase,
    transcript, the pending proposal, the confirmed goal, and the draft's revision. Assembling it
    from four endpoints would make the checkpoint a statement about four caches.
    """
    # Not moved yet (plan 1c, Tasks 5, 7, 8): imported here, which keeps it from being circular.
    from mendel_api.services.authoring import _aged, _placement
    from mendel_api.stages.gathering import _answer_of

    with session_scope() as db:
        row = db.get(PipelineAuthoringSession, session_id)
        if row is None:
            raise KeyError(session_id)
        draft = db.get(PipelineDraft, row.draft_id)

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
        return {
            # **The token total rides the read every poll already makes** (#191; the operator's
            # constraint for 14.7.4: nothing chatty). A provider that reported no usage counts
            # as zero here and stays null on its row.
            "usage": {
                "input": int(spent[0]),
                "output": int(spent[1]),
                "cached": int(spent[2]),
                "calls": int(spent[3]),
                "in_flight": any(t.state == TurnState.PENDING.value for t in turns)
                or (row.mode == Mode.SPAWN.value and row.phase == Phase.RESOLVING.value)
                or _words_coming(pending),
            },
            "id": row.id,
            "draft_id": row.draft_id,
            "mode": row.mode,
            "phase": row.phase,
            "failed_from": row.failed_from,
            "goal": row.goal,
            "facts": list(row.facts or []),
            "cursor": row.cursor,
            "row_version": row.row_version,
            "revision": draft.revision if draft else 0,
            "graph": draft.graph if draft else {},
            "placement": _placement(row, draft, pending),
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
                    "kind": p.kind,
                    "state": p.state,
                    "block": p.payload.get("block"),
                    "by": p.by,
                    "chosen_option": p.chosen_option,
                    "chosen_contract": (p.payload.get("options") or {}).get(p.chosen_option or ""),
                    "answer": _answer_of(p, row.facts or []),
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
            "pending_proposal": (
                None
                if pending is None
                else {
                    "id": pending.id,
                    "kind": pending.kind,
                    "payload": _aged(pending.payload),
                    "draft_revision": pending.draft_revision,
                }
            ),
        }


def _words_coming(pending) -> bool:
    """Whether the proposal on offer is still waiting for a model's words: a question being
    phrased (#167) or a card's read-back (#176). Read from the row already loaded."""
    from mendel_api.services.authoring import _reading

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


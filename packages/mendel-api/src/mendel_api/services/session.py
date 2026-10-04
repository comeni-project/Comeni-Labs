"""Where an authoring session rests, and the one place it moves (14.7.8.1).

**The diagram is the program.** A session sits on a node of `mendel_authoring.protocol.PROTOCOL`
(`at`); a command is an arrow out of it; entering an acting node runs its handler
(`mendel_api.stages`), whose outcome names the arrow on. Nothing else in the shell writes `at`
or the phase: the phase is read off the node the session reaches.
"""

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime

from comeni_core.diagnostics import coded
from mendel_authoring import interpret
from mendel_authoring import state as st
from mendel_authoring.protocol import PROTOCOL, Protocol
from sqlalchemy import select, update

from mendel_api.authoring.types import Phase, ProposalState, TurnState
from mendel_api.db import session_scope
from mendel_api.models import (
    PipelineAuthoringProposal,
    PipelineAuthoringSession,
    PipelineAuthoringTurn,
)

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


@dataclass
class Ctx:
    """What a handler is handed: the session, what arrived (`None` when resumed), its payload,
    and an exception to raise once the session has moved (`raised`, for `resolve`)."""

    session_id: str
    command: str | None
    payload: dict = field(default_factory=dict)
    raised: BaseException | None = None


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
    **payload: object,
) -> interpret.Ran:
    """Take `command`'s arrow from where the session rests, run every handler on the way, and
    write where it comes to rest."""
    return _dispatch(session_id, command, payload, protocol, handlers)


def resume(
    session_id: str,
    *,
    protocol: Protocol = PROTOCOL,
    handlers: dict[str, Handler] | None = None,
    **payload: object,
) -> interpret.Ran:
    """Enter the node the session rests on, as if it had just arrived."""
    return _dispatch(session_id, None, payload, protocol, handlers)


def _dispatch(session_id, command, payload, protocol, handlers) -> interpret.Ran:
    bound = _bound() if handlers is None else handlers
    start, stored, phase, came_from = _where(session_id)
    ctx = Ctx(session_id, command, dict(payload))
    ran = interpret.run(
        protocol, start, command, lambda node: bound[node](ctx), returning_to=came_from
    )
    if ran.at != start:
        # **Written last, compare-and-swap on the node read** (ruling 3 of 14.7.8.1b): each step
        # before this kept its own transaction, and a session another request moved meanwhile is
        # refused rather than overwritten.
        node = next(n for n in protocol.nodes if n.id == ran.at)
        failed = st.failed_from(phase).value if node.phase is Phase.FAILED else None
        held = (
            PipelineAuthoringSession.at.is_(None)
            if stored is None
            else PipelineAuthoringSession.at == stored
        )
        with session_scope() as db:
            done = db.execute(
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
            if done.rowcount != 1:
                raise ValueError(
                    coded("MI0201", "this session moved while you were looking at it")
                    + f"\n  it was at {start} when {command or 'resuming'} arrived"
                    + "\n  re-read it before acting on it"
                )
    if ctx.raised is not None:
        raise ctx.raised
    return ran

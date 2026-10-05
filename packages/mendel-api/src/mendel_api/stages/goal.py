"""③ The goal card: accept, *not quite*, a correction in words, and the read-back in the
model's words (14.7.8.1; plan 1c). Moved from `services/authoring.py`."""

from mendel_authoring import commands as c
from mendel_authoring import state as st
from mendel_authoring.types import Command
from mendel_resolver.goal import Goal
from sqlalchemy import select

from mendel_api.authoring.types import FactKind, FactSource, Phase, ProposalState
from mendel_api.db import session_scope
from mendel_api.models import PipelineAuthoringProposal
from mendel_api.services import authoring_ai, registry, session
from mendel_api.services.session import Ctx, handles, records
from mendel_api.stages import _jobs, _rows, gathering
from mendel_api.stages._rows import now as _now

READS = ("wants_readback", "readback_context")
"""What a job may read of this stage directly (ruling 2 of plan 1c); every change is a command."""

GOAL = _rows.GOAL
store_goal = _rows.store_goal


def withdraw_pending(session_id: str, *, by: str) -> None:
    """Reject whatever is pending — a goal summary the person has just corrected in prose."""
    with session_scope() as db:
        pending = db.scalar(
            select(PipelineAuthoringProposal).where(
                PipelineAuthoringProposal.session_id == session_id,
                PipelineAuthoringProposal.state == ProposalState.PENDING.value,
            )
        )
        if pending is not None:
            pending.state = ProposalState.REJECTED.value
            pending.by = by
            pending.settled_at = _now()


def readback_context(session_id: str) -> str:
    """The composed goal as the read-back call is given it: every input and fact with its
    source, the want, and the constraints kept so far — never the first sentence (#176)."""
    wanted, facts, _ = gathering._gathered(session_id)
    goal = gathering.compose_goal(session_id)
    said = {FactSource.PERSON_SAID: "you said", FactSource.MEASURED: "measured",
            FactSource.MODEL_READ: "read by AI", FactSource.OPEN: "left open"}
    lines = [
        "have: " + (", ".join(
            f"{f.subject} ({said[f.source]})" for f in facts if f.kind is FactKind.INPUT
        ) or "nothing"),
        "facts: " + ("; ".join(
            f"{f.subject} = {f.value if f.value is not None else 'unknown'} ({said[f.source]})"
            for f in facts if f.kind is FactKind.MEASUREMENT
        ) or "none"),
        "want: " + ", ".join(goal.want),
    ]
    kept = goal.constraints.required_states
    if kept:
        lines.append("required: " + "; ".join(
            f"{r.type_id} [{', '.join(r.states)}]" for r in kept
        ))
    return "\n".join(lines)


def _pending_card(db, session_id: str):
    pending = db.scalar(
        select(PipelineAuthoringProposal).where(
            PipelineAuthoringProposal.session_id == session_id,
            PipelineAuthoringProposal.state == ProposalState.PENDING.value,
        )
    )
    return pending if pending is not None and pending.kind == GOAL else None


def _set_card(session_id: str, **changes) -> None:
    with session_scope() as db:
        card = _pending_card(db, session_id)
        if card is None:
            return
        payload = dict(card.payload)
        payload["block"] = {**payload["block"], **changes}
        card.payload = payload


def store_readback(session_id: str, text: str) -> None:
    """The read-back on the card on offer; nothing if the card was already answered (#176)."""
    _set_card(session_id, readback=text, readback_pending=False)


def readback_failed(session_id: str) -> None:
    """A read-back that failed or was refused: the engine's sentence stands."""
    _set_card(session_id, readback_pending=False)


def wants_readback(session_id: str) -> bool:
    with session_scope() as db:
        card = _pending_card(db, session_id)
        return card is not None and bool(card.payload["block"].get("readback_pending"))


# ── the commands ─────────────────────────────────────────────────────────────────────────


@records(c.DecideGoal)
def _decide_goal(ctx: Ctx, cmd: c.DecideGoal) -> tuple[st.Settlement, Phase]:
    """Accept or reject the card (`decide_goal`): its own refusal first (a duplicate is MI0203,
    an old picture MI0201), then the diagram, then the decision, the goal and the move, **in one
    transaction**. Accepting stores the card's goal as the confirmed one."""
    decision = ProposalState(cmd.decision)
    with session_scope() as db:
        row = db.get(PipelineAuthoringProposal, cmd.proposal_id)
        if row is None:
            raise KeyError(cmd.proposal_id)
        ctx.session_id, goal = row.session_id, row.payload.get("goal")
    accepted = decision is ProposalState.ACCEPTED
    if cmd.edited is not None and accepted:
        # **A structured edit needs no model call** — §Task 10. It is held to the same vocabulary
        # a model's goal is, before anything is recorded, so an invented type id typed into the
        # card is refused exactly as one a model wrote would be.
        edited = Goal.model_validate(cmd.edited)
        authoring_ai.admit_goal(edited, registry.stack())
        goal = edited.model_dump(mode="json")
    arrow = Command.CONFIRM_GOAL if accepted else Command.REVISE_GOAL
    # **The proposal's own refusal first** (ruling 8; final review of 1b): a duplicate is MI0203
    # and an old picture of the draft MI0201, before the diagram is asked.
    if _rows.settlement(cmd.proposal_id, decision, cmd.expected_revision).refusal is None:
        session.check(ctx.session_id, arrow.value)
    outcome = _rows.decide(
        cmd.proposal_id, decision, expected_revision=cmd.expected_revision, by=cmd.by
    )
    if outcome.refusal is not None:
        return outcome, session.current_phase(ctx.session_id)
    if accepted:
        store_goal(ctx.session_id, goal)
    session.take(ctx, arrow.value)
    return outcome, session.current_phase(ctx.session_id)


@records(c.Revised)
def _revised(ctx: Ctx, cmd: c.Revised) -> None:
    """A correction in words on the card: the card is withdrawn and the model reads the new
    words. **Only where the diagram still draws it** (final review of 1b): checked first, so a
    card accepted meanwhile withdraws nothing."""
    session.check(cmd.session_id, Command.REVISED.value)
    withdraw_pending(cmd.session_id, by=cmd.by)
    session.take(ctx, Command.REVISED.value)


@records(c.StoreReadback)
def _store_readback(ctx: Ctx, cmd: c.StoreReadback) -> None:
    store_readback(cmd.session_id, cmd.text)


@records(c.ReadbackFailed)
def _readback_failed(ctx: Ctx, cmd: c.ReadbackFailed) -> None:
    readback_failed(cmd.session_id)


# ── the handler ──────────────────────────────────────────────────────────────────────────


@handles("readback")
def readback(ctx: Ctx) -> None:
    """The card on offer is read back in the model's words, once per card (#176). Passes
    straight through to `card`."""
    if wants_readback(ctx.session_id):
        ctx.queue(_jobs.readback(ctx.session_id, session.pending_id(ctx.session_id) or ""))
    return None

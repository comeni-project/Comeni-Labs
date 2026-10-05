"""① You describe it: what you said, the model's reading of it, and retry (14.7.8.1; plan 1c).

Moved from `services/authoring.py`. A recorder per command records what arrived and takes its
arrow; `family` queues the model's reading of what was said, `read_goal` stores the want.
"""

from typing import NamedTuple

from comeni_core.diagnostics import coded
from comeni_core.plan.draft import DraftGraph
from mendel_authoring import commands as c
from mendel_authoring.types import Command
from mendel_resolver.goal import Goal
from sqlalchemy import select, update

from mendel_api.authoring.types import Mode, Phase, ProposalState, TurnState
from mendel_api.db import session_scope
from mendel_api.models import (
    PipelineAuthoringProposal,
    PipelineAuthoringSession,
    PipelineAuthoringTurn,
    PipelineDraft,
)
from mendel_api.services import authoring, session
from mendel_api.services.session import Ctx, handles, records
from mendel_api.stages import _jobs
from mendel_api.stages._rows import GOAL, new_id, next_seq, store_goal
from mendel_api.stages._rows import now as _now

READS = ("turn_context",)
"""What a job may read of this stage directly (ruling 2 of plan 1c); every change is a command."""

UNTITLED = "Untitled analysis"
"""What an authored draft is called until somebody names it.

**Not derived from the prompt.** A first sentence is the likeliest place for a sample name or a
cohort label to appear, and a draft's name is shown in lists and carried into a kept artifact's
directory — §2 already excludes draft labels from what a model is shown, and a name *made from*
the prompt would put the prompt somewhere that exclusion was never meant to reach.
"""

def open_session(draft_id: str, *, mode: Mode, who: str) -> str:
    """Start a conversation about a draft, or refuse if one is already open.

    **One session per draft**, which the unique index enforces and this refuses first — the same
    two-mechanism arrangement `forge_state.begin` uses, so a person reads a sentence rather than
    a constraint violation.
    """
    with session_scope() as session:
        if session.get(PipelineDraft, draft_id) is None:
            raise KeyError(draft_id)

        existing = session.scalar(
            select(PipelineAuthoringSession).where(
                PipelineAuthoringSession.draft_id == draft_id
            )
        )
        if existing is not None:
            raise ValueError(
                coded("MI0200", "this draft already has an authoring session")
                + f"\n  it is {existing.id}, in phase {existing.phase}"
            )

        session_id = new_id()
        now = _now()
        session.add(
            PipelineAuthoringSession(
                id=session_id,
                draft_id=draft_id,
                mode=mode.value,
                phase=Phase.UNDERSTANDING.value,
                at="say",
                failed_from=None,
                goal=None,
                facts=[],
                blueprint={},
                registry_digest="",
                cursor=0,
                row_version=1,
                who=who,
                created_at=now,
                updated_at=now,
            )
        )
    return session_id

def record_said(session_id: str, text: str) -> int:
    """Record what a person said, and the pending turn that will answer it; returns its `seq`.

    **Two rows, written together.** The assistant's turn exists as `pending` from the moment the
    person's is accepted, so the transcript can draw the waiting. A browser inventing that
    placeholder locally would lose it on reload, which is the defect this closes rather than the
    tidiness it looks like.
    """
    with session_scope() as db:
        row = db.get(PipelineAuthoringSession, session_id)
        if row is None:
            raise KeyError(session_id)
        draft = db.get(PipelineDraft, row.draft_id)
        revision = draft.revision if draft else 0

        seq = next_seq(db, session_id)
        now = _now()
        db.add(
            PipelineAuthoringTurn(
                session_id=session_id,
                seq=seq,
                role="person",
                state=TurnState.ANSWERED.value,
                blocks=[],
                text=text,
                base_revision=revision,
                at=now,
            )
        )
        db.add(
            PipelineAuthoringTurn(
                session_id=session_id,
                seq=seq + 1,
                role="assistant",
                state=TurnState.PENDING.value,
                blocks=[],
                text="",
                base_revision=revision,
                at=now,
            )
        )
    return seq + 1

def answer(
    session_id: str,
    seq: int,
    *,
    blocks: list,
    base_revision: int,
    invocation_id: str | None = None,
) -> bool:
    """Fill in a pending assistant turn, unless the draft has moved under it.

    **Returns `False` rather than raising when the answer is late.** A model call that finishes
    after the person revised their goal has not failed — it answered a question that is no longer
    being asked — and the turn is marked `failed` so the transcript says so. Raising would make
    the worker's ordinary case an exception path.
    """
    with session_scope() as db:
        row = db.get(PipelineAuthoringSession, session_id)
        if row is None:
            raise KeyError(session_id)
        draft = db.get(PipelineDraft, row.draft_id)
        current = draft.revision if draft else 0

        late = current != base_revision
        done = db.execute(
            update(PipelineAuthoringTurn)
            .where(
                PipelineAuthoringTurn.session_id == session_id,
                PipelineAuthoringTurn.seq == seq,
                PipelineAuthoringTurn.state == TurnState.PENDING.value,
            )
            .values(
                state=TurnState.FAILED.value if late else TurnState.ANSWERED.value,
                blocks=[] if late else blocks,
                ai_invocation_id=invocation_id,
                at=_now(),
            )
        )
        # rowcount 0 is a duplicate delivery: the turn is already answered, and re-answering it
        # would overwrite one account of what happened with another.
        return done.rowcount == 1 and not late

def pending_turn(session_id: str) -> int:
    """A new pending assistant turn, for a retry into understanding (`family`). **A new turn
    rather than re-opening the failed one**: the failed turn is the record that the call failed,
    its notice says why, and overwriting it would erase what a person trying to understand a flaky
    provider needs to see."""
    with session_scope() as db:
        draft = db.get(PipelineDraft, db.get(PipelineAuthoringSession, session_id).draft_id)
        seq = next_seq(db, session_id)
        db.add(
            PipelineAuthoringTurn(
                session_id=session_id,
                seq=seq,
                role="assistant",
                state=TurnState.PENDING.value,
                blocks=[],
                text="",
                base_revision=draft.revision if draft else 0,
                at=_now(),
            )
        )
    return seq

def newest_pending(session_id: str) -> int | None:
    """The newest pending assistant turn: the one `describe` just wrote."""
    with session_scope() as db:
        return db.scalar(
            select(PipelineAuthoringTurn.seq)
            .where(
                PipelineAuthoringTurn.session_id == session_id,
                PipelineAuthoringTurn.role == "assistant",
                PipelineAuthoringTurn.state == TurnState.PENDING.value,
            )
            .order_by(PipelineAuthoringTurn.seq.desc())
            .limit(1)
        )

class TurnContext(NamedTuple):
    """What one model call is grounded on, read in one transaction so the parts agree.

    §2: *ground every authoring call on the confirmed goal, current known step ids and
    contracts, current pending options, registry digest, and bounded tail — not on the transcript
    alone.* Each of those is a field here, and nothing else is, which is why a draft's label is
    not among them.
    """

    phase: Phase
    prompt: str
    tail: list[tuple[str, str]]
    revision: int
    goal: Goal | None
    steps: list[tuple[str, str]]
    options: list[str]
    registry: str | None

def turn_context(session_id: str, seq: int) -> TurnContext | None:
    """The grounding for assistant turn `seq`, or `None` when that turn is not pending.

    `None` is how a duplicate delivery is recognised **before** a model call is spent, which the
    queue's job id alone cannot promise once Redis has forgotten the id.
    """
    with session_scope() as db:
        row = db.get(PipelineAuthoringSession, session_id)
        if row is None:
            raise KeyError(session_id)
        turns = db.scalars(
            select(PipelineAuthoringTurn)
            .where(PipelineAuthoringTurn.session_id == session_id)
            .order_by(PipelineAuthoringTurn.seq)
        ).all()
        target = next((t for t in turns if t.seq == seq), None)
        if target is None or target.role != "assistant" or target.state != TurnState.PENDING.value:
            return None

        earlier = [t for t in turns if t.seq < seq]
        person = next((t for t in reversed(earlier) if t.role == "person"), None)
        tail = [
            ("person" if t.role == "person" else "model", _spoken(t))
            for t in earlier
            if t is not person and (t.role == "person" or t.state == TurnState.ANSWERED.value)
        ]
        draft = db.get(PipelineDraft, row.draft_id)
        pending = db.scalar(
            select(PipelineAuthoringProposal).where(
                PipelineAuthoringProposal.session_id == session_id,
                PipelineAuthoringProposal.state == ProposalState.PENDING.value,
            )
        )
        # The card's composed goal while it is on offer: `row.goal` holds only the want until the
        # person confirms it (14.7.3).
        card = pending.payload.get("goal") if pending is not None and pending.kind == GOAL else None
        goal = card or row.goal
        return TurnContext(
            phase=Phase(row.phase),
            prompt=person.text if person is not None else "",
            tail=[(role, text) for role, text in tail if text],
            revision=draft.revision if draft else 0,
            goal=authoring.as_goal(goal),
            steps=[
                (node.id, node.contract_id)
                for node in DraftGraph.model_validate(draft.graph).nodes
            ]
            if draft
            else [],
            options=sorted(pending.payload.get("options", {})) if pending is not None else [],
            registry=row.registry_digest or None,
        )

def _spoken(turn: PipelineAuthoringTurn) -> str:
    """What an assistant turn *said*, for the tail — the prose of its blocks, never their ids.

    A goal summary is its three sentences; a narrative or a notice is its text; a question is
    what it asks. Structured
    blocks — a step proposal, a question's options — are the engine's own vocabulary and reach
    the model through `steps` and `options`, where they are held to admission, rather than as
    prose it could quote back as if it had authored them.
    """
    if turn.role == "person":
        return turn.text
    said = []
    for block in turn.blocks or []:
        if block.get("kind") == "goal_summary":
            said.append(f"{block['have']} {block['do']} {block['get']}")
        elif block.get("kind") in ("narrative", "notice"):
            said.append(block.get("text", ""))
        elif block.get("kind") == "question":
            # **What was asked, so the reply is read with it** (#202): a short answer to the
            # engine's *what result do you want?* means nothing without the question. The prose
            # only; the options stay out, as above.
            said.append(block.get("asks", ""))
    return " ".join(part for part in said if part)


# ── the commands ─────────────────────────────────────────────────────────────────────────


@records(c.OpenSession)
def _open(ctx: Ctx, cmd: c.OpenSession) -> str:
    ctx.session_id = open_session(cmd.draft_id, mode=Mode(cmd.mode), who=cmd.who)
    return ctx.session_id


@records(c.Begin)
def _begin(ctx: Ctx, cmd: c.Begin) -> tuple[str, int]:
    """An empty draft, a session about it, and the first turn: one act for a person, and now one
    transaction, so a failure part-way leaves nothing a person could open."""
    from mendel_api.services import drafts

    ctx.session_id = open_session(
        drafts.create(DraftGraph(), UNTITLED, cmd.who), mode=Mode(cmd.mode), who=cmd.who
    )
    return ctx.session_id, _said(ctx, cmd.prompt)


@records(c.Say)
def _say(ctx: Ctx, cmd: c.Say) -> int:
    return _said(ctx, cmd.text)


def _said(ctx: Ctx, text: str) -> int:
    """Record the words and the pending turn that will answer them (`record_said`). **Typed words
    are a command only where the diagram draws one** (14.7.8.1): what you want at `say` (`family`
    queues its reading), an answer at `reply` (`suggest` queues it). Anywhere else they are a chat
    turn, which moves nothing, and its answer is queued here."""
    seq = record_said(ctx.session_id, text)
    for typed in (Command.DESCRIBE, Command.REPLY_IN_WORDS):
        if session.allows(ctx.session_id, typed.value):
            session.take(ctx, typed.value)
            return seq
    ctx.queue(_jobs.turn(ctx.session_id, seq))
    return seq


@records(c.AnswerTurn)
def _answer_turn(ctx: Ctx, cmd: c.AnswerTurn) -> bool:
    return answer(
        cmd.session_id,
        cmd.seq,
        blocks=cmd.blocks,
        base_revision=cmd.base_revision,
        invocation_id=cmd.invocation_id,
    )


@records(c.Understood)
def _understood(ctx: Ctx, cmd: c.Understood) -> None:
    session.take(ctx, Command.UNDERSTOOD.value, goal=cmd.goal)


@records(c.AskedBack)
def _asked_back(ctx: Ctx, cmd: c.AskedBack) -> None:
    session.take(ctx, Command.ASKED_BACK.value)


@records(c.ProviderFailed)
def _provider_failed(ctx: Ctx, cmd: c.ProviderFailed) -> None:
    session.take(ctx, Command.PROVIDER_FAILED.value)


@records(c.Retry)
def _retry(ctx: Ctx, cmd: c.Retry) -> tuple[Phase, int | None]:
    """Leave `failed` for whichever phase failed (`retry`). Into understanding, `family` writes
    the new pending turn and queues it (`pending_turn`)."""
    session.take(ctx, Command.RETRY.value)
    return session.current_phase(ctx.session_id), ctx.payload.get("seq")


# ── the handlers ─────────────────────────────────────────────────────────────────────────


@handles("family")
def family(ctx: Ctx) -> None:
    """The model reads what was said (ruling 5 of plan 1c). `describe` wrote the pending turn;
    `retry` writes a new one here. On `revised` the job reading the correction answers inline,
    and resuming here queues nothing: the turn already waiting was queued when it was written."""
    if ctx.command == Command.RETRY.value:
        seq = pending_turn(ctx.session_id)
    elif ctx.command == Command.DESCRIBE.value:
        seq = newest_pending(ctx.session_id)
    else:
        return None
    ctx.payload["seq"] = seq
    ctx.queue(_jobs.turn(ctx.session_id, seq))
    return None


@handles("read_goal")
def read_goal(ctx: Ctx) -> str:
    """Store the want the model read; the engine takes over to gather what it needs."""
    store_goal(ctx.session_id, ctx.payload["goal"])
    return "want_returned"

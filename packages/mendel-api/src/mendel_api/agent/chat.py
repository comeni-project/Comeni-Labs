"""The agent chat as the routes use it (#463): start, say, answer a question, retry a failed
turn, and what the AI chose that nobody has reviewed yet."""

import logging

from comeni_core.diagnostics import coded
from comeni_core.plan.draft import DraftGraph
from mendel_authoring.blueprint import Blueprint
from mendel_authoring.reviews import fingerprint
from sqlalchemy import select

from mendel_api import jobs
from mendel_api.agent import loop
from mendel_api.authoring.types import TurnRole, TurnState
from mendel_api.db import session_scope
from mendel_api.models import PipelineAuthoringSession, PipelineAuthoringTurn
from mendel_api.services import decisions, drafts

UNTITLED = "Untitled analysis"

log = logging.getLogger(__name__)


async def _queue(session_id: str, seq: int) -> bool:
    """The agent's turn, queued for the AI worker. **A turn that cannot be queued fails at
    once** (#463 review): left pending, it would wait for a job that never comes, the page would
    say it is working, and Retry would not be offered."""
    try:
        return await jobs.enqueue("run_builder_turn", session_id, seq,
                                  job_id=f"builder:agent:{session_id}:{seq}", queue=jobs.AI_QUEUE)
    except Exception:  # noqa: BLE001 — any queue failure ends the turn, coded
        log.exception("builder turn %s:%s could not be queued", session_id, seq)
        loop.fail(session_id, seq, "The builder could not start working on this. Try again.")
        return False


async def start(prompt: str, who: str) -> tuple[str, bool]:
    """A new draft, its session, the person's words, and the agent's turn queued."""
    session_id = loop.start_session(drafts.create(DraftGraph(), UNTITLED, who), who=who)
    seq = loop.add_person_turn(session_id, prompt)
    return session_id, await _queue(session_id, seq)


async def say(session_id: str, text: str, console=None) -> tuple[int, bool]:
    seq = loop.add_person_turn(session_id, text, console)
    return seq, await _queue(session_id, seq)


def _asked(session_id: str, question_id: str) -> dict:
    with session_scope() as db:
        turns = db.scalars(select(PipelineAuthoringTurn)
                           .where(PipelineAuthoringTurn.session_id == session_id)
                           .order_by(PipelineAuthoringTurn.seq.desc())).all()
    for turn in turns:
        for block in turn.blocks:
            if block.get("kind") == "ask" and block.get("question_id") == question_id:
                return block
    raise KeyError(question_id)


async def answer(session_id: str, question_id: str, value) -> tuple[int, bool]:
    """The person's answer to the agent's question, as their next words."""
    asked = _asked(session_id, question_id)
    said = {True: "yes", False: "no"}.get(value, value) if isinstance(value, bool) else value
    unit = f" {asked['unit']}" if asked.get("unit") and not isinstance(value, bool) else ""
    # **Only the answer is the person's words** (walk 2026-11-15): the bubble repeated the whole
    # question. The agent has its question in the history already ("(I asked: …)").
    return await say(session_id, f"{said}{unit}")


def _waiting_for_data(draft_id: str) -> str | None:
    """The draft's session, when its agent's last turn asked for data and nothing was said
    since; otherwise `None`."""
    with session_scope() as db:
        session_id = db.scalar(select(PipelineAuthoringSession.id).where(
            PipelineAuthoringSession.draft_id == draft_id))
        if session_id is None:
            return None
        last = db.scalar(select(PipelineAuthoringTurn)
                         .where(PipelineAuthoringTurn.session_id == session_id)
                         .order_by(PipelineAuthoringTurn.seq.desc()).limit(1))
    asked = last is not None and last.role == TurnRole.ASSISTANT.value and any(
        b.get("kind") == "ask" and b.get("shape") == "data" for b in last.blocks or [])
    return session_id if asked else None


def rebuild_for_data(draft_id: str, who: str) -> None:
    """The draft's pipeline built again from facts its new data established (#511), when it has
    a conversation and a pipeline to rebuild."""
    from mendel_api.agent.direct import _rebuild
    from mendel_api.models import PipelineDraft

    with session_scope() as db:
        session_id = db.scalar(select(PipelineAuthoringSession.id).where(
            PipelineAuthoringSession.draft_id == draft_id))
        draft = db.get(PipelineDraft, draft_id)
        drawn = bool(draft and (draft.graph or {}).get("nodes"))
    if session_id and drawn:
        _rebuild(session_id, draft_id, who)


_DATA_SAID = ("I added data in Data:", "My data changed in Data:")


def _told_and_unbuilt(draft_id: str) -> tuple[str, str] | None:
    """The draft's session and what its agent last heard about the data, when it has heard once,
    has built nothing yet and is not working: a change in Data since is news to it."""
    from mendel_api.models import PipelineDraft

    with session_scope() as db:
        session_id = db.scalar(select(PipelineAuthoringSession.id).where(
            PipelineAuthoringSession.draft_id == draft_id))
        draft = db.get(PipelineDraft, draft_id)
        if session_id is None or (draft and (draft.graph or {}).get("nodes")):
            return None
        turns = db.scalars(select(PipelineAuthoringTurn)
                           .where(PipelineAuthoringTurn.session_id == session_id)
                           .order_by(PipelineAuthoringTurn.seq.desc())).all()
        if any(t.state == TurnState.PENDING.value for t in turns):
            return None
        heard = next((t.text for t in turns if t.role == TurnRole.PERSON.value
                      and (t.text or "").startswith(_DATA_SAID)), None)
    return (session_id, heard) if heard else None


async def data_scanned(draft_id: str) -> None:
    """**A finished scan answers the agent's `data` question** (#511, Checkpoint A): the person
    ticked folders in Data rather than typing, so what was found is said for them, as the person's
    answer: how many samples, of what, and what was measured. Counts and measurements only,
    never a path.

    **Until the agent has built, a change is said too** (walk 2026-11-17): it heard the first scan
    and answered without building; the person then paired a read, left a sample out and added
    the references, and it heard none of it, so Build stayed empty. A reading it already heard
    is not said again; once a pipeline is built, `rebuild_for_data` keeps it current instead."""
    from mendel_api.models import AnalysisData

    session_id, heard = _waiting_for_data(draft_id), None
    if session_id is None:
        told = _told_and_unbuilt(draft_id)
        if told is None:
            return
        session_id, heard = told
    with session_scope() as db:
        row = db.get(AnalysisData, draft_id)
        samples = [s for s in (row.samples if row else []) if not s.get("left_out")]
        references = sorted(r["type_id"] for r in (row.references if row else []))
    kinds = sorted({s.get("type_id") or "unrecognised" for s in samples})
    measured = sorted({f["measurement"] for s in samples for f in s.get("facts", [])})
    reading = (f"{len(samples)} sample{'' if len(samples) == 1 else 's'} "
               f"({', '.join(kinds) or 'none'})")
    reading += f"; measured {', '.join(measured)}" if measured else ""
    reading += f"; references: {', '.join(references)}." if references else "; no references."
    if heard is not None:
        if heard.split(":", 1)[1].strip() == reading:
            return
        await say(session_id, f"{_DATA_SAID[1]} {reading}")
        return
    await say(session_id, f"{_DATA_SAID[0]} {reading}")


async def retry(session_id: str, seq: int) -> bool:
    """A failed turn, asked again. Refused for a turn that is not failed (`MI0203`)."""
    with session_scope() as db:
        turn = db.scalar(select(PipelineAuthoringTurn).where(
            PipelineAuthoringTurn.session_id == session_id, PipelineAuthoringTurn.seq == seq))
        if turn is None or turn.role != TurnRole.ASSISTANT.value:
            raise KeyError(seq)
        if turn.state != TurnState.FAILED.value:
            raise LookupError(coded("MI0203", "only a turn that failed is retried"))
        turn.state, turn.blocks = TurnState.PENDING.value, []
        db.get(PipelineAuthoringSession, session_id).row_version += 1
    return await _queue(session_id, seq)


GRACE_SECONDS = 60
"""How long a pending turn waits for its job before a missing job means the worker died."""


async def sweep(session_id: str) -> None:
    """**A turn whose worker died is failed, not left pending** (#463 review): past the grace
    period, a pending turn with no job queued or running ends coded `MI0220`, so the page
    stops polling and offers Retry."""
    from datetime import UTC, datetime, timedelta

    with session_scope() as db:
        pending = db.scalars(select(PipelineAuthoringTurn).where(
            PipelineAuthoringTurn.session_id == session_id,
            PipelineAuthoringTurn.role == TurnRole.ASSISTANT.value,
            PipelineAuthoringTurn.state == TurnState.PENDING.value)).all()
        stale = [t.seq for t in pending
                 if datetime.now(UTC) - t.at > timedelta(seconds=GRACE_SECONDS)]
    for seq in stale:
        if not await jobs.running(f"builder:agent:{session_id}:{seq}", jobs.AI_QUEUE):
            loop.fail(session_id, seq, "The builder stopped before it finished. Try again.")


def working(turns: list[dict]) -> bool:
    return any(t["role"] == "assistant" and t["state"] == "pending" for t in turns)


def _blueprint(session_id: str) -> tuple[str, Blueprint | None]:
    with session_scope() as db:
        row = db.get(PipelineAuthoringSession, session_id)
        stored = row.blueprint or None
        return row.draft_id, Blueprint.model_validate(stored) if stored else None


def _ai_steps(blueprint: Blueprint) -> list[dict]:
    out = []
    for step in blueprint.pipeline.steps:
        # Each with the reason the AI gave (walk 2026-11-15): the card says why, not only what.
        if step.why.source.value == "model":
            out.append({"node": step.id, "what": f"chose {step.module.contract_id}",
                        "because": step.why.reason})
        out += [{"node": step.id, "what": f"set {s.name} to {s.value}", "because": s.why.reason}
                for s in step.settings if s.why.source.value == "model"]
    return out


def choices(session_id: str) -> list[dict]:
    """What the AI chose in the pipeline last built, each with whether a person has reviewed it
    as it now is; sorted by step and words."""
    draft_id, blueprint = _blueprint(session_id)
    if blueprint is None:
        return []
    seen = {(r.node, r.fingerprint) for r in decisions.reviews(draft_id)}
    return sorted(({**m, "reviewed": (m["node"], fingerprint(blueprint, m["node"])) in seen}
                   for m in _ai_steps(blueprint)), key=lambda m: (m["node"], m["what"]))


def unreviewed(session_id: str) -> list[dict]:
    """What the AI chose, in the pipeline last built, that nobody has reviewed as it now is."""
    return [{"node": m["node"], "what": m["what"], "because": m["because"]}
            for m in choices(session_id) if not m["reviewed"]]


def review(session_id: str, nodes: list[str] | str, who: str) -> None:
    """The person has looked at what the AI chose, at these steps or at all of them."""
    draft_id, blueprint = _blueprint(session_id)
    if blueprint is None:
        return
    chosen = {m["node"] for m in _ai_steps(blueprint)}
    for node in sorted(chosen if nodes == "all" else chosen & set(nodes)):
        decisions.record_review(draft_id, blueprint, node, who=who)

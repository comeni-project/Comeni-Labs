"""Setup for the authoring tests: a session put in a phase by event, and the two resumes tests
drive by hand. **Nothing under `src/` may call these** (`test_authoring_binding.py`)."""

from comeni_core.diagnostics import coded
from comeni_core.goal.asked import Goal
from mendel_api.authoring.types import Fact, Phase
from mendel_api.db import transaction
from mendel_api.models import PipelineAuthoringSession
from mendel_api.services import authoring_decisions, decisions, session
from mendel_api.stages._rows import now as _now
from mendel_authoring import commands as c
from mendel_authoring import state as st
from sqlalchemy import update


def move(session_id: str, event: st.Event, *, row_version: int, **values: object) -> Phase:
    """One phase change, compare-and-swap on the session's own version.

    **Setup for tests only** (ruling 5 of 14.7.8.1b): nothing under `src/` calls it, which
    `test_authoring_binding.py` holds. It clears `at`, so the node is derived from the phase it
    sets (`session.rests_at`).

    `state.advance` decides *whether* and `UPDATE … WHERE row_version` decides *whether it is
    still ours*. Both are needed and they catch different mistakes — the first an illegal move,
    the second a legal move applied to a session somebody else already moved.
    """
    with transaction() as db:
        row = db.get(PipelineAuthoringSession, session_id)
        if row is None:
            raise KeyError(session_id)

        current = Phase(row.phase)
        came_from = Phase(row.failed_from) if row.failed_from else None
        target = st.advance(current, event, came_from)

        # Cleared on every move that is not *into* failure, so a retried session does not carry
        # the phase of a failure it has already recovered from: a stale one sends the next
        # retry wrong.
        failed = st.failed_from(current).value if target is Phase.FAILED else None

        if "goal" in values:
            goal = values.pop("goal")
            if target in (Phase.UNDERSTANDING, Phase.GATHERING):
                # Before confirmation the want lives in the rows (Part I.0 §6.2).
                seed_rows(row.draft_id, (goal or {}).get("want", []))
            else:
                decisions.import_goal(row.draft_id, Goal.model_validate(goal or {}), who=row.who)
                decisions.confirm(row.draft_id)
        if "facts" in values:
            for fact in values.pop("facts"):
                authoring_decisions.record(row.draft_id, Fact.model_validate(fact), who=row.who)
        if "policy" in values:
            policy = values.pop("policy") or {}
            values.update(pacing=policy.get("pacing"), show_gaps=policy.get("show_gaps"))

        done = db.execute(
            update(PipelineAuthoringSession)
            .where(
                PipelineAuthoringSession.id == session_id,
                PipelineAuthoringSession.row_version == row_version,
            )
            .values(
                phase=target.value,
                failed_from=failed,
                at=None,
                row_version=row_version + 1,
                updated_at=_now(),
                **values,
            )
        )
        if done.rowcount != 1:
            raise ValueError(
                coded("MI0201", "this session moved while you were looking at it")
                + f"\n  you held version {row_version}; it is at {row.row_version}"
                + "\n  re-read it before acting on it"
            )
    return target


def offer_next_gap(session_id: str) -> str | None:
    """Resume the session where it rests (`list_needs` or `next_gap`): the pending proposal's
    id, or `None` when nothing can make the want and the person was asked again (#202)."""
    ran = session.perform(c.Resume(session_id)).result
    return session.pending_id(session_id) if ran.at in {"reply", "card"} else None


def start_building(session_id: str) -> str | None:
    return session.perform(c.StartBuilding(session_id)).result


def seed_rows(draft_id: str, want, stated=()) -> None:
    """What a model's first reading leaves: the want in the rows, unconfirmed (Part I.0 §6.2)."""
    from mendel_authoring.decisions import ActorKind

    for type_id in want:
        decisions.set_want(draft_id, type_id, who="model", actor_kind=ActorKind.MODEL)


def seed(session_id: str, want, stated=(), suggested_states=()) -> None:
    """A session as the model's reading leaves it: the want recorded, what it heard unquoted
    offered as suggestions (Part I.0 §5.3)."""
    from mendel_api.services import suggestions
    from mendel_authoring.payloads import DecisionChange

    with transaction() as db:
        draft_id = db.get(PipelineAuthoringSession, session_id).draft_id
    seed_rows(draft_id, want)
    for said in stated:
        value = said.get("value", True) if said["kind"] == "input" else said.get("value")
        suggestions.offer(
            session_id,
            DecisionChange(kind=said["kind"], subject=said["subject"], value=value, actor="model"),
            heard=False,
            invocation_id=None,
        )
    for r in suggested_states:
        suggestions.offer(
            session_id,
            DecisionChange(kind="require", subject=r["type_id"], states=r["states"], actor="model"),
            heard=False,
            invocation_id=None,
        )

"""Setup for the authoring tests: a session put in a phase by event, and the two resumes tests
drive by hand. **Nothing under `src/` may call these** (`test_authoring_binding.py`)."""

from comeni_core.diagnostics import coded
from mendel_api.authoring.types import Phase
from mendel_api.db import session_scope
from mendel_api.models import PipelineAuthoringSession
from mendel_api.services import session
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
    with session_scope() as db:
        row = db.get(PipelineAuthoringSession, session_id)
        if row is None:
            raise KeyError(session_id)

        current = Phase(row.phase)
        came_from = Phase(row.failed_from) if row.failed_from else None
        target = st.advance(current, event, came_from)

        # Cleared on every move that is not *into* failure, so a retried session does not carry
        # the phase of a failure it has already recovered from — `forge_state.move` clears
        # `failed_stage` for exactly this reason, and a stale one sends the next retry wrong.
        failed = st.failed_from(current).value if target is Phase.FAILED else None

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

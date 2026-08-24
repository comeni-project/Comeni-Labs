"""The record, and the cache over it.

`run_event` is the source of truth; `state_of` replays it. `record` appends one event, folds it
into the cached projection, and returns the new state. Rebuilding from scratch is always legal
and is what `state_of` does — the cache exists so a page load does not fold three days of
events, not because the fold is untrustworthy.

**Every table access goes through `repository`** — A177. The plan wrote `select()` calls here
and `test_no_query_is_built_outside_the_repository` refused them, which is the guard doing the
job it was widened to do rather than an inconvenience routed around.
"""

import logging
from datetime import UTC, datetime

from redis.exceptions import RedisError
from sqlalchemy.orm import Session
from wiener_core.events import RunEvent, admit
from wiener_core.state import EMPTY, RunState, fold, replay

from wiener_api import repository
from wiener_api.models import RunEventRow, RunTask
from wiener_api.services import stream

log = logging.getLogger(__name__)


def state_of(session: Session, lab_id: str, run_id: str) -> RunState:
    """The run, folded from its record. No cache is consulted and none is trusted."""
    return replay(RunEvent.model_validate(row.payload) for row in
                  repository.events(session, lab_id, run_id))


def record(session: Session, lab_id: str, run_id: str, payload: dict) -> RunState:
    """Admit one weblog body, append it to the record, and refresh the projections."""
    seq = repository.next_seq(session, lab_id, run_id)
    event = admit(payload, run_id=run_id, seq=seq)

    repository.add(session, lab_id, RunEventRow(
        run_id=run_id, seq=seq, kind=event.kind, at_ms=event.at_ms,
        payload=event.model_dump(mode="json"), received_at=datetime.now(UTC),
    ))

    prior = state_of(session, lab_id, run_id) if seq else EMPTY
    state = fold(prior, event)

    if (row := repository.run(session, lab_id, run_id)) is not None:
        row.phase = state.phase
        if state.ended_at_ms:
            row.ended_at = datetime.fromtimestamp(state.ended_at_ms / 1000, UTC)

    for task in state.tasks.values():
        existing = repository.task(session, lab_id, run_id, task.task_id)
        if existing is None:
            existing = RunTask(run_id=run_id, task_id=task.task_id)
            repository.add(session, lab_id, existing)
        existing.process, existing.status = task.process, task.status
        existing.attempts = [a.model_dump(mode="json") for a in task.attempts]
        existing.latest_exit = task.latest_exit
        existing.last_change_ms = task.last_change_ms

    session.flush()
    # **After the flush and never before.** A stream entry for an event Postgres has not
    # accepted is a tail that disagrees with the record, and the record is what a reload
    # rebuilds from — so a browser would see something that no longer exists.
    try:
        stream.publish(run_id, event)
    except RedisError as exc:
        # **The tail is lossy by design; the record is not.** Losing Redis must not lose an
        # event, so this cannot raise — but a dead tail that nobody notices is a console that
        # silently stops updating, so it does not pass quietly either.
        log.warning("run %s: event %s recorded but not published: %s", run_id, event.seq, exc)
    return state

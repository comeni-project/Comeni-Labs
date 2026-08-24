"""What a run *is*: a fold over the events it produced.

**Idempotent in two different ways, and A176 is about not confusing them.**

- `event.seq <= state.last_seq` returns the state unchanged. That covers **replay** — the same
  recorded event folded twice — and nothing else, because `seq` is assigned as bodies arrive
  (§6.2), so a redelivery over the network carries a *fresh* one.
- **Convergence covers redelivery.** Every field the fold writes is a function of what has been
  seen rather than of how often: `terminal_seen` is a set, `counts` is derived from `tasks`,
  and an attempt is keyed by `trace.attempt`. Folding a body twice lands in the same state.

The spec attributed §4.3 finding 2 to the first mechanism; it is the second that handles it.

**An attempt is keyed, never appended.** A task that ran once is described by three events —
submitted, started, completed — so appending per event gave it three attempts and drew a retry
ring (§9.1) on a task that never retried. `attempts` holds one entry per `trace.attempt`, in
order, and a later event for the same `n` replaces the earlier one.

**Terminality is a set, not a flag** — finding 3. `error` can arrive after `completed`, so the
outcome is decided by what has been *seen*, never by what arrived last.
"""

from collections.abc import Iterable, Mapping
from enum import StrEnum

from pydantic import BaseModel, ConfigDict

from wiener_core.events import EventKind, RunEvent, TaskStatus


class RunPhase(StrEnum):
    QUEUED = "queued"
    LAUNCHING = "launching"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    LOST = "lost"


class Attempt(BaseModel):
    model_config = ConfigDict(frozen=True)
    n: int
    status: TaskStatus
    exit: int | None = None
    at_ms: int


class TaskState(BaseModel):
    model_config = ConfigDict(frozen=True)
    task_id: int
    process: str
    status: TaskStatus
    attempts: tuple[Attempt, ...] = ()
    latest_exit: int | None = None
    first_seen_ms: int
    last_change_ms: int


class Counts(BaseModel):
    model_config = ConfigDict(frozen=True)
    succeeded: int = 0
    failed: int = 0
    cached: int = 0
    running: int = 0
    submitted: int = 0


class RunState(BaseModel):
    model_config = ConfigDict(frozen=True)
    run_id: str = ""
    phase: RunPhase = RunPhase.QUEUED
    tasks: Mapping[int, TaskState] = {}
    counts: Counts = Counts()
    started_at_ms: int | None = None
    ended_at_ms: int | None = None
    last_seq: int = -1
    terminal_seen: frozenset[EventKind] = frozenset()
    run_succeeded: bool | None = None


EMPTY = RunState()

_TERMINAL = {EventKind.COMPLETED, EventKind.ERROR}


def _counts(tasks: Mapping[int, TaskState]) -> Counts:
    by = [t.status for t in tasks.values()]
    return Counts(
        succeeded=by.count(TaskStatus.COMPLETED),
        failed=by.count(TaskStatus.FAILED),
        cached=by.count(TaskStatus.CACHED),
        running=by.count(TaskStatus.RUNNING),
        submitted=by.count(TaskStatus.SUBMITTED),
    )


def _phase(seen: frozenset[EventKind], succeeded: bool | None, started: bool) -> RunPhase:
    if EventKind.ERROR in seen:
        return RunPhase.FAILED
    if EventKind.COMPLETED in seen:
        return RunPhase.SUCCEEDED if succeeded is not False else RunPhase.FAILED
    return RunPhase.RUNNING if started else RunPhase.QUEUED
    # `started` rather than "any event has arrived" — A175 put a HEARTBEAT in the stream, and
    # time passing is not a run beginning. `LAUNCHING` is set by the launcher (Task 7), which
    # is the only thing that knows a subprocess exists.


def fold(state: RunState, event: RunEvent) -> RunState:
    if event.seq <= state.last_seq:
        return state

    tasks = dict(state.tasks)
    if (tr := event.trace) is not None:
        prior = tasks.get(tr.task_id)
        attempt = Attempt(n=tr.attempt, status=tr.status, exit=tr.exit, at_ms=event.at_ms)
        # Keyed by attempt number, not appended — A176. Three events describe one try, and a
        # redelivered body is a fourth; all four are the same attempt reaching a later status.
        by_n = {a.n: a for a in (prior.attempts if prior else ())}
        by_n[attempt.n] = attempt
        attempts = tuple(by_n[n] for n in sorted(by_n))
        tasks[tr.task_id] = TaskState(
            task_id=tr.task_id, process=tr.process, status=tr.status,
            attempts=attempts, latest_exit=tr.exit,
            first_seen_ms=prior.first_seen_ms if prior else event.at_ms,
            last_change_ms=event.at_ms,
        )

    seen = state.terminal_seen | ({event.kind} if event.kind in _TERMINAL else frozenset())
    succeeded = state.run_succeeded
    if event.manifest is not None and event.manifest.success is not None:
        succeeded = event.manifest.success

    started_at = state.started_at_ms or (
        event.at_ms if event.kind is EventKind.STARTED else None)
    started = started_at is not None

    return state.model_copy(update={
        "run_id": event.run_id or state.run_id,
        "tasks": tasks,
        "counts": _counts(tasks),
        "last_seq": event.seq,
        "terminal_seen": seen,
        "run_succeeded": succeeded,
        "started_at_ms": started_at,
        "ended_at_ms": event.at_ms if seen and not state.ended_at_ms else state.ended_at_ms,
        "phase": _phase(seen, succeeded, started),
    })


def replay(events: Iterable[RunEvent]) -> RunState:
    state = EMPTY
    for event in events:
        state = fold(state, event)
    return state

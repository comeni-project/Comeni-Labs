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

from wiener_core.events import FROM_NEXTFLOW, EventKind, RunEvent, TaskStatus


class RunPhase(StrEnum):
    QUEUED = "queued"
    LAUNCHING = "launching"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    LOST = "lost"


class Attempt(BaseModel):
    """One try at a task, and everything the trace said about it.

    **It carries the resources because nothing downstream can get them otherwise** — A184.
    `admit()` keeps the fifteen `trace.enabled` fields and the fold was dropping them, so spans,
    §9.3's panel and `run_task`'s attempts column were all blind to what the record held. That
    is Checkpoint 2's finding one layer up: the record could be replayed to recover, a
    projection could not.

    **Per attempt, not per task**, which is the other half. §8 gives each attempt its own span
    with its own start and end, and `TaskState.first_seen_ms` / `last_change_ms` are per *task* —
    a retried task's three spans would otherwise share one pair of timestamps. A retry that
    asked for more memory is the whole reason retries are history (§5.1).
    """

    model_config = ConfigDict(frozen=True)
    n: int
    status: TaskStatus
    exit: int | None = None
    at_ms: int

    start_ms: int | None = None
    complete_ms: int | None = None
    duration_ms: int | None = None
    realtime_ms: int | None = None
    """`duration - realtime` is queue wait, which on a cluster is the number that explains a
    slow run — and nothing standard has a name for it."""

    cpus: int | None = None
    pct_cpu: float | None = None
    memory_bytes: int | None = None
    peak_rss_bytes: int | None = None
    rchar: int | None = None
    wchar: int | None = None
    read_bytes: int | None = None
    write_bytes: int | None = None
    """**Absent rather than zero** when the run was launched without `trace.enabled` (§4.3
    finding 6). A zero would read as "this task used no memory", which is a lie about a real
    number."""


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
    last_activity_ms: int | None = None
    """When Nextflow last said anything. **A heartbeat is not activity.**

    That distinction is the whole of `LOST` detection (§17): the timer's heartbeat is what
    *wakes* the check, and if it also counted as a sign of life the check could never fire —
    a dead head process would look alive precisely because Wiener kept talking to itself."""
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


_TERMINAL_STATUS = {TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.ABORTED,
                    TaskStatus.CACHED}


def _merge(prior: Attempt | None, latest: Attempt) -> Attempt:
    """One attempt, from however many events described it.

    A field a later event reported wins; a field it left empty keeps whatever was already known.
    A status never rewinds out of a terminal one — a redelivered `process_started` does not make
    a finished task run again.
    """
    if prior is None:
        return latest
    kept = {name: value for name, value in prior.model_dump().items() if value is not None}
    fresh = {name: value for name, value in latest.model_dump().items() if value is not None}
    merged = {**kept, **fresh}
    if prior.status in _TERMINAL_STATUS and latest.status not in _TERMINAL_STATUS:
        merged["status"] = prior.status
        merged["exit"] = prior.exit
    return Attempt.model_validate(merged)


def fold(state: RunState, event: RunEvent) -> RunState:
    if event.seq <= state.last_seq:
        return state

    tasks = dict(state.tasks)
    if (tr := event.trace) is not None:
        prior = tasks.get(tr.task_id)
        attempt = Attempt(
            n=tr.attempt, status=tr.status, exit=tr.exit, at_ms=event.at_ms,
            start_ms=tr.start_ms, complete_ms=tr.complete_ms,
            duration_ms=tr.duration_ms, realtime_ms=tr.realtime_ms,
            cpus=tr.cpus, pct_cpu=tr.pct_cpu,
            memory_bytes=tr.memory_bytes, peak_rss_bytes=tr.peak_rss_bytes,
            rchar=tr.rchar, wchar=tr.wchar,
            read_bytes=tr.read_bytes, write_bytes=tr.write_bytes,
        )
        # Keyed by attempt number, not appended — A176. Three events describe one try, and a
        # redelivered body is a fourth; all four are the same attempt reaching a later status.
        #
        # **Merged, not replaced.** Only `process_completed` carries the resources, so replacing
        # an attempt with a redelivered `process_started` erases them — and the loss is
        # invisible, because an absent field is also what a run without `trace.enabled` looks
        # like. Merging makes the fold converge whatever order bodies arrive in, which is the
        # same property A176 asked of everything else the fold writes.
        by_n = {a.n: a for a in (prior.attempts if prior else ())}
        by_n[attempt.n] = _merge(by_n.get(attempt.n), attempt)
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
    # `max`, not assignment — A176's convergence property caught the difference. A redelivered
    # body carries its ORIGINAL `at_ms`, so overwriting rewinds liveness and a run that has
    # been quiet for an hour can be made to look fresh by an old event arriving twice.
    activity = state.last_activity_ms
    if event.kind in FROM_NEXTFLOW:
        activity = max(event.at_ms, activity) if activity is not None else event.at_ms
    started = started_at is not None

    return state.model_copy(update={
        "run_id": event.run_id or state.run_id,
        "tasks": tasks,
        "counts": _counts(tasks),
        "last_seq": event.seq,
        "last_activity_ms": activity,
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

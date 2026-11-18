"""Fold admitted events into deterministic run, task, and attempt state.

Recorded sequence numbers make replay idempotent, while keyed attempts and derived counts make
freshly sequenced redeliveries converge. Terminal events accumulate as a set, so outcome does
not depend on arrival order and cancellation can retain precedence over its resulting error.
"""

from collections import Counter
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
    matters one layer above admission: the record could be replayed to recover these values,
    but a projection could not.

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

_TERMINAL = {EventKind.COMPLETED, EventKind.ERROR, EventKind.CANCELLED}


_COUNTED = {
    TaskStatus.COMPLETED: "succeeded",
    TaskStatus.FAILED: "failed",
    TaskStatus.CACHED: "cached",
    TaskStatus.RUNNING: "running",
    TaskStatus.SUBMITTED: "submitted",
}


def counts_of(statuses: Mapping[TaskStatus, int]) -> Counts:
    """The counts for this many tasks in each status: one mapping from status to count, used
    by `_counts`, `_shifted` and a projection that counts its tasks in SQL (#566)."""
    tally = dict.fromkeys(_COUNTED.values(), 0)
    for status, n in statuses.items():
        if (field := _COUNTED.get(TaskStatus(status))) is not None:
            tally[field] += n
    return Counts(**tally)


def _counts(tasks: Mapping[int, TaskState]) -> Counts:
    return counts_of(Counter(t.status for t in tasks.values()))


def _shifted(counts: Counts, was: TaskStatus | None, now: TaskStatus) -> Counts:
    """`counts` with one task moved from `was` (absent: a new task) to `now`: what `_counts`
    would answer for the changed tasks, without recounting all of them (#565). A recount on
    every event made a replay O(events × tasks); `restore` still recounts, once."""
    if was is now:
        return counts
    moved = counts.model_dump()
    if (field := _COUNTED.get(was)) is not None:
        moved[field] -= 1
    if (field := _COUNTED.get(now)) is not None:
        moved[field] += 1
    return Counts(**moved)


def _phase(seen: frozenset[EventKind], succeeded: bool | None, started: bool) -> RunPhase:
    # **First, and above `ERROR`.** Cancelling a run makes Nextflow exit non-zero, so a cancel
    # and the error it causes arrive together — and *a person stopped this* is the truer
    # sentence. Reading it as `failed` would send somebody looking for a defect that is a
    # decision.
    if EventKind.CANCELLED in seen:
        return RunPhase.CANCELLED
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


def _task_after(prior: TaskState | None, event: RunEvent) -> TaskState:
    """The task `event.trace` describes, once the event is folded into `prior`."""
    tr = event.trace
    if tr is None or (prior is not None and prior.task_id != tr.task_id):
        raise ValueError("a task folds only the event that describes it")
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
    return TaskState(
        task_id=tr.task_id, process=tr.process, status=tr.status,
        attempts=attempts, latest_exit=tr.exit,
        first_seen_ms=prior.first_seen_ms if prior else event.at_ms,
        last_change_ms=event.at_ms,
    )


def _advanced(state: RunState, event: RunEvent, tasks: Mapping[int, TaskState],
              counts: Counts) -> RunState:
    """The run's own facts after `event`, around tasks and counts already folded."""
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
        "counts": counts,
        "last_seq": event.seq,
        "last_activity_ms": activity,
        "terminal_seen": seen,
        "run_succeeded": succeeded,
        "started_at_ms": started_at,
        "ended_at_ms": event.at_ms if seen and not state.ended_at_ms else state.ended_at_ms,
        "phase": _phase(seen, succeeded, started),
    })


def fold(state: RunState, event: RunEvent) -> RunState:
    if event.seq <= state.last_seq:
        return state
    tasks = dict(state.tasks)
    counts = state.counts
    if (tr := event.trace) is not None:
        prior = tasks.get(tr.task_id)
        tasks[tr.task_id] = _task_after(prior, event)
        counts = _shifted(counts, prior.status if prior else None, tr.status)
    return _advanced(state, event, tasks, counts)


def fold_task(state: RunState, task: TaskState | None,
              event: RunEvent) -> tuple[RunState, TaskState | None]:
    """`fold` for a caller that holds the run's facts and only the task `event` touches
    (#566): ingest, which would otherwise load every task to fold one event.

    `task` is that task's state before the event (`None` when it is new, or when the event
    describes none). `state.tasks` is neither read nor changed; `state.counts` must be the
    whole run's. Returns the run's facts and the task after the event, equal to what `fold`
    gives for them — `test_folding_one_task_is_folding_the_run` holds the two together, and
    they share every line that decides anything."""
    if event.seq <= state.last_seq:
        return state, task
    counts = state.counts
    if (tr := event.trace) is not None:
        counts = _shifted(counts, task.status if task else None, tr.status)
        task = _task_after(task, event)
    return _advanced(state, event, state.tasks, counts), task


def restore(
    *,
    run_id: str,
    tasks: Mapping[int, TaskState],
    last_seq: int,
    last_activity_ms: int | None,
    started_at_ms: int | None,
    ended_at_ms: int | None,
    terminal_seen: frozenset[EventKind],
    run_succeeded: bool | None,
) -> RunState:
    """A run's state rebuilt from the facts a projection stores, so the fold can go on from it
    without replaying the record (issue 282). **Counts and phase are not inputs**: they are
    worked out here as `fold` works them out, so the projection cannot store a second answer.
    `restore(<a state's own facts>) == state` for every state `replay` produces."""
    return RunState(
        run_id=run_id,
        tasks=dict(tasks),
        counts=_counts(tasks),
        started_at_ms=started_at_ms,
        ended_at_ms=ended_at_ms,
        last_seq=last_seq,
        last_activity_ms=last_activity_ms,
        terminal_seen=frozenset(terminal_seen),
        run_succeeded=run_succeeded,
        phase=_phase(frozenset(terminal_seen), run_succeeded, started_at_ms is not None),
    )


def replay(events: Iterable[RunEvent]) -> RunState:
    state = EMPTY
    for event in events:
        state = fold(state, event)
    return state

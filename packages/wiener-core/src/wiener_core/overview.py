"""§9.3's four comparisons, per process — one row for every process the artifact declares.

**Comparisons rather than readings**: a bare `peak_rss` means nothing without what was asked
for, and over-allocation is the commonest waste in bioinformatics. Four pairs —

| | asked | got | why it matters |
|---|---|---|---|
| memory | `memory` | `peak_rss` | the OOM story *before* the OOM |
| cpu | `cpus` | `%cpu` | 8 cores requested, 100% of one used |
| time | `duration` | `realtime` | the difference is queue wait |
| i/o | — | `read_bytes` · `write_bytes` | which step actually moves the data |

**Per process, not per task, and the maximum is kept.** A 400-task run has 400 traces and
nobody reads 400 rows — and the maximum is what kills a run where the mean is what hides it.

**A number nothing reported is `None`, never zero.** A run launched without `trace.enabled`
reports no resources at all (§4.3 finding 6), and a zero would read as *this task used no
memory*, which is a lie about a real number that a reader cannot tell from a true one.

**The declared processes come from the artifact, and a row exists before the run reaches it.**
That is what lets this be the front door rather than a log: the table's length is known before
the first event, so it does not grow as the run discovers work.
"""

from collections.abc import Sequence

from pydantic import BaseModel, ConfigDict

from wiener_core.events import TaskStatus
from wiener_core.state import RunState, TaskState


class ProcessRow(BaseModel):
    model_config = ConfigDict(frozen=True)

    process: str
    declared: bool = False
    """In the artifact. **False means the run ran something the pipeline does not describe** —
    which happens when an artifact cannot be read (A192), and must not be silently hidden."""
    reached: bool = False
    """Any task of it has been seen. `declared and not reached` is the not-started row."""

    tasks: int = 0
    done: int = 0
    running: int = 0
    failed: int = 0
    cached: int = 0
    attempts_max: int = 1

    memory_asked_bytes: int | None = None
    memory_peak_bytes: int | None = None
    cpus_asked: int | None = None
    cpu_used_pct: float | None = None
    realtime_ms: int | None = None
    queue_wait_ms: int | None = None
    read_bytes: int | None = None
    write_bytes: int | None = None

    @property
    def reported_resources(self) -> bool:
        """Whether this run was launched with `trace.enabled`. The panel says so rather than
        drawing four empty bars, because an absent number and a zero are different facts."""
        return self.memory_peak_bytes is not None or self.cpu_used_pct is not None


class Overview(BaseModel):
    model_config = ConfigDict(frozen=True)

    rows: tuple[ProcessRow, ...] = ()
    steps_declared: int = 0
    """From the artifact. **The only honest denominator** — §5: Nextflow discovers tasks as
    channels emit, so a task-level percentage is a number nobody can source."""
    steps_finished: int = 0
    """Declared steps whose every task is done. **Not monotonic, and it cannot be** — Nextflow
    discovers tasks as channels emit, so a step with three tasks done is finished until a
    fourth is submitted. The interface must not draw this as a bar that only fills; the
    alternative, remembering that a step was once finished, is monotonic and false."""


_DONE = {TaskStatus.COMPLETED, TaskStatus.CACHED}
_FAILED = {TaskStatus.FAILED, TaskStatus.ABORTED}
_RUNNING = {TaskStatus.RUNNING, TaskStatus.SUBMITTED}


def _worst(values: list[int | float | None]) -> int | float | None:
    present = [value for value in values if value is not None]
    return max(present) if present else None


def _row(process: str, declared: bool, tasks: list[TaskState]) -> ProcessRow:
    attempts = [a for task in tasks for a in task.attempts]
    return ProcessRow(
        process=process,
        declared=declared,
        reached=bool(tasks),
        tasks=len(tasks),
        done=sum(1 for t in tasks if t.status in _DONE),
        cached=sum(1 for t in tasks if t.status == TaskStatus.CACHED),
        failed=sum(1 for t in tasks if t.status in _FAILED),
        running=sum(1 for t in tasks if t.status in _RUNNING),
        attempts_max=max((len(t.attempts) for t in tasks), default=1),
        memory_asked_bytes=_worst([a.memory_bytes for a in attempts]),
        memory_peak_bytes=_worst([a.peak_rss_bytes for a in attempts]),
        cpus_asked=_worst([a.cpus for a in attempts]),
        cpu_used_pct=_worst([a.pct_cpu for a in attempts]),
        realtime_ms=_worst([a.realtime_ms for a in attempts]),
        queue_wait_ms=_worst([
            a.duration_ms - a.realtime_ms
            for a in attempts if a.duration_ms is not None and a.realtime_ms is not None
        ]),
        read_bytes=_worst([a.read_bytes for a in attempts]),
        write_bytes=_worst([a.write_bytes for a in attempts]),
    )


def overview(state: RunState, declared: Sequence[str]) -> Overview:
    """Per process, worst case kept, in the order the artifact declares.

    **Declared order, not sorted.** The pipeline's shape is what a reader is orienting by, and
    a table that reorders itself as a run progresses cannot be scanned twice.
    """
    by_process: dict[str, list[TaskState]] = {}
    for task in state.tasks.values():
        by_process.setdefault(task.process, []).append(task)

    # Declared first, in order; then anything the run ran that the artifact does not describe.
    named = set(declared)
    names = list(declared) + [p for p in by_process if p not in named]

    rows = tuple(_row(name, name in named, by_process.get(name, [])) for name in names)
    # **Every task done, not merely no task running** — found at Checkpoint 1 against a real
    # failed run. `reached and running == 0 and tasks > 0` counts a process whose tasks all
    # FAILED, so `0d3a4e3d` reported 2 of 5 finished with zero successes and §5's one honest
    # bar advanced on failure. `done` is COMPLETED or CACHED, so `done == tasks` is the whole
    # rule: nothing running, nothing failed, and at least one task actually ran.
    finished = sum(
        1 for row in rows
        if row.declared and row.tasks > 0 and row.done == row.tasks
    )
    return Overview(rows=rows, steps_declared=len(declared), steps_finished=finished)

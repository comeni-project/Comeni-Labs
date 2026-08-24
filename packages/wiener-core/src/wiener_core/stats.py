"""§9.3's four comparisons, per process.

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
"""

from pydantic import BaseModel, ConfigDict

from wiener_core.state import RunState


class ProcessStats(BaseModel):
    model_config = ConfigDict(frozen=True)

    process: str
    tasks: int

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


def _worst(values: list[int | float | None]) -> int | float | None:
    present = [value for value in values if value is not None]
    return max(present) if present else None


def stats(state: RunState) -> list[ProcessStats]:
    """The four comparisons, worst case per process, ordered by what took longest."""
    by_process: dict[str, list] = {}
    for task in state.tasks.values():
        by_process.setdefault(task.process, []).extend(task.attempts)

    rows = [
        ProcessStats(
            process=process,
            tasks=sum(1 for task in state.tasks.values() if task.process == process),
            memory_asked_bytes=_worst([a.memory_bytes for a in attempts]),
            memory_peak_bytes=_worst([a.peak_rss_bytes for a in attempts]),
            cpus_asked=_worst([a.cpus for a in attempts]),
            cpu_used_pct=_worst([a.pct_cpu for a in attempts]),
            realtime_ms=_worst([a.realtime_ms for a in attempts]),
            queue_wait_ms=_worst([
                (a.duration_ms - a.realtime_ms)
                if a.duration_ms is not None and a.realtime_ms is not None else None
                for a in attempts
            ]),
            read_bytes=_worst([a.read_bytes for a in attempts]),
            write_bytes=_worst([a.write_bytes for a in attempts]),
        )
        for process, attempts in by_process.items()
    ]
    return sorted(rows, key=lambda row: row.realtime_ms or 0, reverse=True)

"""What Nextflow sends, and the subset Wiener agrees to keep.

**Mendel declares what may leave; Wiener declares what may enter.** `admit()` is the exact
mirror of `tests/test_egress.py` — an allowlist rather than a blocklist, because a blocklist
can only forbid what somebody named. `docs/design/wiener.md` §4.4.

The fields marked `LAB_STRING` are the ones a real run fills with a laboratory's own words:
`script` holds the command including file names, `workdir` is a path, `name` and `tag` carry
the sample tag, and `parameters` is where `--input samplesheet.csv` lands. §4.3 finding 4 is
why that marking exists on the type rather than in a reviewer's head — **the dangerous fields
are structured**, so "structured fields only" was never a privacy guarantee.
"""

from datetime import datetime
from enum import StrEnum
from typing import Annotated, Any, Final, final

from comeni_core.diagnostics import coded
from pydantic import BaseModel, ConfigDict, Field


@final
class LabString:
    """Marks a field a laboratory's own words reach. §10.2's redactor filters on this, and §8
    forbids one becoming a span attribute.

    A sentinel **type** rather than a bare `"lab-string"` — A182. The marking is load-bearing:
    §10.2's claim is that a marked field added later *cannot* be missed, because the totality
    test fails rather than the data leaking. A string is spellable by accident and collides
    with any other `Annotated[str, "lab-string"]`; an instance of a private class is neither.

    It is deliberately **not** `comeni_core.spell.Mark` — widening that enum pulls in the
    egress accounting invariant 14 keeps, for a marking that never crosses a Mendel door.
    """


LAB_STRING: Final = LabString()


class EventKind(StrEnum):
    STARTED = "started"
    PROCESS_SUBMITTED = "process_submitted"
    PROCESS_STARTED = "process_started"
    PROCESS_COMPLETED = "process_completed"
    COMPLETED = "completed"
    ERROR = "error"
    HEARTBEAT = "heartbeat"
    """**Wiener's own, not Nextflow's** — §6.1. `wiener-core` may not read a clock, so the
    passage of time reaches the fold as an event that `wiener-api`'s timer appends. It is what
    `LOST` is detected by and what §10.1's cheap standing brief is woken by."""

    CANCELLED = "cancelled"
    """**Wiener's own too, and for the same reason `HEARTBEAT` is** — Plan 6 phase 1.

    A person cancelling a run is not something Nextflow emits, so a cancel could either be
    written straight onto the row or admitted as an event. It is an event, because §7.1 is
    *"`run_event` is the source of truth and everything else is a projection"* — and a phase
    written only on the row makes a replayed run **forget it was cancelled**, which is the one
    thing the audit exists to remember.

    It also means the console shows the cancel in order, beside the tasks that were running
    when it happened, without anything being taught to merge two sources."""


FROM_NEXTFLOW: Final = frozenset(EventKind) - {EventKind.HEARTBEAT}
"""What an external party may author. Smaller than `EventKind` on purpose — A175."""


class TaskStatus(StrEnum):
    SUBMITTED = "SUBMITTED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    ABORTED = "ABORTED"
    CACHED = "CACHED"


class ErrorAction(StrEnum):
    RETRY = "RETRY"
    TERMINATE = "TERMINATE"
    IGNORE = "IGNORE"
    FINISH = "FINISH"


class TaskTrace(BaseModel):
    """One task as Nextflow reported it. Anything not declared here is dropped.

    **`populate_by_name` is load-bearing, not tidiness.** Nextflow sends `%cpu`, `start` and
    `peak_rss`; `model_dump()` writes `pct_cpu`, `start_ms` and `peak_rss_bytes`; and
    `run_event.payload` holds the dump. Without this, reading the record back validated by alias
    only, so **every aliased field came back `None`** and `extra="ignore"` swallowed the
    evidence — §7.1's *"run_event is the source of truth and everything else is a projection"*
    was false for nine fields of fifteen.

    It hid well: `cpus`, `read_bytes` and `write_bytes` have no alias, so a span carried three
    of the nine and looked merely sparse. Found by printing the spans at a checkpoint and asking
    why one number was missing.
    """

    model_config = ConfigDict(frozen=True, extra="ignore", populate_by_name=True)

    task_id: int
    process: str
    name: Annotated[str, LAB_STRING]
    status: TaskStatus
    exit: int | None = None
    attempt: int = 1
    error_action: ErrorAction | None = None
    submit_ms: int | None = Field(default=None, alias="submit")
    start_ms: int | None = Field(default=None, alias="start")
    complete_ms: int | None = Field(default=None, alias="complete")
    duration_ms: int | None = Field(default=None, alias="duration")
    realtime_ms: int | None = Field(default=None, alias="realtime")
    cpus: int | None = None
    memory_bytes: int | None = Field(default=None, alias="memory")
    hash: str | None = None
    script: Annotated[str, LAB_STRING] | None = None
    workdir: Annotated[str, LAB_STRING] | None = None
    tag: Annotated[str, LAB_STRING] | None = None

    # --- what `trace.enabled` adds, and what §9 draws ----------------------------------
    #
    # **Kept because the record cannot be back-filled.** §9.4 says admitting these is "a line
    # in an allowlist and a test, rather than a subsystem", and it reads like display work
    # deferrable to phase 3 — it is not. `run_event` is the source of truth, so a run recorded
    # without them has no resource history *ever*, and the dashboard that phase 3 builds would
    # open on months of runs it can say nothing about.
    #
    # Confirmed against a real capture on 2026-08-24 rather than assumed: with
    # `trace.enabled = true` the weblog body carries all of these, and `admit()` was dropping
    # every one. §9.3's four comparisons are asked-versus-got pairs, and both halves are here —
    # `cpus` against `%cpu`, `memory` against `peak_rss`, `duration` against `realtime`.
    pct_cpu: float | None = Field(default=None, alias="%cpu")
    pct_mem: float | None = Field(default=None, alias="%mem")
    rss_bytes: int | None = Field(default=None, alias="rss")
    vmem_bytes: int | None = Field(default=None, alias="vmem")
    peak_rss_bytes: int | None = Field(default=None, alias="peak_rss")
    peak_vmem_bytes: int | None = Field(default=None, alias="peak_vmem")
    rchar: int | None = None
    wchar: int | None = None
    read_bytes: int | None = None
    write_bytes: int | None = None
    syscr: int | None = None
    syscw: int | None = None
    vol_ctxt: int | None = None
    inv_ctxt: int | None = None
    cpu_model: str | None = None
    """Not a lab string: the model of the CPU the site owns, which says nothing about a
    sample. `container`, `queue` and `native_id` are the same class and are deliberately still
    dropped — nothing reads them yet, and §4.4's rule is that a field arrives when something
    needs it, in a diff."""


class RunManifest(BaseModel):
    """The `metadata` on `started` and `completed`, reduced to what Wiener uses."""

    model_config = ConfigDict(frozen=True, extra="ignore", populate_by_name=True)

    success: bool | None = None
    exit_status: int | None = None
    succeeded: int = 0
    failed: int = 0
    cached: int = 0
    ignored: int = 0
    report: Annotated[str, LAB_STRING] | None = None


class RunEvent(BaseModel):
    """What `admit()` produces, and the only thing `fold()` ever sees."""

    model_config = ConfigDict(frozen=True)

    kind: EventKind
    run_id: str
    at_ms: int
    seq: int
    trace: TaskTrace | None = None
    manifest: RunManifest | None = None


NO_EXIT: Final = 2**31 - 1
"""Nextflow's sentinel for *this task has no exit code yet* — `Integer.MAX_VALUE`.

**It is not an exit code and must not be stored as one.** A task that is submitted or running
carries it, and left alone it reaches a dashboard as `exit_code 2147483647` grouped beside the
real 0s and 1s. §4.4's job is deciding what may enter; a sentinel that means *absent* enters as
absent.

Found on 2026-08-24 by grouping real spans by exit code and reading the answer.
"""


def _at_ms(body: dict[str, Any]) -> int:
    return int(datetime.fromisoformat(body["utcTime"].replace("Z", "+00:00")).timestamp() * 1000)


def admit(payload: dict[str, Any], run_id: str, seq: int) -> RunEvent:
    """Convert one weblog body into Wiener's own closed types, dropping the rest."""
    raw = payload.get("event")
    try:
        kind = EventKind(raw)
    except ValueError:
        raise ValueError(coded("MW0001", f"unknown event kind {raw!r}")) from None
    if kind not in FROM_NEXTFLOW:
        raise ValueError(coded("MW0002", f"{kind} is authored by Wiener, not posted to it"))

    trace = TaskTrace.model_validate(payload["trace"]) if payload.get("trace") else None
    if trace is not None and trace.exit == NO_EXIT:
        trace = trace.model_copy(update={"exit": None})

    manifest = None
    if (meta := payload.get("metadata")) is not None:
        wf = meta.get("workflow", {})
        stats = wf.get("stats", {}) or {}
        manifest = RunManifest(
            success=wf.get("success"),
            exit_status=wf.get("exitStatus"),
            succeeded=stats.get("succeededCount", 0),
            failed=stats.get("failedCount", 0),
            cached=stats.get("cachedCount", 0),
            ignored=stats.get("ignoredCount", 0),
            report=wf.get("errorReport"),
        )

    return RunEvent(kind=kind, run_id=run_id, at_ms=_at_ms(payload), seq=seq,
                    trace=trace, manifest=manifest)


def heartbeat(run_id: str, at_ms: int, seq: int) -> RunEvent:
    """The timer speaking. The **only** way a `HEARTBEAT` is constructed — `admit()` refuses
    one from the network, so this function is the whole of that kind's provenance."""
    return RunEvent(kind=EventKind.HEARTBEAT, run_id=run_id, at_ms=at_ms, seq=seq)

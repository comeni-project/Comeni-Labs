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
    """One task as Nextflow reported it. Anything not declared here is dropped."""

    model_config = ConfigDict(frozen=True, extra="ignore")

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


class RunManifest(BaseModel):
    """The `metadata` on `started` and `completed`, reduced to what Wiener uses."""

    model_config = ConfigDict(frozen=True, extra="ignore")

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

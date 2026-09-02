"""A run, as OpenTelemetry sees it. Pure — the SDK is a network client and lives next door.

`docs/notes/specs/2026-08-24-telemetry-for-a-run.md` is where every name below comes from, and the
short version is that **there is no batch-job convention** — the issue asking for one has been
open since 2021 — while the **CI/CD** conventions fit almost exactly: a pipeline that runs named
tasks which succeed or fail is the same shape as a Nextflow run.

**This module builds `Span`s, not SDK spans.** `wiener-api` translates and sends. That split is
§3.1's whole payoff: the mapping replays, and a three-day run maps in milliseconds because a
span may be backdated.
"""

from enum import StrEnum
from typing import Final

from pydantic import BaseModel, ConfigDict

from wiener_core.events import EventKind
from wiener_core.state import Attempt, RunPhase, RunState, TaskStatus


class SpanKind(StrEnum):
    SERVER = "SERVER"
    INTERNAL = "INTERNAL"


class Span(BaseModel):
    """One span, with its timestamps already decided.

    `start_ns` and `end_ns` are nanoseconds since the epoch and are **the events' own**, not the
    clock's — which is what lets `spans()` be pure and a finished run be mapped after the fact.
    Nothing in OpenTelemetry rejects a timestamp in the past.
    """

    model_config = ConfigDict(frozen=True)

    name: str
    kind: SpanKind
    span_id: str
    parent: str | None = None
    start_ns: int
    end_ns: int | None = None
    attributes: dict[str, str | int | float | bool] = {}


_RESULT: Final[dict[RunPhase, str]] = {
    RunPhase.SUCCEEDED: "success",
    RunPhase.FAILED: "failure",
    RunPhase.CANCELLED: "cancellation",
    RunPhase.LOST: "timeout",
}
"""§1.4. `LOST -> timeout` is the arguable one: a run Wiener stopped hearing from did not fail —
nothing said so — and did not error, because Wiener did not break. It ran out of time to speak.
`error` is reserved for Wiener breaking, which is what makes both values worth having."""

_TASK_RESULT: Final[dict[TaskStatus, str]] = {
    TaskStatus.COMPLETED: "success",
    TaskStatus.FAILED: "failure",
    TaskStatus.CACHED: "skip",
    TaskStatus.ABORTED: "cancellation",
}
"""`CACHED -> skip` because the task did not run, which is exactly what `skip` says."""


def pipeline_name(pipeline) -> str:
    """What `cicd.pipeline.name` carries — **A190, decided 2026-08-24.**

    The convention makes it Required on the resource, the run span and three of the five
    metrics, and `Pipeline` has no name field. Derived from the goal, so it is *stable across
    rebuilds*: every board groups by this, and using the artifact digest would start a new
    series on every change, which makes "is the spine getting slower" unanswerable across
    exactly the change you want to measure.

    The cost, stated: two different pipelines producing the same thing collide. The fix if that
    bites is a name the submitter supplies **defaulting to this**, which is an added field and
    not a changed one — so nothing here has to move.
    """
    if pipeline is None:
        return "unknown"
    want = "+".join(sorted(pipeline.goal.want)) or "unknown"
    return want


def _span_id(*parts: object) -> str:
    """Derived, never random. A random id makes a golden file impossible and replay
    non-identical — and §6's claim is that the same events produce the same everything.

    **A readable composite rather than a hash**, because the purity guard refused `hashlib`
    here and was right to: OpenTelemetry's ids are eight bytes on the wire, and meeting a wire
    format is the exporter's job. This says *which* span; `wiener-api` says what it looks like
    to a backend. The pure half keeping a legible id is a bonus — a golden file reads.
    """
    return ".".join(str(p) for p in parts)


def _attempt_window(attempt: Attempt) -> tuple[int, int | None]:
    start = attempt.start_ms or attempt.at_ms
    return start * 1_000_000, (attempt.complete_ms * 1_000_000 if attempt.complete_ms else None)


def spans(state: RunState, pipeline=None, run_url: str | None = None) -> list[Span]:
    """The run as one `SERVER` span with an `INTERNAL` child per attempt.

    **Per attempt, not per task** — §8: a retry that succeeded after two failures should look
    like three spans, not one, and `Attempt` carries its own window precisely so that they can.
    """
    if state.started_at_ms is None:
        return []

    name = pipeline_name(pipeline)
    run_id = _span_id(state.run_id)
    root = Span(
        name=f"RUN {name}",
        kind=SpanKind.SERVER,
        span_id=run_id,
        start_ns=state.started_at_ms * 1_000_000,
        end_ns=(state.ended_at_ms * 1_000_000) if state.ended_at_ms else None,
        attributes={
            "cicd.pipeline.name": name,
            "cicd.pipeline.run.id": state.run_id,
            "cicd.pipeline.action.name": "RUN",
            **({"cicd.pipeline.run.url.full": run_url} if run_url else {}),
            **({"cicd.pipeline.result": _RESULT[state.phase]} if state.phase in _RESULT else {}),
            **({"error.type": _error_type(state)} if _failed(state) else {}),
        },
    )

    made = [root]
    for task in sorted(state.tasks.values(), key=lambda t: t.task_id):
        for attempt in task.attempts:
            start_ns, end_ns = _attempt_window(attempt)
            made.append(Span(
                name=task.process,
                kind=SpanKind.INTERNAL,
                span_id=_span_id(state.run_id, task.task_id, attempt.n),
                parent=run_id,
                start_ns=start_ns,
                end_ns=end_ns,
                attributes=_task_attributes(state, task, attempt, run_url),
            ))
    return made


def _failed(state: RunState) -> bool:
    return state.phase in (RunPhase.FAILED, RunPhase.LOST)


def _error_type(state: RunState) -> str:
    """Conditionally Required when the result is `failure` or `error`. Derived from what the
    run did, never from message text — the same rule §10.1 puts on a failure signature."""
    if state.phase is RunPhase.LOST:
        return "no_events"
    if EventKind.ERROR in state.terminal_seen:
        return "run_error"
    return "task_failed"


def _task_attributes(state, task, attempt, run_url):
    """The CI/CD names, then `process.exit.code`, then the six that have no convention."""
    attributes: dict[str, str | int | float | bool] = {
        "cicd.pipeline.task.name": task.process,
        "cicd.pipeline.task.run.id": f"{task.task_id}.{attempt.n}",
        "cicd.pipeline.task.run.url.full": f"{run_url}#task-{task.task_id}" if run_url else "",
        "wiener.task.attempt": attempt.n,
        "wiener.task.cached": attempt.status is TaskStatus.CACHED,
    }
    if attempt.status in _TASK_RESULT:
        attributes["cicd.pipeline.task.run.result"] = _TASK_RESULT[attempt.status]
    if attempt.status in (TaskStatus.FAILED, TaskStatus.ABORTED):
        attributes["error.type"] = f"exit_{attempt.exit}" if attempt.exit is not None else "failed"
    if attempt.exit is not None:
        attributes["process.exit.code"] = attempt.exit

    # The six with no standard name — §2 of the note. **Absent, never zero**, when the run was
    # launched without `trace.enabled`: a zero would read as "this task used no memory".
    optional = {
        "wiener.task.cpus_asked": attempt.cpus,
        "wiener.task.cpu_used_pct": attempt.pct_cpu,
        "wiener.task.memory_asked_bytes": attempt.memory_bytes,
        "wiener.task.memory_peak_bytes": attempt.peak_rss_bytes,
        "wiener.task.read_bytes": attempt.read_bytes,
        "wiener.task.write_bytes": attempt.write_bytes,
    }
    if attempt.duration_ms is not None and attempt.realtime_ms is not None:
        optional["wiener.task.queue_wait_ms"] = attempt.duration_ms - attempt.realtime_ms
    attributes.update({k: v for k, v in optional.items() if v is not None})
    return attributes

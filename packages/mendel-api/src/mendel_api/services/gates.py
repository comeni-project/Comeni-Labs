"""Running a gate, and remembering that it ran.

**A gate is not a run.** `docs/design/execution-boundary.md` §3: a gate runs Mendel's own
artifact against data somebody else published, takes no samplesheet, and is bounded. A *run*
takes a laboratory's data and belongs to Wiener. Nothing in this module accepts a path from a
client — the directory is derived from an opaque draft id, exactly as `drafts._output_root`
derives its destination, and for the same reason: invariant 15.

**The flow is `_publish_verb`'s, not a second one.** `mendel_compiler/cli/artifact_verbs.py`
already emits, materialises stub inputs, gates and stamps in that order, and every step of it
earned itself — A47, A49, A104. This re-uses the pieces rather than reordering them.

**`_run` and `_directory` are seams, not indirection**, for the reason `services/drafts.py`
records about its own: these tests need Postgres and Nextflow, CI has neither, and a rule only
a developer machine can check is a rule nobody checks.
"""

import asyncio
import secrets
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from pathlib import Path

from comeni_core.artifact.gates import Gate
from comeni_core.diagnostics import coded
from mendel_compiler import pipeline_file
from mendel_compiler.emit import emit, emit_config, entry_params
from mendel_compiler.gates import LONGEST, GateResult, materialise_stub_data, run_gate
from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError

from mendel_api.db import session_scope
from mendel_api.models import GateRun
from mendel_api.settings import settings


class GateState(StrEnum):
    """Where a gate's row is. Queued and running are live (`LIVE`); passed and failed end it."""

    QUEUED = "queued"
    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"


LIVE = (GateState.QUEUED, GateState.RUNNING)
"""The states a gate can still move out of. The browser polls while it is one of these. A draft
has at most one gate in them (`GateRun`'s `ix_gate_run_one_live`)."""

MARGIN = 300
"""Seconds allowed around Nextflow for emitting the files and stamping the artifact."""
JOB_TIMEOUT = LONGEST + MARGIN
"""What the worker allows a gate job: the longest gate, and the work around it (issue 278)."""
LOST_AFTER = JOB_TIMEOUT + MARGIN
"""How long after it was asked for a gate still live is lost, not slow: past its job's own
limit and a queue's wait. Every gate has a hard limit, so time alone can tell the two apart."""

BUSY = "a gate is already running on this pipeline"
FAILED = "the gate could not run to a result"
LOST = "this gate was lost: no result came back within its time limit"


class GateView(BaseModel):
    """What the browser polls.

    No path and no host detail — the same restraint the drafts routes take, for the same
    reason. `output` is a tool's own text and is shown to the person who asked; see
    `models.GateRun` for why it must not travel any further than that.
    """

    id: str
    gate: Gate
    state: str
    output: str
    queued_at: datetime
    finished_at: datetime | None


def _directory(draft_id: str) -> Path:
    """The destination seam. Server-chosen, never client-supplied — invariant 15."""
    return settings.draft_root / draft_id


def _run(gate: Gate, directory: Path) -> GateResult:
    """The subprocess seam, so a test can stub Nextflow without one installed."""
    return run_gate(gate, directory)


def request(draft_id: str, gate: Gate, who: str) -> str:
    """Record the ask, and return the run id.

    **Enqueueing is the route's job.** A service that reached Redis would make every test that
    touches a gate need one, and the split is the same one `drafts.create` already makes.
    """
    run_id = secrets.token_hex(16)
    try:
        with session_scope() as session:
            live = (
                session.query(GateRun)
                .filter(GateRun.draft_id == draft_id, GateRun.state.in_(LIVE))
                .first()
            )
            if live is not None:
                raise ValueError(coded("MI0003", BUSY))
            session.add(
                GateRun(
                    id=run_id,
                    draft_id=draft_id,
                    who=who,
                    gate=gate.value,
                    state=GateState.QUEUED,
                    output="",
                    queued_at=datetime.now(UTC),
                )
            )
    except IntegrityError:  # two asks raced past the check; the index refused the second
        raise ValueError(coded("MI0003", BUSY)) from None
    return run_id


def of(directory: Path, gate: Gate) -> GateResult:
    """Emit, materialise, gate. The pure half — no database, so it is testable without one.

    **Emission happens here rather than at `keep`.** `keep` writes `pipeline.yml` and the
    modules and nothing else, and the Nextflow is regenerated from the artifact every time —
    which is the property `mendel emit` sells and the reason a gate cannot certify something
    the artifact does not describe.
    """
    target = directory / pipeline_file.FILENAME
    if not target.exists():
        # No f-string: ruff refuses one with no placeholder (F541), and `make check` runs it.
        raise ValueError(coded("MI0001", "there is no pipeline to gate. Keep the draft first."))

    pipeline = pipeline_file.load(target)
    (directory / "main.nf").write_text(emit(pipeline))
    (directory / "nextflow.config").write_text(emit_config(pipeline))
    if gate is Gate.STUB:
        materialise_stub_data(directory, entry_params(pipeline))
    return _run(gate, directory)


async def execute(run_id: str) -> None:
    """The worker's entry point.

    `run_gate` blocks for up to 3600s, so it goes to a thread: an ARQ worker is one event loop,
    and a blocking subprocess in it stops every other job on the queue.
    """
    with session_scope() as session:
        row = session.get(GateRun, run_id)
        if row is None:
            return
        row.state = GateState.RUNNING
        draft_id, gate = row.draft_id, Gate(row.gate)

    try:
        directory = _directory(draft_id)
        result = await asyncio.to_thread(of, directory, gate)
        state, output = (GateState.PASSED if result.passed else GateState.FAILED), result.output
        # **Stamped on the failing path too, and that is not symmetry for its own sake.**
        # `of` regenerated `main.nf` and `nextflow.config`, so leaving the `emitted:` record
        # untouched makes the directory diverge from its own `pipeline.yml` — and the next
        # `mendel emit` refuses with MD0214, blaming the person for a change this gate made.
        # `_publish_verb` stamps on both paths for exactly this reason, with `gate=None` on
        # failure: A4, never leave an artifact stamped with a gate it did not pass.
        pipeline = pipeline_file.load(directory / pipeline_file.FILENAME)
        pipeline_file.stamp(directory, pipeline, gate=result.gate if result.passed else None)
    except ValueError as refusal:  # a coded refusal, e.g. MI0001
        state, output = GateState.FAILED, str(refusal)
    except (Exception, asyncio.CancelledError) as broke:
        # **Every way out lands an end state** (issue 278). Anything else left the row
        # `running` for good; a cancellation (the worker stopping) is recorded, then goes on.
        _finish(run_id, GateState.FAILED, coded("MI0002", f"{FAILED}: {broke!r}"))
        if isinstance(broke, asyncio.CancelledError):
            raise
        return

    _finish(run_id, state, output)


def _finish(run_id: str, state: str, output: str) -> None:
    with session_scope() as session:
        row = session.get(GateRun, run_id)
        if row is not None:
            row.state, row.output = state, output
            row.finished_at = datetime.now(UTC)


def sweep(now: datetime | None = None) -> list[str]:
    """Fail every gate still live `LOST_AFTER` seconds after it was asked for; its ids.

    Its worker died, or the queue lost its job. Left alone it would read as running for ever
    and, through the one-live index, hold its draft's gates up for good (issue 278).
    """
    cutoff = (now or datetime.now(UTC)) - timedelta(seconds=LOST_AFTER)
    with session_scope() as session:
        lost = (
            session.query(GateRun)
            .filter(GateRun.state.in_(LIVE), GateRun.queued_at < cutoff)
            .order_by(GateRun.id)
            .all()
        )
        for row in lost:
            row.state, row.output = GateState.FAILED, coded("MI0004", LOST)
            row.finished_at = datetime.now(UTC)
        return [row.id for row in lost]


def read(run_id: str) -> GateView:
    """Raises `KeyError` for an unknown run; the route maps it to 404."""
    with session_scope() as session:
        row = session.get(GateRun, run_id)
        if row is None:
            raise KeyError(run_id)
        return GateView(
            id=row.id,
            gate=Gate(row.gate),
            state=row.state,
            output=row.output,
            queued_at=row.queued_at,
            finished_at=row.finished_at,
        )

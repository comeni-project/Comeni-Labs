"""The public surface: upload an artifact, submit a run, read what happened.

Every body here is `extra="forbid"`, which is what makes an unexpected field a 422 rather than
a field silently ignored — and the field somebody would try is a path.
"""

import asyncio
import secrets
from datetime import UTC, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Form, HTTPException, UploadFile, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, ConfigDict
from wiener_core.series import Series, series
from wiener_core.signals import signal_of
from wiener_core.state import Attempt

from wiener_api import db, jobs, repository
from wiener_api.models import Run, RunArtifact
from wiener_api.services import launcher, stream
from wiener_api.services.artifacts import (
    declared_holes,
    input_shape,
    pipeline_digest,
    store,
)
from wiener_api.services.projection import state_of
from wiener_api.settings import settings

router = APIRouter(prefix="/api")


class SubmitRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    artifact_id: str
    params: dict[str, str | list[str] | list[dict[str, str]]] = {}
    """The values only the laboratory can supply, and **the artifact is the schema**.

    Mendel emits every value it can justify and `= null` for every value it cannot, so a
    submission fills precisely those nulls — no more, and no fewer. That makes this map
    flexible without being open: `declared_holes()` reads them out of the artifact, so an
    unknown key and a missing one are both refused, for any pipeline, including one Mendel
    never built.

    **Not stored** — §7.1: no table holds a samplesheet. These ride to the launcher as a job
    argument, which is transient by nature and the right lifetime for run data.

    **A value may be a list of rows**, which is a samplesheet composed in the browser: the
    launcher writes it as a CSV into the run's workdir and points the parameter at that file.
    A plain string is passed through unchanged, so a laboratory that already has a samplesheet
    still gives its path — the table editor is a convenience over that, not a gate in front of
    it.
    """
    executor: Literal["local"] = "local"
    """`local` only in W1. k8s and awsbatch are W5, and an enum that accepted them before
    anything had run there would be a lie the API tells its own generated client, which would
    offer them in a dropdown."""


class ArtifactStored(BaseModel):
    artifact_id: str
    digest: str
    size_bytes: int
    declared: list[str] = []
    """The parameters this artifact leaves `null` — what a submission must fill, exactly.

    **Returned here so nobody has to provoke a 422 to find out.** `submit` already refuses with
    `declared`/`missing`/`unknown`, and a client could learn the shape by posting an empty map
    and reading the refusal — which works, and would make an error the documented way to ask a
    question. The moment somebody has uploaded an artifact is the moment they need to know what
    it wants, so it is said then.
    """

    input_form: Literal["direct", "samplesheet"] = "direct"
    """Whether `params.input` is a glob or the path to a samplesheet.

    **The one hole whose name does not say what it wants.** `params.gtf` and `params.gtf_2` are
    two nulls and the run sheet asks for two files with no help from anybody — two same-type
    channels work here by construction. `params.input` is **one null either way**, so without
    this the form asks the same question for a glob and a CSV, somebody answers with the wrong
    kind of thing, and the run fails inside Nextflow minutes later.
    """

    input_columns: list[str] = []
    """The samplesheet's columns, when `input_form` is `samplesheet`. Empty otherwise.

    `sample` is not among them and never will be: it is the identifier column every row
    carries, and it is the browser's to render. These are the *file* columns each sample
    supplies — `reads_1`, `reads_2`, `gtf`."""


class RunAccepted(BaseModel):
    run_id: str


class EventPage(BaseModel):
    """A page of the record, **and where to subscribe from when you have read it**.

    The handoff is the only ordering subtlety in the console (§7.2), so it is a field rather
    than a convention: page from Postgres, then tail from `stream_id`. A browser that has been
    closed for a day does not scroll back through Redis.
    """

    events: list[dict]
    cursor: int
    """The highest `seq` on this page. `-1` when the run has no events yet."""
    stream_id: str
    """The Redis id to resume after. `"0-0"` when the tail is empty or has been trimmed."""


class RunRow(BaseModel):
    id: str
    phase: str
    executor: str
    name: str = ""
    """What a person called the pipeline this run is of — Plan 6 phase 2.

    `""` for an artifact uploaded without one, which every artifact predating this field is and
    every hand-uploaded `mendel build` artifact still may be. The row draws `run <id>` then,
    which is what it drew before the field existed. **Never derived from the digest**: a name
    nobody chose is worse than no name, because a reader cannot tell the two apart.
    """
    submitted_by: str
    submitted_at: datetime
    ended_at: datetime | None = None
    """So the board can say how long a run took without opening it."""
    tasks_done: int = 0
    tasks_seen: int = 0
    """**Tasks, not steps.** `steps_declared` is in the artifact and reading one per row is
    what the board could never afford; how many tasks a run has seen is one GROUP BY over the
    `run_task` projection W2 built."""
    pipeline_digest: str | None = None
    """Which pipeline this run is of — **the join key the browser reads.**

    Mendel reports the same value for every pipeline it holds, computed by the same method over
    the same bytes, so a page can put the two beside each other without either server learning
    the other's identifiers (`wiener.md` §12). `None` for an artifact uploaded before this was
    recorded, which shows as a run without a pipeline rather than as somebody else's.
    """


class RunsPage(BaseModel):
    """A page of the board, and the total the same filters match."""

    runs: list[RunRow]
    total: int


class DayCount(BaseModel):
    day: str
    succeeded: int
    failed: int


class BoardSummary(BaseModel):
    """What the tiles count. **Every field is a tally or a percentile over `run`** — nothing
    here folds an event stream, which is what keeps the board a page and not a job."""

    window_days: int
    failed: int
    running: int
    succeeded: int
    total: int
    median_ms: int | None
    p95_ms: int | None
    days: list[DayCount]
    by_pipeline: dict[str, int] = {}
    """`{pipeline_digest: median_ms}` — what *vs usual* is measured against.

    **A median in the abstract is trivia; the same median beside a run is a judgement.** That is
    `rn-board`'s argument for why this is the board's best number and why it only earned a place
    by moving onto a row.

    A pipeline with fewer than a floor of finished runs is **absent**, not zero: *usually 38m*
    over two runs is one number wearing the clothes of a distribution.

    **A delta needs a finished run.** `-43% vs usual` under a live bar reads as *it was faster*,
    which is the opposite of what it means — a running row says `of ~38m` instead. That rule is
    the page's to keep; this field only supplies the number.
    """


@router.post("/artifacts", status_code=201, operation_id="uploadArtifact",
             summary="Upload a gated pipeline directory")
async def upload_artifact(bundle: UploadFile,
                          name: Annotated[str, Form()] = "") -> ArtifactStored:
    """**`name` is optional and stays optional.** The browser is the courier and it has the
    draft's name to send; `curl -F bundle=@run.zip` has nothing to send and must keep working,
    because an air-gapped site uploading a `mendel build` artifact by hand is invariant 13's
    customer rather than a degraded one. An artifact with no name reads `run <id>`.
    """
    try:
        artifact_id, digest, size = store(await bundle.read())
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    with db.session_scope() as session:
        repository.add(session, settings.lab_id, RunArtifact(
            id=artifact_id, uploaded_by="operator", uploaded_at=datetime.now(UTC),
            digest=digest, size_bytes=size, name=name.strip()[:200],
            # **The column stopped being decoration here.** Declared in W1 and never assigned;
            # it is the key that lets the browser put runs beside pipelines without either
            # server learning the other exists.
            pipeline_digest=pipeline_digest(artifact_id),
        ))
    form, columns = input_shape(artifact_id)
    return ArtifactStored(artifact_id=artifact_id, digest=digest, size_bytes=size,
                          declared=sorted(declared_holes(artifact_id)),
                          input_form=form, input_columns=columns)


@router.post("/runs", status_code=202, operation_id="submitRun", summary="Run a pipeline")
async def submit(body: SubmitRequest) -> RunAccepted:
    run_id = secrets.token_hex(16)
    with db.session_scope() as session:
        if repository.artifact(session, settings.lab_id, body.artifact_id) is None:
            raise HTTPException(status_code=404, detail="no such artifact")

        holes = declared_holes(body.artifact_id)
        if (supplied := set(body.params)) != holes:
            raise HTTPException(status_code=422, detail={
                "message": "a run fills exactly the parameters the artifact leaves null",
                "declared": sorted(holes),
                "unknown": sorted(supplied - holes),
                "missing": sorted(holes - supplied),
            })
        repository.add(session, settings.lab_id, Run(
            id=run_id, artifact_id=body.artifact_id, submitted_by="operator",
            submitted_at=datetime.now(UTC), phase="queued", executor=body.executor,
            ingest_secret=secrets.token_hex(16),
        ))
    await jobs.enqueue("launch_job", run_id, body.params)
    return RunAccepted(run_id=run_id)


@router.get("/runs", operation_id="listRuns", summary="The board")
def board(phase: str | None = None, who: str | None = None, executor: str | None = None,
          after: int = 0, limit: int = 25) -> RunsPage:
    """One page of runs, newest first, with each row's task tally beside it."""
    with db.session_scope() as session:
        page, total = repository.runs_page(session, settings.lab_id, phase=phase, who=who,
                                           executor=executor, after=after, limit=limit)
        counts = repository.task_counts(session, settings.lab_id, [r.id for r in page])
        # One statement for the page, like the tallies above — never one lookup per row.
        digests = repository.pipeline_digests(
            session, settings.lab_id, [r.artifact_id for r in page]
        )
        names = repository.artifact_names(
            session, settings.lab_id, [r.artifact_id for r in page]
        )
        return RunsPage(
            runs=[
                RunRow(id=r.id, phase=r.phase, executor=r.executor,
                       submitted_by=r.submitted_by, submitted_at=r.submitted_at,
                       ended_at=r.ended_at,
                       tasks_done=counts.get(r.id, (0, 0))[0],
                       tasks_seen=counts.get(r.id, (0, 0))[1],
                       pipeline_digest=digests.get(r.artifact_id),
                       name=names.get(r.artifact_id, ""))
                for r in page
            ],
            total=total,
        )


@router.get("/runs/summary", operation_id="readBoardSummary",
            summary="What the board's tiles count")
def board_summary(days: int = 14) -> BoardSummary:
    """**Declared before `/runs/{run_id}`**, or FastAPI matches `summary` as a run id and every
    request 404s on a run nobody asked for. A literal path and a parameterised one that can
    both match are ordered, never disambiguated."""
    with db.session_scope() as session:
        window = max(1, min(days, 90))
        return BoardSummary(
            **repository.board_summary(session, settings.lab_id, days=window),
            by_pipeline=repository.durations_by_pipeline(session, settings.lab_id, days=window),
        )


@router.get("/runs/{run_id}", operation_id="readRun", summary="A run, projected")
def read(run_id: str) -> dict:
    with db.session_scope() as session:
        row = repository.run(session, settings.lab_id, run_id)
        if row is None:
            raise HTTPException(status_code=404)
        state = state_of(session, settings.lab_id, run_id).model_dump(mode="json")
        # **Beside the projection, never inside it.** `RunState` is what `wiener-core` folded
        # from the events, and a name is not in the events — it came off the upload. Folding it
        # in would put a field on the pure type that no event can produce, which is how a
        # projection stops being replayable from its own record.
        state["name"] = repository.artifact_names(
            session, settings.lab_id, [row.artifact_id]
        ).get(row.artifact_id, "")
    return state


@router.get("/runs/{run_id}/events", operation_id="readRunEvents",
            summary="The record, in order")
def events(run_id: str, after: int = -1, limit: int = 200) -> EventPage:
    """What the console reads before it subscribes — §7.2's page-then-tail handoff."""
    with db.session_scope() as session:
        if repository.run(session, settings.lab_id, run_id) is None:
            raise HTTPException(status_code=404)
        rows = repository.events(session, settings.lab_id, run_id)
        page = [row for row in rows if row.seq > after][:limit]

    # Read AFTER the page, so an event that lands between the two is tailed rather than
    # missed. The reverse order drops anything that arrives in the gap.
    return EventPage(
        events=[row.payload for row in page],
        cursor=page[-1].seq if page else after,
        stream_id=stream.last_id(run_id),
    )


class PlacedNode(BaseModel):
    """A node, where the layout put it, and what the run did to it."""

    id: str
    process: str
    x: int
    y: int
    width: int
    height: int
    tier: int
    inputs: list[str] = []
    outputs: list[str] = []
    done: int = 0
    failed: int = 0
    running: int = 0
    total: int = 0
    attempts: int = 1


class DrawnWire(BaseModel):
    from_node: str
    from_port: str
    to_node: str
    to_port: str
    points: list[dict[str, int]]
    active: bool = False
    """**"This edge is active" and nothing more** — §9.2. The consumer is running on what the
    producer wrote, which the event stream supports. A rate would be invented."""
    bytes_moved: int | None = None
    """Only once the consumer finished, because `read_bytes` arrives on `process_completed`."""


class RunGraphOut(BaseModel):
    nodes: list[PlacedNode] = []
    wires: list[DrawnWire] = []
    width: int = 0
    height: int = 0


@router.get("/runs/{run_id}/graph", operation_id="readRunGraph",
            summary="The pipeline's own graph, coloured by what the run did")
def graph(run_id: str) -> RunGraphOut:
    """**Nothing new is computed** — §9.1. The layout is `dag-core`'s, the same one the builder
    draws, and the colouring is the fold's. A graph that cannot disagree with either.
    """
    import dag_core
    from wiener_core.graph import coloured, graph_of

    with db.session_scope() as session:
        if repository.run(session, settings.lab_id, run_id) is None:
            raise HTTPException(status_code=404)
        pipeline = _pipeline_of(session, run_id)
        if pipeline is None:
            raise HTTPException(status_code=404, detail="this run's artifact cannot be read")
        state = state_of(session, settings.lab_id, run_id)

    laid = dag_core.of(graph_of(pipeline))
    run = coloured(pipeline, laid, state)
    by_id = {node.id: node for node in run.nodes}
    ports = {node.id: node for node in graph_of(pipeline).nodes}

    finished = {
        node.id for node in run.nodes if node.total and node.done + node.failed == node.total
    }
    return RunGraphOut(
        nodes=[
            PlacedNode(
                id=placed.id, process=by_id[placed.id].process,
                x=placed.x, y=placed.y, width=placed.width, height=placed.height,
                tier=placed.tier,
                inputs=list(ports[placed.id].inputs), outputs=list(ports[placed.id].outputs),
                done=by_id[placed.id].done, failed=by_id[placed.id].failed,
                running=by_id[placed.id].running, total=by_id[placed.id].total,
                attempts=by_id[placed.id].attempts,
            )
            for placed in laid.nodes
        ],
        wires=[
            DrawnWire(
                from_node=wire.from_node, from_port=wire.from_port,
                to_node=wire.to_node, to_port=wire.to_port,
                points=[{"x": point.x, "y": point.y} for point in wire.points],
                # Active means the consumer is running on what the producer wrote — a fact the
                # stream supports. It stops being active when the consumer stops, not when the
                # data stops flowing, because nothing reports the latter.
                active=(by_id[wire.to_node].running > 0 and wire.from_node in finished),
            )
            for wire in laid.wires
        ],
        width=laid.width, height=laid.height,
    )


def _pipeline_of(session, run_id: str):
    from wiener_api.services.projection import _artifact_pipeline

    return _artifact_pipeline(session, settings.lab_id, run_id)


class ProcessRowOut(BaseModel):
    """One process's row. **Absent is not zero** — a `null` here means the run was launched
    without `trace.enabled` and nothing was reported, or the run has not reached this process
    at all. The interface renders both as a dash and neither as a number.

    Mirrored from `wiener_core.ProcessRow` rather than reused, the way `/graph`'s models are:
    the wire format is `wiener-api`'s to keep stable, and the pure package's types answer to
    the fold. Declared field by field rather than as a `dict`, because the generated client is
    what stops the two halves drifting and a `dict` reaches TypeScript as nothing at all.
    """

    process: str
    declared: bool = False
    reached: bool = False

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


class OverviewOut(BaseModel):
    rows: list[ProcessRowOut] = []
    steps_declared: int = 0
    """**The only honest denominator** — §5. Nextflow discovers tasks as channels emit, so a
    task-level percentage is a number nobody can source; the artifact declares its steps
    before the run starts. `0` means the artifact could not be read, and the bar draws
    nothing rather than dividing by it."""
    steps_finished: int = 0


@router.get("/runs/{run_id}/overview", operation_id="readOverview",
            summary="One row per process the artifact declares")
def run_overview(run_id: str) -> OverviewOut:
    """**It does not 404 on an unreadable artifact** — A192, and deliberately unlike `/graph`.
    The counts come from the fold and are true whatever happened to the directory; what is lost
    is the declared list, so every row says `declared: false` and the bar has no denominator.
    """
    from wiener_core.overview import overview

    with db.session_scope() as session:
        if repository.run(session, settings.lab_id, run_id) is None:
            raise HTTPException(status_code=404)
        pipeline = _pipeline_of(session, run_id)
        state = state_of(session, settings.lab_id, run_id)

    declared = [step.process for step in pipeline.steps] if pipeline is not None else []
    got = overview(state, declared)
    return OverviewOut(
        rows=[ProcessRowOut(**row.model_dump()) for row in got.rows],
        steps_declared=got.steps_declared,
        steps_finished=got.steps_finished,
    )


class AttemptOut(BaseModel):
    """One try, with what it ASKED FOR beside what it TOUCHED.

    **Both halves, or neither is worth showing.** `peak_rss_bytes` alone says a task touched
    47 GB and leaves *was that a lot?* to the reader; `memory_bytes` is the reservation it was
    given, and the pair is what makes 36 → 48 → 72 a story rather than three numbers.

    Every field is nullable, because a run launched without `trace.enabled` recorded none of
    them — **absent rather than zero** (§4.3 finding 6).
    """

    n: int
    status: str
    exit: int | None = None
    signal: str | None = None
    """`SIGKILL` for 137 — the 128+n convention and nothing else.

    **Not a verdict.** *The OOM killer did it* is the sentence a reader wants under a 137 and
    it is an inference: a preemption, a `kill -9` and a cgroup limit are the same code. §18.1
    says nothing explains a failure until W3, and `wiener_core.signals` holds that line with a
    scan rather than with discipline.
    """
    memory_bytes: int | None = None
    peak_rss_bytes: int | None = None
    realtime_ms: int | None = None


class TaskOut(BaseModel):
    """One task row. `tag` is the laboratory's own word for it — A200 — and it is the only
    field here that a laboratory wrote."""

    task_id: int
    process: str
    status: str
    attempts: int = 1
    latest_exit: int | None = None
    last_change_ms: int = 0

    peak_rss_bytes: int | None = None
    realtime_ms: int | None = None
    pct_cpu: float | None = None
    tag: str | None = None

    history: list[AttemptOut] = []
    """Every attempt, in order — **the column `attempts` could never be.**

    `attempts` is a count, and a count cannot show 36 → 48 → 72 GB. The escalation is the
    whole reason retries are kept as history (§5.1) and it was in the JSON blob and out of
    reach of every reader. It ships on a single-attempt task too: even one try carries asked
    beside touched, which no other field on this row does.
    """


class TasksOut(BaseModel):
    tasks: list[TaskOut] = []
    total: int = 0
    """How many the same filters match, not how many are on this page. A table that says
    *404 more* has to know."""


@router.get("/runs/{run_id}/tasks", operation_id="readTasks",
            summary="A run's tasks, filtered, sorted and paged")
def run_tasks(run_id: str, process: str | None = None, status: str | None = None,
              retried_only: bool = False, attempt: int | None = None,
              tag: str | None = None,
              sort: str = "task_id", after: int = 0, limit: int = 100) -> TasksOut:
    """**A query, never a fold** — A191. `sort` is a closed vocabulary and an unknown value
    falls back to `task_id` rather than reaching the database.

    **`tag` is scoped to this run and there is no endpoint that lists tags.** Answering *how
    did sampleB do* needs only the filter; answering *which samples exist* would be a distinct
    query over lab strings, which is the deployment-wide search A200 refused. The table already
    shows every tag on the page, so a person picks one from what is in front of them.
    """
    with db.session_scope() as session:
        if repository.run(session, settings.lab_id, run_id) is None:
            raise HTTPException(status_code=404)
        filters = {"process": process, "status": status, "retried_only": retried_only,
                   "attempt": attempt, "tag": tag}
        rows = repository.tasks_page(session, settings.lab_id, run_id,
                                     sort=sort, after=after, limit=limit, **filters)
        total = repository.tasks_total(session, settings.lab_id, run_id, **filters)
        tasks = [
            TaskOut(
                task_id=row.task_id, process=row.process, status=row.status,
                attempts=len(row.attempts or []) or 1, latest_exit=row.latest_exit,
                last_change_ms=row.last_change_ms,
                peak_rss_bytes=row.peak_rss_bytes, realtime_ms=row.realtime_ms,
                pct_cpu=row.pct_cpu,
                tag=(row.labels or [{}])[-1].get("tag"),
                history=[
                    AttemptOut(
                        n=one["n"], status=one["status"], exit=one.get("exit"),
                        signal=signal_of(one.get("exit")),
                        memory_bytes=one.get("memory_bytes"),
                        peak_rss_bytes=one.get("peak_rss_bytes"),
                        realtime_ms=one.get("realtime_ms"),
                    )
                    for one in sorted(row.attempts or [], key=lambda a: a["n"])
                ],
            )
            for row in rows
        ]

    return TasksOut(tasks=tasks, total=total)


@router.get("/runs/{run_id}/series", operation_id="readSeries",
            summary="What this run held over time, and which curves are honest")
def run_series(run_id: str) -> Series:
    """**A query, never a fold** — `rn-blocked`, and A191's rule that a board is a query.

    `projection.state_of` replays every event a run ever produced; `run_task.attempts` is a
    column holding the same attempts, written by the projection when the row was written. A
    5,000-task run is 15,000 events to fold and one indexed `SELECT` to read.

    Every decision about *which* curves are honest belongs to `wiener_core.series`, which is
    pure and reads no clock. This route reads rows and hands them over.
    """
    with db.session_scope() as session:
        if repository.run(session, settings.lab_id, run_id) is None:
            raise HTTPException(status_code=404)
        rows = repository.attempts_of(session, settings.lab_id, run_id)

    attempts = [Attempt.model_validate(one) for row in rows for one in (row or [])]
    return series(attempts)


class ResultFile(BaseModel):
    """One published file. Every field is read off the filesystem; nothing is inferred."""

    process: str
    """The directory `publishDir` put it in, which is the process name lowercased. Read back
    rather than joined to the artifact: what is on disk is what the run actually produced."""
    name: str
    """Relative to the process directory, so nothing here is an absolute path."""
    size_bytes: int
    modified_ms: int


class ResultsOut(BaseModel):
    """What a run published, and — when it published nothing — which kind of nothing.

    **Three absences, and they are different facts.** `rn-absence`'s rule and
    `ProcessRow.reported_resources` are the shape being copied: an empty list for all three
    would say *this run produced no output* about a run that has not started, about a run whose
    pipeline predates publishing entirely, and about a run that genuinely made nothing.
    """

    files: list[ResultFile] = []
    total: int = 0
    """How many the run published, not how many are on this page."""
    published: bool
    """Whether this run has a results directory at all. `False` means the run was launched
    before `publishDir` existed, or has not reached `launch()` — never that it made nothing."""


@router.get("/runs/{run_id}/results", operation_id="readResults",
            summary="What a run published")
def run_results(run_id: str, after: int = 0, limit: int = 200) -> ResultsOut:
    """A directory walk, and deliberately nothing more.

    **Nothing here resolves anything** — the 2026-08-19 audit found every registry-touching
    screen cost ~250ms warm, and a results list has no reason to be one of them.

    **Paged, because a 5,000-task run publishes more than a page.** W2 shipped a console that
    fetched once at 200 and subscribed, and it was invisible on every run anybody had because
    the largest was five tasks. Same mistake, same file, one endpoint along.

    `lab_id` is enforced the way `repository.py`'s header asks: this hands back filenames, and a
    filter you can forget is a leak.
    """
    with db.session_scope() as session:
        if repository.run(session, settings.lab_id, run_id) is None:
            raise HTTPException(status_code=404)

    root = launcher.results_dir(run_id)
    if not root.is_dir():
        return ResultsOut(published=False)

    found = sorted(
        (path for path in root.rglob("*") if path.is_file()),
        key=lambda path: str(path.relative_to(root)),
    )
    page = found[after:after + limit]
    return ResultsOut(
        files=[
            ResultFile(
                process=path.relative_to(root).parts[0],
                name="/".join(path.relative_to(root).parts[1:]) or path.name,
                size_bytes=path.stat().st_size,
                modified_ms=int(path.stat().st_mtime * 1000),
            )
            for path in page
        ],
        total=len(found),
        published=True,
    )


TERMINAL = {"succeeded", "failed", "cancelled", "lost"}


@router.websocket("/runs/{run_id}/stream")
async def tail(socket: WebSocket, run_id: str) -> None:
    """The live tail, resumed from where a page of the record ended.

    **Closes when the run is terminal AND the stream is drained**, never on the first terminal
    event: §4.3 finding 3 is that `error` arrived *after* `completed`, so a socket that hangs
    up on the first one shows a failed run as successful and then goes quiet.

    The `from` query parameter is the `stream_id` the events page handed over (§7.2). Absent,
    it starts at the tail's current end rather than replaying — a subscriber with no page
    behind it asked to watch, not to catch up.
    """
    resume = socket.query_params.get("from") or "$"
    with db.session_scope() as session:
        if repository.run(session, settings.lab_id, run_id) is None:
            await socket.close(code=4404)
            return

    await socket.accept()
    try:
        while True:
            entries = await asyncio.to_thread(
                stream.read, run_id, resume, block_ms=1_000, count=100
            )
            for entry_id, fields in entries:
                resume = entry_id
                await socket.send_text(fields["json"])

            if not entries:
                # Drained. Only now does a terminal phase mean the run is over — the phase is
                # read from the projection rather than from the last event, because the fold
                # is what decides terminality and it takes both events into account.
                with db.session_scope() as session:
                    row = repository.run(session, settings.lab_id, run_id)
                    if row is not None and row.phase in TERMINAL:
                        await socket.close(code=1000)
                        return
    except WebSocketDisconnect:
        return

"""The public surface: upload an artifact, submit a run, read what happened.

Every body here is `extra="forbid"`, which is what makes an unexpected field a 422 rather than
a field silently ignored — and the field somebody would try is a path.
"""

import asyncio
import secrets
from datetime import UTC, datetime
from typing import Literal

from fastapi import APIRouter, HTTPException, UploadFile, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, ConfigDict

from wiener_api import db, jobs, repository
from wiener_api.models import Run, RunArtifact
from wiener_api.services import stream
from wiener_api.services.artifacts import declared_holes, store
from wiener_api.services.projection import state_of
from wiener_api.settings import settings

router = APIRouter(prefix="/api")


class SubmitRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    artifact_id: str
    params: dict[str, str | list[str]] = {}
    """The values only the laboratory can supply, and **the artifact is the schema**.

    Mendel emits every value it can justify and `= null` for every value it cannot, so a
    submission fills precisely those nulls — no more, and no fewer. That makes this map
    flexible without being open: `declared_holes()` reads them out of the artifact, so an
    unknown key and a missing one are both refused, for any pipeline, including one Mendel
    never built.

    **Not stored** — §7.1: no table holds a samplesheet. These ride to the launcher as a job
    argument, which is transient by nature and the right lifetime for run data.
    """
    executor: Literal["local"] = "local"
    """`local` only in W1. k8s and awsbatch are W5, and an enum that accepted them before
    anything had run there would be a lie the API tells its own generated client, which would
    offer them in a dropdown."""


class ArtifactStored(BaseModel):
    artifact_id: str
    digest: str
    size_bytes: int


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
    submitted_by: str
    submitted_at: datetime


@router.post("/artifacts", status_code=201, operation_id="uploadArtifact",
             summary="Upload a gated pipeline directory")
async def upload_artifact(bundle: UploadFile) -> ArtifactStored:
    try:
        artifact_id, digest, size = store(await bundle.read())
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    with db.session_scope() as session:
        repository.add(session, settings.lab_id, RunArtifact(
            id=artifact_id, uploaded_by="operator", uploaded_at=datetime.now(UTC),
            digest=digest, size_bytes=size,
        ))
    return ArtifactStored(artifact_id=artifact_id, digest=digest, size_bytes=size)


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
def board() -> list[RunRow]:
    with db.session_scope() as session:
        return [
            RunRow(id=r.id, phase=r.phase, executor=r.executor,
                   submitted_by=r.submitted_by, submitted_at=r.submitted_at)
            for r in repository.runs(session, settings.lab_id)
        ]


@router.get("/runs/{run_id}", operation_id="readRun", summary="A run, projected")
def read(run_id: str) -> dict:
    with db.session_scope() as session:
        if repository.run(session, settings.lab_id, run_id) is None:
            raise HTTPException(status_code=404)
        return state_of(session, settings.lab_id, run_id).model_dump(mode="json")


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

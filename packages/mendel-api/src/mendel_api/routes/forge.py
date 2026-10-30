"""`/forge` — the forge's catalogue of upstream modules (forge part 1, #362).

Read-only apart from asking for a sync. Nothing here writes the registry: forging, pull requests
and releases are later parts, each behind a person's approval.
"""

from typing import Annotated

from comeni_core.diagnostics import coded
from fastapi import APIRouter, HTTPException, Query
from mendel_forge.state import State
from pydantic import BaseModel

from mendel_api import jobs
from mendel_api.identity import default_author
from mendel_api.refusals import REFUSES, Refusal
from mendel_api.services import catalogue, forge_tests, forging
from mendel_api.services.catalogue import CataloguePage, ModuleDetail, Sort

router = APIRouter(prefix="/forge", tags=["forge"])


class SyncQueued(BaseModel):
    queued: bool
    """`False` when a sync is already running or queued: nothing new was started."""


@router.get(
    "/catalogue",
    operation_id="readCatalogue",
    summary="Upstream modules against the registry, filtered, searched and paged",
)
def read_catalogue(
    state: State | None = None,
    topic: Annotated[list[str], Query()] = [],  # noqa: B006 — FastAPI copies query defaults
    format: Annotated[list[str], Query()] = [],  # noqa: B006
    source: str | None = None,
    q: str | None = None,
    sort: Sort = Sort.BEST,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> CataloguePage:
    return catalogue.read_page(state=state, topics=topic, formats=format, source=source, q=q,
                               sort=sort, offset=offset, limit=limit)


@router.get(
    "/catalogue/{source}/{path:path}",
    operation_id="readCatalogueModule",
    summary="One upstream module: everything its source declares, and its state",
    responses=REFUSES,
)
def read_catalogue_module(source: str, path: str) -> ModuleDetail:
    try:
        return catalogue.read_module(source, path)
    except KeyError:
        raise HTTPException(
            status_code=404,
            detail=coded("MF0503", f"no module {path!r} from {source} in the catalogue"),
        ) from None


@router.post(
    "/catalogue/sync",
    operation_id="syncCatalogue",
    summary="Sync the catalogue from its source now",
    status_code=202,
    responses={**REFUSES, 503: {"model": Refusal, "description": "The job queue is down."}},
)
async def sync_catalogue() -> SyncQueued:
    if catalogue.sync_running():
        return SyncQueued(queued=False)
    try:
        queued = await jobs.enqueue("sync_catalogue_job", job_id=catalogue.sync_job_id())
    except Exception as error:
        raise HTTPException(
            status_code=503,
            detail=coded("MF0502", f"the sync could not be queued: {error}"),
        ) from error
    return SyncQueued(queued=queued)


# ═══ Forging (forge MVP 3, #364) ══════════════════════════════════════════════════════════════


class StartBody(BaseModel):
    model_config = {"extra": "forbid"}

    source: str
    path: str
    reforge: str | None = None
    """The contract id of an imported tool to re-forge from."""


class MessageBody(BaseModel):
    model_config = {"extra": "forbid"}

    content: str
    item: str | None = None
    """The item the message is about, if any."""


def _unknown(adaptation_id: str) -> HTTPException:
    return HTTPException(status_code=404, detail=coded(
        "MF0510", f"no adaptation {adaptation_id!r}"))


@router.post(
    "/adaptations",
    operation_id="startAdaptation",
    summary="Start forging a module from the catalogue",
    status_code=201,
    responses=REFUSES,
)
def start_adaptation(body: StartBody) -> forging.AdaptationView:
    try:
        return forging.start(body.source, body.path, default_author(), body.reforge)
    except KeyError as missing:
        raise HTTPException(status_code=404, detail=coded(
            "MF0503", f"no module or tool {missing.args[0]!r} to forge from")) from None


@router.get("/adaptations", operation_id="listAdaptations", summary="Open adaptations")
def list_adaptations() -> forging.AdaptationList:
    return forging.summaries()


@router.get(
    "/adaptations/{adaptation_id}",
    operation_id="readAdaptation",
    summary="An adaptation: its pieces, items, revisions and chat",
    responses=REFUSES,
)
def read_adaptation(adaptation_id: str) -> forging.AdaptationView:
    try:
        return forging.read(adaptation_id)
    except KeyError:
        raise _unknown(adaptation_id) from None


@router.post(
    "/adaptations/{adaptation_id}/commands",
    operation_id="commandAdaptation",
    summary="A person's decision on one item: answer, write, approve, change, reject, remove",
    responses=REFUSES,
)
def command_adaptation(adaptation_id: str, body: forging.CommandBody) -> forging.AdaptationView:
    try:
        return forging.act(adaptation_id, forging.person(
            body.move, body.item, expected=body.expected, value=body.value,
            because=body.because))
    except KeyError:
        raise _unknown(adaptation_id) from None


@router.post(
    "/adaptations/{adaptation_id}/messages",
    operation_id="messageAdaptation",
    summary="Say something to the AI about this tool, or about one item",
    status_code=202,
    responses=REFUSES,
)
async def message_adaptation(adaptation_id: str, body: MessageBody) -> forging.MessageView:
    try:
        return await forging.say(adaptation_id, body.content, body.item, default_author())
    except KeyError:
        raise _unknown(adaptation_id) from None


class DraftBody(BaseModel):
    model_config = {"extra": "forbid"}

    piece: str


@router.post(
    "/adaptations/{adaptation_id}/draft",
    operation_id="draftAdaptationPiece",
    summary="Ask the AI to draft the next piece",
    status_code=202,
    responses=REFUSES,
)
async def draft_adaptation_piece(adaptation_id: str, body: DraftBody) -> SyncQueued:
    try:
        return SyncQueued(queued=await forging.ask_to_draft(adaptation_id, body.piece))
    except KeyError:
        raise _unknown(adaptation_id) from None


@router.post(
    "/adaptations/{adaptation_id}/assemble",
    operation_id="assembleAdaptation",
    summary="Write the draft layer and prove it loads and conforms",
    responses=REFUSES,
)
def assemble_adaptation(adaptation_id: str) -> forging.AssemblyView:
    try:
        return forging.assemble(adaptation_id)
    except KeyError:
        raise _unknown(adaptation_id) from None


@router.post(
    "/adaptations/{adaptation_id}/tests",
    operation_id="runAdaptationTests",
    summary="Run the assembled draft's tests as Wiener runs",
    status_code=202,
    responses=REFUSES,
)
async def run_adaptation_tests(adaptation_id: str) -> forging.AdaptationView:
    try:
        return await forge_tests.start(adaptation_id)
    except KeyError:
        raise _unknown(adaptation_id) from None


@router.delete(
    "/adaptations/{adaptation_id}",
    operation_id="abandonAdaptation",
    summary="Abandon an adaptation; its record is kept",
    status_code=204,
    responses=REFUSES,
)
def abandon_adaptation(adaptation_id: str) -> None:
    try:
        forging.abandon(adaptation_id)
    except KeyError:
        raise _unknown(adaptation_id) from None

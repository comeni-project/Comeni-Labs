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
from mendel_api.refusals import REFUSES, Refusal
from mendel_api.services import catalogue
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

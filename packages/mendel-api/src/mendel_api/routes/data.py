"""An analysis's data (#511): the folder tree under the data roots, the folders an analysis
ticks, and what was found in them. An analysis is a draft, so its data is addressed by the
draft's id."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from mendel_api import identity, jobs
from mendel_api.db import session_scope
from mendel_api.models import AnalysisData, PipelineDraft
from mendel_api.refusals import REFUSES
from mendel_api.services.data import roots
from mendel_api.services.data.types import (
    AnalysisDataView,
    DataSample,
    FilesPage,
    Scan,
    ScannedFile,
)
from mendel_api.settings import settings

router = APIRouter(prefix="/data", tags=["data"])


class Folders(BaseModel):
    folders: list[str]


@router.get("/tree", operation_id="readDataTree", summary="A folder under the data roots",
            responses=REFUSES)
def read_tree(path: str | None = None) -> roots.FolderListing:
    """The folder's subfolders and file count; no `path` lists the roots themselves."""
    return roots.list_folder(path, settings.data_roots)


def _view(draft_id: str, row: AnalysisData | None) -> AnalysisDataView:
    if row is None:
        return AnalysisDataView(draft_id=draft_id)
    return AnalysisDataView(
        draft_id=draft_id, folders=list(row.folders or []), scan=Scan(**(row.scan or {})),
        samples=[DataSample(**s) for s in row.samples or []], files=len(row.files or []),
        revision=row.revision)


def _draft(db, draft_id: str) -> None:
    if db.get(PipelineDraft, draft_id) is None:
        raise HTTPException(status_code=404, detail=f"no draft {draft_id}")


@router.get("/{draft_id}", operation_id="readAnalysisData",
            summary="An analysis's data: its folders, samples and scan", responses=REFUSES)
def read_data(draft_id: str) -> AnalysisDataView:
    with session_scope() as db:
        _draft(db, draft_id)
        return _view(draft_id, db.get(AnalysisData, draft_id))


@router.get("/{draft_id}/files", operation_id="readAnalysisFiles",
            summary="A page of the files in an analysis's folders", responses=REFUSES)
def read_files(draft_id: str, offset: int = 0, limit: int = 200) -> FilesPage:
    with session_scope() as db:
        _draft(db, draft_id)
        row = db.get(AnalysisData, draft_id)
        files = list(row.files or []) if row else []
    limit = max(1, min(limit, 1000))
    return FilesPage(files=[ScannedFile(**f) for f in files[max(0, offset):offset + limit]],
                     total=len(files))


@router.put("/{draft_id}/folders", operation_id="tickDataFolders",
            summary="Tick the folders an analysis reads, and scan them", responses=REFUSES)
async def tick_folders(draft_id: str, body: Folders) -> AnalysisDataView:
    """Each folder is checked against the data roots, then the scan is queued: the page polls
    `readAnalysisData` while it runs."""
    ticked = sorted({str(roots.inside_roots(f, settings.data_roots)) for f in body.folders})
    with session_scope() as db:
        _draft(db, draft_id)
        row = db.get(AnalysisData, draft_id)
        if row is None:
            row = AnalysisData(draft_id=draft_id, folders=[], scan={}, files=[], samples=[])
            db.add(row)
        row.folders = ticked
        row.revision = (row.revision or 0) + 1
        row.scan = Scan(state="scanning").model_dump()
        revision = row.revision
    await jobs.enqueue("scan_analysis_data", draft_id, identity.default_author(),
                       job_id=jobs.job_id_for("scan", draft_id, str(revision)))
    with session_scope() as db:
        return _view(draft_id, db.get(AnalysisData, draft_id))

"""An analysis's data (#511): the folder tree under the data roots, the folders an analysis
ticks, and what was found in them. An analysis is a draft, so its data is addressed by the
draft's id."""

import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from mendel_api import identity, jobs
from mendel_api.db import session_scope
from mendel_api.models import AnalysisData, PipelineDraft
from mendel_api.refusals import REFUSES
from mendel_api.services.data import roots, rule
from mendel_api.services.data.rule import Fix, Rule
from mendel_api.services.data.types import (
    AnalysisDataView,
    DataSample,
    FilesPage,
    RuleResult,
    Scan,
    ScannedFile,
)
from mendel_api.settings import settings

router = APIRouter(prefix="/data", tags=["data"])
log = logging.getLogger(__name__)


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
    samples = list(row.samples or [])
    scanned = Scan(**(row.scan or {}))
    return AnalysisDataView(
        draft_id=draft_id, folders=list(row.folders or []), scan=scanned,
        samples=[DataSample(**s) for s in samples], files=len(row.files or []),
        revision=row.revision, rule=Rule(**row.rule) if row.rule else Rule(),
        fixes=[Fix(**f) for f in row.fixes or []],
        rule_result=RuleResult(samples=len(samples), unfit=len(row.unfit or []),
                               examples=scanned.examples),
        checks=rule.checks(samples, list(row.unfit or [])))


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


async def _rescan(draft_id: str, change) -> AnalysisDataView:
    """Apply `change` to the analysis's data row, then queue a scan of its newest revision. A scan
    that cannot be queued says so rather than scanning for ever."""
    with session_scope() as db:
        _draft(db, draft_id)
        row = db.get(AnalysisData, draft_id)
        if row is None:
            row = AnalysisData(draft_id=draft_id, folders=[], scan={}, files=[], samples=[],
                               fixes=[], unfit=[])
            db.add(row)
        change(row)
        row.revision = (row.revision or 0) + 1
        row.scan = Scan(state="scanning").model_dump()
        revision = row.revision
    try:
        await jobs.enqueue("scan_analysis_data", draft_id, identity.default_author(), revision,
                           job_id=jobs.job_id_for("scan", draft_id, str(revision)))
    except Exception:  # noqa: BLE001 — a scan nobody will run must not say it is scanning
        log.exception("scan %s:%s could not be queued", draft_id, revision)
        with session_scope() as db:
            row = db.get(AnalysisData, draft_id)
            if row is not None and row.revision == revision:
                said = "the scan could not start; tick the folder again"
                row.scan = Scan(state="failed", error=said).model_dump()
    with session_scope() as db:
        return _view(draft_id, db.get(AnalysisData, draft_id))


@router.put("/{draft_id}/folders", operation_id="tickDataFolders",
            summary="Tick the folders an analysis reads, and scan them", responses=REFUSES)
async def tick_folders(draft_id: str, body: Folders) -> AnalysisDataView:
    """Each folder is checked against the data roots, then the scan is queued: the page polls
    `readAnalysisData` while it runs."""
    ticked = sorted({str(roots.inside_folder(f, settings.data_roots)) for f in body.folders})
    return await _rescan(draft_id, lambda row: setattr(row, "folders", ticked))


class Pattern(BaseModel):
    pattern: str | None


@router.put("/{draft_id}/rule", operation_id="setReadingRule",
            summary="Read the files into samples by a pattern, and scan again", responses=REFUSES)
async def set_rule(draft_id: str, body: Pattern) -> AnalysisDataView:
    """`{sample}` and `{read}` in a file name; `null` returns to the default pairing. The person's
    rule is theirs and unconfirmed until **Looks right**."""
    chosen = Rule(pattern=body.pattern, origin="you" if body.pattern else "rule")
    if chosen.pattern is not None:
        rule.group([], chosen, [])  # refuses a bad pattern now, with MI0223
    return await _rescan(draft_id, lambda row: setattr(row, "rule", chosen.model_dump()))


@router.post("/{draft_id}/rule/confirm", operation_id="confirmReadingRule",
             summary="The reading rule looks right", responses=REFUSES)
def confirm_rule(draft_id: str) -> AnalysisDataView:
    with session_scope() as db:
        _draft(db, draft_id)
        row = db.get(AnalysisData, draft_id)
        if row is None:
            raise HTTPException(status_code=404, detail=f"no data for {draft_id}")
        row.rule = (Rule(**row.rule) if row.rule else Rule()).model_copy(
            update={"confirmed": True}).model_dump()
        return _view(draft_id, row)


@router.post("/{draft_id}/fixes", operation_id="applyDataFix",
             summary="Use a file as a sample's mate, or leave a sample out; then scan again",
             responses=REFUSES)
async def apply_fix(draft_id: str, body: Fix) -> AnalysisDataView:
    """A fix is kept and applied on every scan, so it survives the next one."""
    def keep(row):
        row.fixes = [*(row.fixes or []), body.model_dump()]
    return await _rescan(draft_id, keep)

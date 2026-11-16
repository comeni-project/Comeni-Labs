"""An analysis's data (#511): the folder tree under the data roots, the folders an analysis
ticks, and what was found in them. An analysis is a draft, so its data is addressed by the
draft's id."""

import logging
from typing import Literal

from comeni_core.diagnostics import coded
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from mendel_api import identity, jobs
from mendel_api.db import session_scope
from mendel_api.models import AnalysisData, PipelineDraft
from mendel_api.refusals import REFUSES
from mendel_api.services.data import roots, rule
from mendel_api.services.data.bindings import Bindings, bind
from mendel_api.services.data.kinds import Reader
from mendel_api.services.data.rule import Fix, Rule
from mendel_api.services.data.summary import summary
from mendel_api.services.data.types import (
    AnalysisDataView,
    DataSample,
    FilesPage,
    Reference,
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
    """The folder's subfolders and file count, each saying what it looks like; no `path` lists
    the roots themselves."""
    from pathlib import Path

    from mendel_api.services.data import kinds

    listing = roots.list_folder(path, settings.data_roots)
    for folder in listing.folders:
        folder.looks_like = kinds.looks_like(Path(folder.path))
    return listing


@router.get("/readers", operation_id="readDataReaders",
            summary="The kinds of data Comeni reads, from which files, and what it measures",
            responses=REFUSES)
def read_readers() -> list[Reader]:
    from mendel_api.services.data import kinds

    return kinds.readers()


class Machine(BaseModel):
    cpus: int
    load: float
    """Processes waiting or running, over the last minute."""
    memory_gb: float
    memory_free_gb: float
    disk_free_gb: float
    """Free space where the data is, or where this server runs when no data folder is set."""


@router.get("/machine", operation_id="readMachine", summary="This machine: CPUs, memory, disk",
            responses=REFUSES)
def machine() -> Machine:
    import os
    import shutil

    def meminfo(key: str) -> float:
        try:
            with open("/proc/meminfo") as handle:
                for line in handle:
                    if line.startswith(key + ":"):
                        return int(line.split()[1]) / 2**20
        except OSError:
            pass
        return 0.0

    where = settings.data_roots[0] if settings.data_roots else "."
    try:
        free = shutil.disk_usage(where).free / 2**30
    except OSError:
        free = 0.0
    return Machine(cpus=os.cpu_count() or 1, load=round(os.getloadavg()[0], 1),
                   memory_gb=round(meminfo("MemTotal"), 1),
                   memory_free_gb=round(meminfo("MemAvailable"), 1), disk_free_gb=round(free, 1))


@router.get("/reference-types", operation_id="readReferenceTypes",
            summary="The kinds of file a reference can be", responses=REFUSES)
def reference_types() -> list[str]:
    """Every declared type that is one file for the whole study (a genome, an annotation, an
    index), which is what a reference is."""
    from mendel_api.services import registry

    return sorted(t for t, grain in registry.stack().vocabulary.grains.items()
                  if str(grain) == "study")


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
        checks=rule.checks(samples, list(row.unfit or []), [Fix(**f) for f in row.fixes or []]),
        references=[Reference(**r) for r in row.references or []],
        columns=dict(row.columns or {}),
        summary=summary(samples, list(row.files or [])))


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
            row = _blank(draft_id)
            db.add(row)
        change(row)
        row.revision = (row.revision or 0) + 1
        row.scan = Scan(state="scanning").model_dump()
        revision = row.revision
    from mendel_api.services import decisions

    # What the data says may have moved already (a reference is an input at once).
    decisions.data_changed(draft_id)
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


class FixRequest(BaseModel):
    kind: Literal["use_file", "leave_out", "keep"]
    sample: str
    file: str | None = None
    measurement: str | None = None


@router.post("/{draft_id}/fixes", operation_id="applyDataFix",
             summary="Use a file as a sample's mate, or leave a sample out; then scan again",
             responses=REFUSES)
async def apply_fix(draft_id: str, body: FixRequest) -> AnalysisDataView:
    """A fix is kept and applied on every scan, so it survives the next one. **Recorded as the
    person's**: who made a change is the server's to say, never the page's."""
    made = Fix(kind=body.kind, sample=body.sample, file=body.file, measurement=body.measurement)
    with session_scope() as db:
        _draft(db, draft_id)
        row = db.get(AnalysisData, draft_id)
        rule.validate(made, list(row.samples or []) if row else [],
                      list(row.unfit or []) if row else [])

    def keep(row):
        row.fixes = [*(row.fixes or []), made.model_dump()]
    return await _rescan(draft_id, keep)


@router.post("/{draft_id}/fixes/{index}/keep", operation_id="keepDataFix",
             summary="Keep a fix the AI made: it becomes the person's", responses=REFUSES)
def keep_fix(draft_id: str, index: int) -> AnalysisDataView:
    with session_scope() as db:
        _draft(db, draft_id)
        row = db.get(AnalysisData, draft_id)
        fixes = list(row.fixes or []) if row else []
        if not 0 <= index < len(fixes):
            raise HTTPException(status_code=404, detail=f"no fix {index}")
        fixes[index] = {**fixes[index], "by": "you"}
        row.fixes = fixes
        db.flush()
        return _view(draft_id, row)


@router.post("/{draft_id}/rescan", operation_id="rescanData",
             summary="Read the ticked folders again", responses=REFUSES)
async def rescan(draft_id: str) -> AnalysisDataView:
    """Files added, changed or removed since the last scan are read again."""
    return await _rescan(draft_id, lambda row: None)


class Cell(BaseModel):
    value: str


@router.put("/{draft_id}/columns/{name}/{sample}", operation_id="setDataCell",
            summary="Set one sample's value in a column", responses=REFUSES)
def set_cell(draft_id: str, name: str, sample: str, body: Cell) -> AnalysisDataView:
    """One cell, so two cells edited one after the other both stand."""
    def keep(row):
        if name not in (row.columns or {}):
            raise HTTPException(status_code=404, detail=f"no column {name}")
        column = {**row.columns[name], sample: body.value.strip()}
        row.columns = {**row.columns, name: column}
    return _change(draft_id, keep)


def _blank(draft_id: str) -> AnalysisData:
    return AnalysisData(draft_id=draft_id, folders=[], scan={}, files=[], samples=[], fixes=[],
                        unfit=[], references=[], columns={})


def _change(draft_id: str, change) -> AnalysisDataView:
    """A change that needs no scan: what a person named or typed."""
    with session_scope() as db:
        _draft(db, draft_id)
        row = db.get(AnalysisData, draft_id)
        if row is None:
            row = _blank(draft_id)
            db.add(row)
        change(row)
        db.flush()
        view = _view(draft_id, row)
    # What a person named or typed changes the facts and inputs: the pipeline is built again.
    from mendel_api.agent import chat
    from mendel_api.services import decisions

    decisions.data_changed(draft_id)
    try:
        chat.rebuild_for_data(draft_id, identity.default_author())
    except Exception:  # noqa: BLE001 — the data is saved; a build that fails says so on Build
        log.exception("rebuild after a data change on %s failed", draft_id)
    return view


class NamedFile(BaseModel):
    path: str
    type_id: str


@router.post("/{draft_id}/references", operation_id="addReference",
             summary="Add a study-wide file, such as a genome, with its type", responses=REFUSES)
async def add_reference(draft_id: str, body: NamedFile) -> AnalysisDataView:
    """The file is checked against the data roots and its type against the vocabulary, then its
    head is measured like a sample's. It becomes an input the analysis has."""
    from mendel_api.authoring.types import SampleFact
    from mendel_api.services import inspect, registry
    from mendel_api.services.data.scan import _head

    path = roots.inside_roots(body.path, settings.data_roots)
    if not path.is_file():
        raise ValueError(coded("MI0221", f"{body.path} is not a file Comeni can read"))
    if body.type_id not in registry.stack().vocabulary.types:
        raise ValueError(coded("MI0224", f"{body.type_id} is not a declared type"))
    found = inspect.inspect_sample([(path.name, _head(path, inspect.HEAD_BYTES))],
                                   registry.stack(), None, sizes=(path.stat().st_size,))
    made = Reference(path=str(path), name=path.name, type_id=body.type_id, facts=[
        SampleFact(measurement=f.measurement, value=f.value, coverage=f.coverage,
                   pieces=list(f.pieces))
        for f in found.facts if f.undetermined is None])

    def keep(row):
        row.references = [*(row.references or []), made.model_dump(mode="json")]
    # Scanned again: a file named as a reference is not a sample any more.
    return await _rescan(draft_id, keep)


@router.delete("/{draft_id}/references/{index}", operation_id="removeReference",
               summary="Remove a study-wide file", responses=REFUSES)
async def remove_reference(draft_id: str, index: int) -> AnalysisDataView:
    def drop(row):
        kept = list(row.references or [])
        if not 0 <= index < len(kept):
            raise HTTPException(status_code=404, detail=f"no reference {index}")
        row.references = kept[:index] + kept[index + 1:]
    return await _rescan(draft_id, drop)


class Column(BaseModel):
    name: str
    values: dict[str, str]


@router.put("/{draft_id}/columns", operation_id="setDataColumn",
            summary="Set a column of the samples table, such as condition or batch",
            responses=REFUSES)
def set_column(draft_id: str, body: Column) -> AnalysisDataView:
    """A column a person types: a condition, a batch, or a fact nothing measured (strandedness),
    which the run's samplesheet then reads. One named after a fact the data measured is refused:
    the measured values are already that column."""
    name = body.name.strip()
    with session_scope() as db:
        row = db.get(AnalysisData, draft_id)
        measured = {f["measurement"] for s in (row.samples if row else []) for f in s["facts"]}
    if not name or name in measured:
        raise ValueError(coded("MI0225", f"{body.name!r} is measured on this data already; "
                                         "choose another name"))

    def keep(row):
        # A column that exists keeps its values: adding it again changes nothing.
        given = dict(body.values) or dict((row.columns or {}).get(name, {}))
        row.columns = {**(row.columns or {}), name: given}
    return _change(draft_id, keep)


@router.get("/{draft_id}/bindings", operation_id="readRunBindings",
            summary="A run's inputs, answered from the analysis's data", responses=REFUSES)
def read_bindings(draft_id: str) -> Bindings:
    """Each input the kept pipeline declares, answered by type from the samples and references,
    or `missing` with why. Built now, never stored: the browser sends it to Wiener."""
    from comeni_core import yaml_strict
    from comeni_core.artifact.pipeline import Pipeline

    from mendel_api.services import drafts as draft_service

    with session_scope() as db:
        _draft(db, draft_id)
        row = db.get(AnalysisData, draft_id)
        samples = list(row.samples or []) if row else []
        references = list(row.references or []) if row else []
        columns = dict(row.columns or {}) if row else {}
    path = draft_service.artifact_path(draft_id)
    pipeline = (Pipeline.model_validate(yaml_strict.load(path))
                if path is not None and path.is_file() else None)
    return bind(pipeline, samples, references, columns)


@router.delete("/{draft_id}/fixes/{index}", operation_id="undoDataFix",
               summary="Undo a fix, and scan again", responses=REFUSES)
async def undo_fix(draft_id: str, index: int) -> AnalysisDataView:
    def drop(row):
        kept = list(row.fixes or [])
        if not 0 <= index < len(kept):
            raise HTTPException(status_code=404, detail=f"no fix {index}")
        row.fixes = kept[:index] + kept[index + 1:]
    return await _rescan(draft_id, drop)

"""Reference selection from the saved inventory, using opaque IDs at the agent boundary."""

import hashlib
from pathlib import Path

from comeni_core.diagnostics import coded
from comeni_core.egress.agent import ReferenceCandidate

from mendel_api.authoring.types import SampleFact
from mendel_api.db import session_scope
from mendel_api.models import AnalysisData
from mendel_api.services import decisions, inspect, registry
from mendel_api.services.data import kinds, roots
from mendel_api.services.data.scan import REFERENCE_FOLDERS, _head
from mendel_api.services.data.types import Reference
from mendel_api.settings import settings


def file_id(path: str) -> str:
    return "sha256:" + hashlib.sha256(path.encode()).hexdigest()


def candidates(row: AnalysisData) -> list[ReferenceCandidate]:
    study = sorted(t for t, grain in registry.stack().vocabulary.grains.items()
                   if str(grain) == "study")
    readers = kinds.readers()
    selected = {r["path"]: r["type_id"] for r in row.references or []}
    result = []
    for found in row.files or []:
        if found.get("sample") or found.get("recognised") == "fastq.reads":
            continue
        path = Path(found["path"])
        name = path.name.lower().removesuffix(".gz")
        types = []
        for type_id in study:
            suffix = "." + type_id.rsplit(".", 1)[-1]
            family = next((r.extensions for r in readers if suffix in r.extensions), [suffix])
            if any(name.endswith(extension) for extension in family):
                types.append(type_id)
        exact = [t for t in types if name.endswith("." + t.rsplit(".", 1)[-1])]
        if exact:
            types = exact
        if found["path"] in selected:
            types = sorted(set([*types, selected[found["path"]]]))
        if not types:
            continue
        collection = (path.parent.parent.name if path.parent.name.lower() in REFERENCE_FOLDERS
                      else path.parent.name)
        result.append(ReferenceCandidate(
            id=file_id(found["path"]), name=path.name[:256],
            collection=(collection or "data")[:256], types=types,
            selected=found["path"] in selected))
    return result


def choose(draft_id: str, selected_id: str, type_id: str, because: str) -> str:
    with session_scope() as db:
        row = db.get(AnalysisData, draft_id, with_for_update=True)
        if row is None:
            raise ValueError(coded(
                "MI0226", "read the analysis's data before choosing a reference"))
        available = candidates(row)
        candidate = next((c for c in available if c.id == selected_id), None)
        if candidate is None or type_id not in candidate.types:
            raise ValueError(coded(
                "MI0226", "choose a file and reference kind offered by read_data"))
        if (row.scan or {}).get("state") == "scanning":
            raise ValueError(coded("MI0226", "wait for the current file read to finish"))
        stored = next(f for f in row.files if file_id(f["path"]) == selected_id)
        if any(r["path"] == stored["path"] and r["type_id"] == type_id
               for r in row.references or []):
            return candidate.name
        try:
            path = roots.inside_roots(stored["path"], settings.data_roots)
        except ValueError:
            raise ValueError(coded("MI0221", "the selected reference is no longer accessible; "
                                   "refresh Data")) from None
        # Read just the chosen reference, never rescan the sample files.
        found = inspect.inspect_sample([(path.name, _head(path, inspect.HEAD_BYTES))],
                                       registry.stack(), None, sizes=(path.stat().st_size,))
        made = Reference(path=str(path), name=path.name, type_id=type_id, origin="ai",
                         reason=because, facts=[SampleFact(
                             measurement=f.measurement, value=f.value, coverage=f.coverage,
                             pieces=list(f.pieces)) for f in found.facts
                             if f.undetermined is None])
        previous = {r["path"] for r in row.references or []
                    if r["type_id"] == type_id or r["path"] == stored["path"]}
        kept = [r for r in row.references or []
                if r["type_id"] != type_id and r["path"] != stored["path"]]
        row.references = [*kept, made.model_dump(mode="json")]
        still_selected = {r["path"] for r in row.references}
        row.files = [{**f, "used_as": "reference" if f["path"] in still_selected
                      else "candidate" if f["path"] in previous else f.get("used_as")}
                     for f in row.files or []]
        row.revision = (row.revision or 0) + 1
        db.flush()
    decisions.data_changed(draft_id)
    return candidate.name

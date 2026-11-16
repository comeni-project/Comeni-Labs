"""Scanning an analysis's ticked folders (#511): every file listed, paired into samples, and each
sample measured from its files' heads where they lie.

**One sample's heads at a time.** Hundreds of samples are read in turn: a sample's heads are
read, measured and dropped before the next, and only the facts are kept. Nothing is copied.

**It never raises.** A job that raised would leave the page saying *scanning* for ever; a failure
is written down as `failed`, with what went wrong, and the person can tick again.
"""

import os
from pathlib import Path

from mendel_api.authoring.types import SampleFact
from mendel_api.db import session_scope
from mendel_api.models import AnalysisData
from mendel_api.services import inspect, protection, registry
from mendel_api.services.data import pairing, record
from mendel_api.services.data.roots import inside_roots
from mendel_api.services.data.types import DataSample, Scan, ScannedFile
from mendel_api.settings import settings


def _head(path: Path, size: int) -> bytes:
    """A file's first `size` bytes, read and nothing more."""
    with open(path, "rb") as handle:
        return handle.read(size)


def _files(folders: list[str]) -> list[list[Path]]:
    """Each ticked folder's own files (not its subfolders', which are ticked on their own),
    sorted by name, hidden ones left out; a folder ticked twice counts once."""
    seen: set[Path] = set()
    out = []
    for folder in folders:
        where = inside_roots(folder, settings.data_roots)
        if where in seen:
            continue
        seen.add(where)
        with os.scandir(where) as entries:
            out.append(sorted(Path(e.path) for e in entries
                              if e.is_file() and not e.name.startswith(".")))
    return out


def _save(draft_id: str, **columns) -> None:
    with session_scope() as db:
        row = db.get(AnalysisData, draft_id)
        for name, value in columns.items():
            setattr(row, name, value)


def scan(draft_id: str, *, who: str) -> None:
    """Read the ticked folders of `draft_id` again, from scratch."""
    try:
        if not protection.allows(protection.Crossing.SAMPLE_HEAD):
            raise ValueError(protection.refuse(protection.Crossing.SAMPLE_HEAD))
        with session_scope() as db:
            folders = list(db.get(AnalysisData, draft_id).folders or [])
        groups = _files(folders)
        total = sum(len(g) for g in groups)
        _save(draft_id, scan=Scan(state="scanning", total=total).model_dump())
        stack = registry.stack()
        files: list[ScannedFile] = []
        samples: list[DataSample] = []
        inspections = []
        taken: set[str] = set()
        done = 0
        for paths in groups:
            for name, indexes in pairing.pair([p.name for p in paths], taken):
                chosen = [paths[i] for i in indexes]
                sizes = tuple(p.stat().st_size for p in chosen)
                heads = [(p.name, _head(p, inspect.HEAD_BYTES)) for p in chosen]
                found = inspect.inspect_sample(heads, stack, None, sizes=sizes)
                del heads
                inspections.append(found)
                samples.append(DataSample(
                    name=name, files=[str(p) for p in chosen], outcome=found.outcome,
                    type_id=found.type_id,
                    facts=[SampleFact(measurement=f.measurement, value=f.value, coverage=f.coverage)
                           for f in found.facts if f.undetermined is None]))
                files += [ScannedFile(path=str(p), name=p.name, size=s, sample=name,
                                      recognised=found.type_id)
                          for p, s in zip(chosen, sizes, strict=True)]
                done += len(chosen)
                _save(draft_id, scan=Scan(state="scanning", done=done, total=total).model_dump())
        _save(draft_id, files=[f.model_dump() for f in files],
              samples=[s.model_dump(mode="json") for s in samples])
        if inspections:
            record.record_measured(draft_id, record.agreed(inspections), who=who)
        _save(draft_id, scan=Scan(state="done", done=done, total=total).model_dump())
    except Exception as failed:  # noqa: BLE001 — a scan says what went wrong, never hangs
        _save(draft_id, scan=Scan(state="failed", error=str(failed)[:500]).model_dump())

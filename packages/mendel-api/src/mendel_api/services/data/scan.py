"""Scanning an analysis's ticked folders (#511): every file listed, paired into samples, and each
sample measured from its files' heads where they lie.

**One sample's heads at a time.** Hundreds of samples are read in turn: a sample's heads are
read, measured and dropped before the next, and only the facts are kept. Nothing is copied.

**It never raises.** A job that raised would leave the page saying *scanning* for ever; a failure
is written down as `failed`, with what went wrong, and the person can tick again.
"""

import os
import stat
from pathlib import Path

from mendel_api.authoring.types import SampleFact
from mendel_api.db import session_scope
from mendel_api.models import AnalysisData
from mendel_api.services import inspect, registry
from mendel_api.services.data import pairing
from mendel_api.services.data.roots import inside_roots
from mendel_api.services.data.types import DataSample, Scan, ScannedFile
from mendel_api.settings import settings


def _head(path: Path, size: int) -> bytes:
    """A regular file's first `size` bytes, read and nothing more. **Opened without following a
    link, and checked to be a regular file on the open descriptor**, so nothing swapped in
    after the check is read, and a FIFO or device cannot hang the scan."""
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            raise OSError(f"{path.name} is not a regular file")
        with os.fdopen(fd, "rb", closefd=False) as handle:
            return handle.read(size)
    finally:
        os.close(fd)


def _files(folders: list[str]) -> list[list[Path]]:
    """Each ticked folder's own regular files (not its subfolders', which are ticked on their
    own), resolved, each inside a data root, sorted by name; hidden ones left out. **A link that
    leads outside the roots is skipped, not followed** (Checkpoint A). A folder ticked twice
    counts once."""
    roots = settings.data_roots
    seen: set[Path] = set()
    out = []
    for folder in folders:
        where = inside_roots(folder, roots)
        if where in seen:
            continue
        seen.add(where)
        kept = []
        with os.scandir(where) as entries:
            for entry in entries:
                if entry.name.startswith("."):
                    continue
                try:
                    resolved = inside_roots(entry.path, roots)
                except ValueError:
                    continue
                if resolved.is_file():
                    kept.append(resolved)
        out.append(sorted(set(kept), key=lambda p: p.name))
    return out


class _Stale(Exception):
    """The draft is gone, or the person ticked again: this scan's results are nobody's."""


def _save(draft_id: str, revision: int, **columns) -> None:
    """Write this scan's columns, **only while it is still the newest scan of a live draft**."""
    with session_scope() as db:
        row = db.get(AnalysisData, draft_id)
        if row is None or row.revision != revision:
            raise _Stale()
        for name, value in columns.items():
            setattr(row, name, value)


def scan(draft_id: str, *, who: str, revision: int | None = None) -> None:
    """Read the ticked folders of `draft_id` again, from scratch. `revision` is the tick this
    scan answers; a newer tick makes it stale and it stops writing."""
    try:
        with session_scope() as db:
            row = db.get(AnalysisData, draft_id)
            if row is None:
                return
            folders = list(row.folders or [])
            revision = row.revision if revision is None else revision
        _run(draft_id, folders, revision, who)
    except _Stale:
        return


def _run(draft_id: str, folders: list[str], revision: int, who: str) -> None:
    try:
        groups = _files(folders)
        total = sum(len(g) for g in groups)
        _save(draft_id, revision, scan=Scan(state="scanning", total=total).model_dump())
        stack = registry.stack()
        files: list[ScannedFile] = []
        samples: list[DataSample] = []
        taken: set[str] = set()
        done = 0
        for paths in groups:
            for name, indexes in pairing.pair([p.name for p in paths], taken):
                chosen = [paths[i] for i in indexes]
                try:
                    sizes = tuple(p.stat().st_size for p in chosen)
                    heads = [(p.name, _head(p, inspect.HEAD_BYTES)) for p in chosen]
                except OSError:
                    continue  # gone, or not a regular file any more: not a sample
                found = inspect.inspect_sample(heads, stack, None, sizes=sizes)
                del heads
                samples.append(DataSample(
                    name=name, files=[str(p) for p in chosen], outcome=found.outcome,
                    type_id=found.type_id,
                    facts=[SampleFact(measurement=f.measurement, value=f.value, coverage=f.coverage)
                           for f in found.facts if f.undetermined is None]))
                files += [ScannedFile(path=str(p), name=p.name, size=s, sample=name,
                                      recognised=found.type_id)
                          for p, s in zip(chosen, sizes, strict=True)]
                done += len(chosen)
                _save(draft_id, revision,
                      scan=Scan(state="scanning", done=done, total=total).model_dump())
        _save(draft_id, revision, files=[f.model_dump() for f in files],
              samples=[s.model_dump(mode="json") for s in samples])
        _save(draft_id, revision, scan=Scan(state="done", done=done, total=total).model_dump())
    except _Stale:
        raise
    except Exception as failed:  # noqa: BLE001 — a scan says what went wrong, never hangs
        # What another selection found is not this one's: a failed scan shows nothing found.
        _save(draft_id, revision, files=[], samples=[],
              scan=Scan(state="failed", error=str(failed)[:500]).model_dump())


def finished(draft_id: str, revision: int) -> bool:
    """Whether the scan for `revision` is the newest and finished well."""
    with session_scope() as db:
        row = db.get(AnalysisData, draft_id)
        return bool(row and row.revision == revision and (row.scan or {}).get("state") == "done")

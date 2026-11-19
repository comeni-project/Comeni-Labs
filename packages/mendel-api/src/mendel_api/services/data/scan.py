"""Scanning an analysis's ticked folders (#511): every file listed, paired into samples, and each
sample measured from its files' heads where they lie.

**A sample measured once.** A rescan reuses what a sample measured when it is the same files,
each with the same size, modification time and inode, under the same registry and measurer
versions (#570); anything else is measured again. A rewrite that keeps all three stats is not
seen, which the operator accepted on 2026-11-18 over hashing every head.

**At most `inspect.AT_ONCE` samples' heads at a time** (#571): two samples are measured at
once, each sample's heads read, measured and dropped before that worker takes the next, and
only the facts are kept. Never every head first. Nothing is copied.

**It never raises.** A job that raised would leave the page saying *scanning* for ever; a failure
is written down as `failed`, with what went wrong, and the person can tick again.
"""

import hashlib
import importlib.metadata
import json
import os
import stat
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path

from mendel_api.authoring.types import SampleFact
from mendel_api.db import session_scope
from mendel_api.models import AnalysisData
from mendel_api.services import decisions, inspect, registry
from mendel_api.services.data import rule
from mendel_api.services.data.roots import inside_roots
from mendel_api.services.data.rule import Fix, Rule
from mendel_api.services.data.types import Scan, ScannedFile, StoredSample
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


def _measurers() -> str:
    """What measures a sample besides the registry: the inspection code's released versions."""
    return ",".join(importlib.metadata.version(name) for name in ("comeni-inspect", "mendel-api"))


def _key(digest: str, chosen: list[Path], stats: list[os.stat_result]) -> str:
    """The reuse key of one sample (#570): its files in order, each file's size, modification
    time and inode, the registry digest and the measurers' versions. A digest of them, so the
    stored key says nothing about the files."""
    made = [digest, _measurers(),
            [[str(p), st.st_size, st.st_mtime_ns, st.st_ino] for p, st in zip(chosen, stats,
                                                                              strict=True)]]
    return "sha256:" + hashlib.sha256(json.dumps(made).encode()).hexdigest()


def scan(draft_id: str, *, who: str, revision: int | None = None) -> None:
    """Read the ticked folders of `draft_id` again. A sample whose files are unchanged keeps
    what it measured (#570); every other is measured from its files' heads. `revision` is the
    tick this scan answers; a newer tick makes it stale and it stops writing."""
    try:
        with session_scope() as db:
            row = db.get(AnalysisData, draft_id)
            if row is None:
                return
            folders = list(row.folders or [])
            revision = row.revision if revision is None else revision
            reading = Rule(**row.rule) if row.rule else Rule()
            fixes = [Fix(**f) for f in row.fixes or []]
            references = {r["path"] for r in row.references or []}
            measured = {s["key"]: s for s in row.samples or [] if s.get("key")}
        _run(draft_id, folders, revision, who, reading, fixes, references, measured)
    except _Stale:
        return


# Folders whose files are the study's references, not samples (walk 2026-11-16). Only names
# that say *reference*: `genomes/` is where a lab keeps its isolates' assemblies (Checkpoint D).
REFERENCE_FOLDERS = frozenset({"reference", "references", "ref", "refs"})


def _run(draft_id: str, folders: list[str], revision: int, who: str, reading: Rule,
         fixes: list[Fix], references: set[str] = frozenset(),
         measured: dict[str, dict] | None = None) -> None:
    measured = measured or {}
    try:
        groups = _files(folders)
        total = sum(len(g) for g in groups)
        _save(draft_id, revision, scan=Scan(state="scanning", total=total).model_dump())
        stack, digest = registry.stack(), registry.digest()
        said_at = time.monotonic()
        files: list[ScannedFile] = []
        samples: list[StoredSample] = []
        taken: set[str] = set()
        unfit: list[str] = []
        left_out = {f.sample for f in fixes if f.kind == "leave_out"}
        done = 0
        examples: list[tuple[str, str, str | None]] = []
        for listed in groups:
            # A file named as a reference is the study's, not a sample (#511).
            paths = [p for p in listed if str(p) not in references
                     and p.parent.name.lower() not in REFERENCE_FOLDERS]
            for p in listed:
                if str(p) in references or p.parent.name.lower() in REFERENCE_FOLDERS:
                    files.append(ScannedFile(
                        path=str(p), name=p.name, size=p.stat().st_size,
                        used_as="reference" if str(p) in references else "candidate"))
                    done += 1
            grouped = rule.group([p.name for p in paths], reading, fixes, taken)
            examples += grouped.examples[:3 - len(examples)]
            for index in grouped.unfit:
                try:
                    size = paths[index].stat().st_size
                except OSError:
                    continue  # gone since it was listed: not a file of this folder any more
                unfit.append(paths[index].name)
                files.append(ScannedFile(path=str(paths[index]), name=paths[index].name,
                                         size=size))
                done += 1
            # Planned in order, then measured two at a time (#571): `inspect.AT_ONCE` children
            # may run at once, and samples went one after another. Results are taken in the
            # order planned, never in the order they finish, so the output is the same.
            plan = []
            for name, indexes in grouped.samples:
                chosen = [paths[i] for i in indexes]
                try:
                    stats = [p.stat() for p in chosen]
                except OSError:
                    continue  # gone since it was listed: not a sample
                key = _key(digest, chosen, stats)
                plan.append((name, chosen, tuple(st.st_size for st in stats), key,
                             measured.get(key)))

            def measure(entry):
                _, chosen, sizes, _, _ = entry
                try:
                    heads = [(p.name, _head(p, inspect.HEAD_BYTES)) for p in chosen]
                except OSError:
                    return None  # gone, or not a regular file any more: not a sample
                return inspect.inspect_sample(heads, stack, None, sizes=sizes)

            pool = ThreadPoolExecutor(max_workers=inspect.AT_ONCE)
            try:
                results = pool.map(measure, [e for e in plan if e[4] is None])
                for entry in plan:
                    name, chosen, sizes, key, kept = entry
                    if kept is not None:
                        # Unchanged since it was measured: its facts are still what it measures.
                        samples.append(StoredSample(**{**kept, "name": name,
                                                       "left_out": name in left_out}))
                        files += [ScannedFile(path=str(p), name=p.name, size=s, sample=name,
                                              recognised=kept["type_id"])
                                  for p, s in zip(chosen, sizes, strict=True)]
                        done += len(chosen)
                        continue
                    found = next(results)
                    if found is None:
                        continue
                    if found.type_id is None:
                        # Nothing reads it: listed with the other unread files, not a sample.
                        unfit += [p.name for p in chosen]
                        files += [ScannedFile(path=str(p), name=p.name, size=s)
                                  for p, s in zip(chosen, sizes, strict=True)]
                        done += len(chosen)
                        continue
                    samples.append(StoredSample(
                        name=name, files=[str(p) for p in chosen], outcome=found.outcome,
                        type_id=found.type_id, left_out=name in left_out, key=key,
                        facts=[SampleFact(measurement=f.measurement, value=f.value,
                                          coverage=f.coverage, pieces=list(f.pieces))
                               for f in found.facts if f.undetermined is None]))
                    files += [ScannedFile(path=str(p), name=p.name, size=s, sample=name,
                                          recognised=found.type_id)
                              for p, s in zip(chosen, sizes, strict=True)]
                    done += len(chosen)
                    # At most twice a second (#573): a transaction per sample was most of a
                    # reused scan's time, and the page polls every 2 s.
                    if time.monotonic() - said_at >= 0.5:
                        said_at = time.monotonic()
                        _save(draft_id, revision,
                              scan=Scan(state="scanning", done=done, total=total).model_dump())
            finally:
                # A stale or failed scan starts no more children than are already running.
                pool.shutdown(wait=True, cancel_futures=True)
        _save(draft_id, revision, files=[f.model_dump() for f in files],
              samples=[s.model_dump(mode="json") for s in samples], unfit=unfit)
        decisions.data_changed(draft_id)
        _save(draft_id, revision, scan=Scan(state="done", done=done, total=total,
                                            examples=examples,
                                            finished_at=datetime.now(UTC).isoformat()).model_dump())
    except _Stale:
        raise
    except Exception as failed:  # noqa: BLE001 — a scan says what went wrong, never hangs
        # What another selection found is not this one's: a failed scan shows nothing found.
        _save(draft_id, revision, files=[], samples=[], unfit=[],
              scan=Scan(state="failed", error=str(failed)[:500]).model_dump())


def finished(draft_id: str, revision: int) -> bool:
    """Whether the scan for `revision` is the newest and finished well."""
    with session_scope() as db:
        row = db.get(AnalysisData, draft_id)
        return bool(row and row.revision == revision and (row.scan or {}).get("state") == "done")


def sweep_interrupted() -> int:
    """Scans a worker lost (restarted, or timed out) say so, rather than reading for ever. Run when
    the worker starts: no scan of its own is running yet. Returns how many."""
    with session_scope() as db:
        rows = [r for r in db.query(AnalysisData).all()
                if (r.scan or {}).get("state") == "scanning"]
        for row in rows:
            row.scan = Scan(state="failed",
                            error="the scan was interrupted; press Read again").model_dump()
        return len(rows)

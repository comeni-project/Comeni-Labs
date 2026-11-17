"""Apply data choices to saved measurements, reading only files whose pairing changes."""

from pathlib import Path

from fastapi import HTTPException

from mendel_api.authoring.types import SampleFact
from mendel_api.db import session_scope
from mendel_api.models import AnalysisData
from mendel_api.services import decisions, inspect, registry
from mendel_api.services.data import roots, rule
from mendel_api.services.data.rule import Fix, Rule
from mendel_api.services.data.scan import _head
from mendel_api.services.data.types import DataSample
from mendel_api.settings import settings


def _regroup(row: AnalysisData) -> None:
    """Use the saved inventory; unchanged file groups retain their measured facts."""
    cached = {tuple(s["files"]): s for s in row.samples or []}
    files = {f["path"]: dict(f) for f in row.files or []}
    unreadable = {path for path, f in files.items() if not f.get("recognised")}
    folders: dict[str, list[str]] = {}
    for path, found in files.items():
        if found.get("used_as"):
            continue
        found.update(sample=None, recognised=None)
        folders.setdefault(str(Path(path).parent), []).append(path)
    reading = Rule(**row.rule) if row.rule else Rule()
    fixes = [Fix(**f) for f in row.fixes or []]
    left_out = {f.sample for f in fixes if f.kind == "leave_out"}
    taken: set[str] = set()
    samples, unfit, examples = [], [], []
    for paths in folders.values():
        paths.sort(key=lambda p: Path(p).name)
        grouped = rule.group([Path(p).name for p in paths], reading, fixes, taken)
        examples.extend(grouped.examples[: 3 - len(examples)])
        unfit.extend(Path(paths[i]).name for i in grouped.unfit)
        for name, indexes in grouped.samples:
            chosen = [paths[i] for i in indexes]
            prior = cached.get(tuple(chosen))
            if prior is None and len(chosen) == 1 and chosen[0] in unreadable:
                unfit.append(Path(chosen[0]).name)
                continue
            if prior is not None:
                sample = {**prior, "name": name, "left_out": name in left_out}
            else:
                # Only a newly paired/split sample needs measuring. No directory traversal or
                # reads of other samples; paths are rechecked before opening affected files.
                safe = [roots.inside_roots(path, settings.data_roots) for path in chosen]
                sizes = tuple(p.stat().st_size for p in safe)
                found = inspect.inspect_sample(
                    [(p.name, _head(p, inspect.HEAD_BYTES)) for p in safe],
                    registry.stack(),
                    None,
                    sizes=sizes,
                )
                if found.type_id is None:
                    unfit.extend(p.name for p in safe)
                    continue
                sample = DataSample(
                    name=name,
                    files=chosen,
                    outcome=found.outcome,
                    type_id=found.type_id,
                    left_out=name in left_out,
                    facts=[
                        SampleFact(
                            measurement=f.measurement,
                            value=f.value,
                            coverage=f.coverage,
                            pieces=list(f.pieces),
                        )
                        for f in found.facts
                        if f.undetermined is None
                    ],
                ).model_dump(mode="json")
            samples.append(sample)
            for path in chosen:
                files[path].update(sample=name, recognised=sample["type_id"])
    row.samples, row.files, row.unfit = samples, list(files.values()), unfit
    row.scan = {**row.scan, "examples": examples}


def change(draft_id: str, *, fix: Fix | None = None, undo: int | None = None) -> AnalysisData:
    """Serialize edits; identical retries are no-ops, and active scans cannot overwrite edits."""
    with session_scope() as db:
        row = db.get(AnalysisData, draft_id, with_for_update=True)
        if row is None:
            raise HTTPException(404, f"no data for {draft_id}")
        fixes = [Fix(**f) for f in row.fixes or []]
        if fix is not None and any(
            (f.kind, f.sample, f.file, f.measurement)
            == (fix.kind, fix.sample, fix.file, fix.measurement)
            for f in fixes
        ):
            return row
        if (row.scan or {}).get("state") == "scanning":
            raise HTTPException(
                409, "Wait for the current file read to finish before changing samples."
            )
        if fix is not None:
            rule.validate(fix, list(row.samples or []), list(row.unfit or []))
            changed = fix
            fixes.append(fix)
        else:
            if undo is None or not 0 <= undo < len(fixes):
                raise HTTPException(404, f"no fix {undo}")
            changed = fixes[undo]
            # Old versions could append an identical choice repeatedly. Undo that logical
            # choice once, including those retries, while preserving other changes.
            fixes = [f for f in fixes if f != changed]
        row.fixes = [f.model_dump() for f in fixes]
        if changed.kind == "use_file":
            _regroup(row)
        else:
            left_out = {f.sample for f in fixes if f.kind == "leave_out"}
            row.samples = [{**s, "left_out": s["name"] in left_out} for s in row.samples or []]
        row.revision = (row.revision or 0) + 1
        db.flush()
    decisions.data_changed(draft_id)
    return row

"""What a folder looks like before it is ticked (#511, the board of 2026-11-16): its files
counted by the kind their extension names. A format reader names the kinds it reads; a
study-wide type is named by its own suffix (`annotation.gtf` → `.gtf`). In a folder named for
references, a file a reader would take as a sample is the study's instead: a genome, not an
assembly. Extensions only — nothing is opened."""

import os
from collections import Counter
from pathlib import Path

from pydantic import BaseModel

from mendel_api.services import registry
from mendel_api.services.data.roots import Looks
from mendel_api.services.data.scan import REFERENCE_FOLDERS


class RuleRowView(BaseModel):
    when: dict[str, str]
    then: str | None


class FactRule(BaseModel):
    """A decision that reads this fact: which role it fills, and its rows."""

    role: str
    rows: list[RuleRowView]


class FactSetting(BaseModel):
    """A setting worked out from this fact, as a formula a person reads."""

    name: str
    formula: str


class ReaderFact(BaseModel):
    measurement: str
    unit: str | None = None
    description: str | None = None
    rules: list[FactRule] = []
    settings: list[FactSetting] = []
    tests: list[str] = []
    """The cases its tests check, by their names."""


class Reader(BaseModel):
    """**A reader and what it measures** (Registry · Measurers, board 7b): a format our code reads
    as data is read, or a tool's output read in the run; each fact it makes, the rules and settings
    that decide by it, and its tests."""

    id: str
    type_id: str
    """What it reads: a data type for a format reader, a tool's output for a tool's."""
    by: str
    """`code` (our code, on this server and in the run) or `tool` (a tool's output, in the run)."""
    uses: str | None = None
    extensions: list[str]
    compressed: list[str]
    """Compression it reads through, the same for every reader (`.gz`)."""
    runs: list[str]
    measures: list[str]
    facts: list[ReaderFact] = []


Tables = tuple[list[tuple[str, str, frozenset[str]]], dict[str, str], tuple[str, ...]]


def _tables() -> Tables:
    stack = registry.stack()
    codecs = tuple(
        sorted(
            {e.lower() for c in stack.inspection.codecs.values() for e in c.extensions},
            key=len,
            reverse=True,
        )
    )
    readers = [
        (e.lower(), f.reads[0], frozenset(x.lower() for x in f.extensions))
        for f in stack.inspection.formats.values()
        if f.reads
        for e in f.extensions
    ]
    readers.sort(key=lambda r: -len(r[0]))
    study = {
        "." + t.rsplit(".", 1)[-1]: t
        for t, grain in sorted(stack.vocabulary.grains.items())
        if str(grain) == "study"
    }
    return readers, study, codecs


def kind_of(name: str, *, reference_folder: bool, tables: Tables) -> str | None:
    readers, study, codecs = tables
    lower = name.lower()
    # A compressed file is its kind under the compression: `L01_R1.fastq.gz` is FASTQ.
    lower = next((lower[: -len(c)] for c in codecs if lower.endswith(c)), lower)
    for ext, type_id, family in readers:
        if lower.endswith(ext):
            if reference_folder:
                return next((study[e] for e in sorted(family) if e in study), type_id)
            return type_id
    return next((t for ext, t in study.items() if lower.endswith(ext)), None)


def looks_like(folder: Path) -> list[Looks]:
    tables = _tables()
    reference = folder.name.lower() in REFERENCE_FOLDERS
    try:
        with os.scandir(folder) as entries:
            names = [e.name for e in entries if e.is_file() and not e.name.startswith(".")]
    except OSError:
        return []
    counted = Counter(
        k for n in names if (k := kind_of(n, reference_folder=reference, tables=tables))
    )
    return [Looks(type_id=t, count=c) for t, c in sorted(counted.items())]


_OPS = {
    "log2": "log₂({x})",
    "divide": "{x} / {by}",
    "subtract": "{x} − {by}",
    "add": "{x} + {by}",
    "multiply": "{x} × {by}",
    "at_most": "min({by}, {x})",
    "at_least": "max({by}, {x})",
    "round": "round({x})",
}


def _formula(source: str, transforms) -> str:
    """`min(14, log₂(genome length) / 2 − 1)` from a derivation's steps, as a person reads it."""
    x = source.replace("_", " ")
    for step in transforms:
        by = (
            ""
            if step.by is None
            else (str(int(step.by)) if float(step.by).is_integer() else str(step.by))
        )
        x = _OPS.get(str(step.op), f"{step.op}({{x}})").format(x=x, by=by)
    return x


def _tests(measurer_id: str) -> list[str]:
    """The test cases a measurer's own tests check, by name (`test_uniform_150_is_decided` →
    "uniform 150 is decided")."""
    import re

    stack = registry.stack()
    names: list[str] = []
    for root in stack.paths:
        for test in sorted(
            (Path(root) / "measurers" / "measures" / measurer_id).glob("piece/test_*.py")
        ):
            names += [
                m.replace("_", " ")
                for m in re.findall(r"^def test_(\w+)\(", test.read_text(), re.M)
            ]
    return names


def _fact(measurement: str, measurer_id: str) -> ReaderFact:
    stack = registry.stack()
    declared = stack.measurements.get(measurement) if hasattr(stack.measurements, "get") else None
    rules = [
        FactRule(
            # Every role it decides, not the first (#535): a rule may decide several.
            role=", ".join(sorted({str(t.of) for t in (
                d.decides if isinstance(d.decides, list) else [d.decides])})),
            rows=[
                RuleRowView(
                    when={k: str(v) for k, v in row.when.items()},
                    then=None if row.then is None else str(row.then),
                )
                for row in d.rows
            ],
        )
        for d in stack.rules.decisions
        if any(measurement in row.when or f"fact.{measurement}" in row.when for row in d.rows)
    ]
    settings = [
        FactSetting(name=d.fact, formula=_formula(d.source, d.transform or []))
        for d in stack.rules.derivations
        if d.source == measurement
    ]
    return ReaderFact(
        measurement=measurement,
        unit=getattr(declared, "unit", None),
        description=getattr(declared, "description", None),
        rules=rules,
        settings=settings,
        tests=_tests(measurer_id),
    )


def readers() -> list[Reader]:
    inspection = registry.stack().inspection
    compressed = sorted({e for c in inspection.codecs.values() for e in c.extensions})
    found: list[Reader] = []
    for f in sorted(inspection.formats.values(), key=lambda f: f.id):
        if not f.reads:
            continue
        measurers = sorted(
            (
                m
                for m in inspection.measurers.values()
                if m.record == f.record and str(m.by) == "code"
            ),
            key=lambda m: m.measures,
        )
        runs = sorted(
            {str(r) for m in measurers for r in m.runs} or {"server"},
            key=["server", "pipeline"].index,
        )
        found.append(
            Reader(
                id=f.id,
                type_id=f.reads[0],
                by="code",
                extensions=list(f.extensions),
                compressed=compressed,
                runs=runs,
                measures=[m.measures for m in measurers],
                facts=[_fact(m.measures, m.id) for m in measurers],
            )
        )
    for m in sorted(
        (m for m in inspection.measurers.values() if str(m.by) == "tool"), key=lambda m: m.id
    ):
        found.append(
            Reader(
                id=m.id,
                type_id=str(m.output or ""),
                by="tool",
                uses=m.uses,
                extensions=[],
                compressed=[],
                runs=[str(r) for r in m.runs],
                measures=[m.measures],
                facts=[_fact(m.measures, m.id)],
            )
        )
    return found

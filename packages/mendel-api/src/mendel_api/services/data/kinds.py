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


class Reader(BaseModel):
    """A format reader: what it reads, from which extensions, and what it measures there."""

    id: str
    type_id: str
    extensions: list[str]
    compressed: list[str]
    """Compression it reads through, the same for every reader (`.gz`)."""
    measures: list[str]


Tables = tuple[list[tuple[str, str, frozenset[str]]], dict[str, str], tuple[str, ...]]


def _tables() -> Tables:
    stack = registry.stack()
    codecs = tuple(sorted({e.lower() for c in stack.inspection.codecs.values()
                           for e in c.extensions}, key=len, reverse=True))
    readers = [(e.lower(), f.reads[0], frozenset(x.lower() for x in f.extensions))
               for f in stack.inspection.formats.values() if f.reads for e in f.extensions]
    readers.sort(key=lambda r: -len(r[0]))
    study = {"." + t.rsplit(".", 1)[-1]: t for t, grain in sorted(stack.vocabulary.grains.items())
             if str(grain) == "study"}
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
    counted = Counter(k for n in names
                      if (k := kind_of(n, reference_folder=reference, tables=tables)))
    return [Looks(type_id=t, count=c) for t, c in sorted(counted.items())]


def readers() -> list[Reader]:
    inspection = registry.stack().inspection
    compressed = sorted({e for c in inspection.codecs.values() for e in c.extensions})
    return [Reader(id=f.id, type_id=f.reads[0], extensions=list(f.extensions),
                   compressed=compressed,
                   measures=sorted(m.measures for m in inspection.measurers.values()
                                   if m.record == f.record and str(m.by) == "code"))
            for f in sorted(inspection.formats.values(), key=lambda f: f.id) if f.reads]

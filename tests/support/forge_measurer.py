"""The `genome_length_fai` measurer as forge items (#487): what the AI would draft for
`samtools faidx`, read from the registry's own hand-written piece so the two cannot drift."""

import shutil
from pathlib import Path

from support.paths import REGISTRY

PIECE = REGISTRY / "measurers" / "measures" / "genome_length_fai" / "piece"
FAIDX = "nf-core/samtools/faidx@1.24"
KEY = "measurers:measurer:genome_length_fai"
OURS = "measurers/measures/genome_length_fai"


def registry_before(root: Path) -> Path:
    """A copy of the registry before `genome_length_fai` existed: a re-forge refuses to draft a
    measurer the registry already has, and these tests draft that one."""
    before = root / "registry-before"
    shutil.copytree(REGISTRY, before, ignore=shutil.ignore_patterns(".git"))
    shutil.rmtree(before / OURS)
    return before


def measurer() -> dict:
    """The item's value. The tests import the module by the measurer's id, as a drafted
    measurer's do: its entry is `piece/<id>.py`."""
    return {
        "measures": "genome_length",
        "output": "fai",
        "explain": "samtools faidx writes one line per sequence, its length second; the sum.",
        "code": (PIECE / "fai.py").read_text(),
        "tests": (PIECE / "test_fai.py").read_text()
        .replace("import fai\n", "import genome_length_fai as fai\n"),
    }

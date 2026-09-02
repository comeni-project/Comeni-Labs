"""Where the repository is, from anywhere under `tests/`.

Every test file used to spell this as `Path(__file__).parent.parent`, which is a claim about
how deep the file sits. It was true while `tests/` was flat and became false the moment a file
moved — so the depth lives in one place and the files ask for a name instead.
"""

from __future__ import annotations

import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[2]
"""The repository root — the directory holding `packages/`, `registry/` and `Makefile`."""

TESTS = ROOT / "tests"
REGISTRY = ROOT / "registry"
FIXTURES = TESTS / "fixtures"
GOLDEN = TESTS / "golden"
EXAMPLES = ROOT / "examples"
PACKAGES = ROOT / "packages"

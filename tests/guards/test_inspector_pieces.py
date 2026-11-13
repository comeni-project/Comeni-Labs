"""Check the import and filesystem boundaries of shipped inspector pieces.

The closed import allowlist catches ordinary access to networks, files, and processes. This static
guard is a tripwire rather than a Python sandbox; runtime isolation comes from the short-lived
inspection process, and operators still choose which registry layers to trust.
"""

import pytest
from mendel_compiler.registry_lint import piece_code, piece_problems
from support.paths import ROOT

INSPECTORS = ROOT / "registry" / "measurers"
PIECES = sorted(p for p in INSPECTORS.glob("*/*") if p.is_dir() and p.name != "__pycache__")
CODE = piece_code(ROOT / "registry")
"""The allowlist and the walk live in `mendel lint` (MD0027, #487), so the forge's drafts, its
publish check and the registry's CI hold a piece to the same rules this guard does."""


def test_there_are_pieces():
    assert PIECES, "no pieces found: the loops below would assert nothing"
    assert CODE, "no piece code found: the allowlist below would assert nothing"


@pytest.mark.parametrize("piece", PIECES, ids=lambda p: f"{p.parent.name}/{p.name}")
def test_a_piece_has_its_declaration_code_and_tests(piece):
    assert len(list(piece.glob("*.yml"))) == 1, "one declaration per piece"
    assert [p for p in (piece / "piece").glob("*.py") if not p.name.startswith("test_")]
    tests = list((piece / "piece").glob("test_*.py"))
    assert tests and any("def test_" in t.read_text() for t in tests)


@pytest.mark.parametrize("code", CODE, ids=lambda p: str(p.relative_to(INSPECTORS)))
def test_a_piece_imports_only_the_allowlist(code):
    """The gzip codec *defines* a function called `open`; a definition is not a call and is
    not matched. Every `.py` under `piece/`, in subfolders too, since an entry may sit in one."""
    reached = piece_problems(code.read_text())
    assert not reached, f"{code.name} reaches past the allowlist: {reached}"

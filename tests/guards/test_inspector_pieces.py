"""Every inspector piece in the shipped registry keeps the rules (spec §3).

**A closed import allowlist**, the shape `test_purity.py` uses for `comeni-core`: a piece reads
only the stream it is handed, so it imports nothing that reaches a network, a file or a process.
"""

import ast

import pytest
from support.paths import ROOT

INSPECTORS = ROOT / "registry" / "inspectors"
PIECES = sorted(p for p in INSPECTORS.glob("*/*") if p.is_dir() and p.name != "__pycache__")
ALLOWED = {"comeni_inspect", "gzip", "zlib", "io", "re", "math", "collections", "typing"}
CODE = sorted(
    p
    for p in INSPECTORS.glob("*/*/piece/*.py")
    if not p.name.startswith("test_")
)


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
    """`open`, `exec`, `eval` and `__import__` called as builtins are banned too. The gzip
    codec *defines* a function called `open`; a definition is not a call and is not matched."""
    names = set()
    for node in ast.walk(ast.parse(code.read_text())):
        if isinstance(node, ast.Import):
            names |= {alias.name.split(".")[0] for alias in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module.split(".")[0])
        elif isinstance(node, ast.Call) and getattr(node.func, "id", "") in {
            "__import__", "open", "exec", "eval", "compile",
        }:
            names.add(f"<{node.func.id}()>")
    assert names <= ALLOWED, f"{code.name} reaches past the allowlist: {sorted(names - ALLOWED)}"

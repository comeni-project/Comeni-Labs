"""Every inspector piece in the shipped registry keeps the rules (spec §3).

**A closed import allowlist**, the shape `test_purity.py` uses for `comeni-core`: a piece reads
only the stream it is handed, so it imports nothing that reaches a network, a file or a process.

**A tripwire, not a sandbox.** Python cannot be confined by reading its source; this catches the
ordinary ways a piece would reach out, so that doing it takes intent. The sandbox is the process
an inspection runs in (14.7.6.4), and pieces load only from layers an operator trusts.
"""

import ast

import pytest
from support.paths import ROOT

INSPECTORS = ROOT / "registry" / "inspectors"
PIECES = sorted(p for p in INSPECTORS.glob("*/*") if p.is_dir() and p.name != "__pycache__")
ALLOWED = {
    "comeni_inspect.outcome", "comeni_inspect.records",
    "gzip", "zlib", "io", "re", "math", "collections", "collections.abc", "typing",
}
"""Module names, whole. `comeni_inspect` itself is not on it: its runner loads any file by path
and its harness runs commands, so a piece may import only the two shapes it answers in."""
BANNED_CALLS = {"open", "getattr", "setattr", "__import__", "exec", "eval", "compile", "vars"}
"""Builtins a piece may not call by name."""
BANNED_METHODS = {"open"}
"""And as an attribute: `io.open(...)` and `gzip.open(path)` are file reads too. Only `open`,
because `re.compile` is not the builtin."""
BANNED_NAMES = {"__builtins__", "__subclasses__", "__globals__", "__code__", "__loader__"}
CODE = sorted(
    p
    for p in INSPECTORS.glob("*/*/piece/**/*.py")
    if not p.name.startswith("test_") and "fixtures" not in p.relative_to(INSPECTORS).parts
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


def _reaches(code) -> set[str]:
    found = set()
    for node in ast.walk(ast.parse(code.read_text())):
        if isinstance(node, ast.Import):
            found |= {alias.name for alias in node.names} - ALLOWED
        elif isinstance(node, ast.ImportFrom):
            if node.level or (node.module or "") not in ALLOWED:
                found.add(node.module or "<relative import>")
        elif isinstance(node, ast.Call):
            name = getattr(node.func, "id", None)
            method = getattr(node.func, "attr", None)
            if name in BANNED_CALLS or method in BANNED_METHODS:
                found.add(f"<{name or method}()>")
        elif isinstance(node, ast.Name) and node.id in BANNED_NAMES:
            found.add(node.id)
        elif isinstance(node, ast.Attribute) and node.attr in BANNED_NAMES:
            found.add(node.attr)
    return found


@pytest.mark.parametrize("code", CODE, ids=lambda p: str(p.relative_to(INSPECTORS)))
def test_a_piece_imports_only_the_allowlist(code):
    """The gzip codec *defines* a function called `open`; a definition is not a call and is
    not matched. Every `.py` under `piece/`, in subfolders too, since an entry may sit in one."""
    reached = _reaches(code)
    assert not reached, f"{code.name} reaches past the allowlist: {sorted(reached)}"

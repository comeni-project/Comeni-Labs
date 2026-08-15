"""How much of A14 is left, counted per **guard** rather than per file.

A69 (issue #33): the ledger's residue was tracked per file, and by that measure 46 of 47 test
files were covered — so A14 read as nearly closed while three of its four guarded invariants
fell in one audit round. Its actual condition is per guard, a guard being a test whose purpose
is to refuse something, and counted that way roughly a fifth had a recorded revert.

**The point is that the number is derived, not asserted.** `CLAUDE.md` says no count is
repeated in it because two counts were stale for three plans, and the ledger is the thing that
can be counted. This is what counts it.

Not a gate. A14 is open by design and a target that fails CI would be a target somebody
deletes; `make residue` prints it, and the ledger is where the work is recorded.
"""

import ast
import pathlib
import sys

ROOT = pathlib.Path(__file__).parent.parent
LEDGER = ROOT / "docs" / "internal" / "audits" / "guard-ledger.md"

REFUSAL_MARKERS = ("pytest.raises", "== []", "assert not ", "is None", "DID NOT RAISE")
"""What makes a test a *guard*: it refuses something.

A heuristic, and it is allowed to be one — A69's own text says the exact numbers are not the
point and the order-of-magnitude gap is. What would not be allowed is a heuristic presented as
a count, which is why this prints both halves and the file list.
"""


def _test_files() -> list[pathlib.Path]:
    found = sorted((ROOT / "tests").rglob("test_*.py"))
    for package in sorted((ROOT / "packages").iterdir()):
        found += sorted((package / "tests").rglob("test_*.py"))
    return found


def _guards(path: pathlib.Path) -> list[str]:
    """Every refusal-shaped test function in this file."""
    tree = ast.parse(path.read_text())
    found = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef) or not node.name.startswith("test_"):
            continue
        body = ast.get_source_segment(path.read_text(), node) or ""
        if any(marker in body for marker in REFUSAL_MARKERS):
            found.append(node.name)
    return found


def main() -> int:
    ledger = LEDGER.read_text()
    total = watched = 0
    uncovered: dict[str, list[str]] = {}
    for path in _test_files():
        names = _guards(path)
        total += len(names)
        missing = [name for name in names if name not in ledger]
        watched += len(names) - len(missing)
        if missing:
            uncovered[str(path.relative_to(ROOT))] = missing
    print(f"guards: {total}    watched failing: {watched}    residue: {total - watched}")
    print(f"        {watched * 100 // max(total, 1)}% of A14's condition, counted per guard")
    if "--list" in sys.argv:
        for where, names in sorted(uncovered.items()):
            print(f"\n{where}  ({len(names)})")
            for name in names:
                print(f"  {name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

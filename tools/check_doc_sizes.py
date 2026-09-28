"""A line budget for the files every session reads first (#118). Compact, don't raise it.

`CLAUDE.md` reached 1,441 lines by accretion, each addition reasonable on its own. A number that
fails the build is the only thing that has ever stopped that in this repository: the rules for
what goes where are in `docs/notes/compaction.md`, and this is what makes them get read.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BUDGETS = {"CLAUDE.md": 300, "docs/notes/now.md": 150}


def over_budget(root: Path, budgets: dict[str, int]) -> list[tuple[str, int, int]]:
    out = []
    for name, limit in budgets.items():
        path = root / name
        if path.exists():
            lines = len(path.read_text().splitlines())
            if lines > limit:
                out.append((name, lines, limit))
    return out


def main() -> int:
    over = over_budget(ROOT, BUDGETS)
    for name, lines, limit in over:
        print(f"{name} is {lines} lines, over its budget of {limit}. Compact it "
              "(docs/notes/compaction.md); don't raise the limit.")
    return 1 if over else 0


if __name__ == "__main__":
    sys.exit(main())

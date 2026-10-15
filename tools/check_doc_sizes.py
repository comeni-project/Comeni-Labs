"""Report files exceeding the configured line budgets.

Checks CLAUDE.md and docs/notes/now.md without modifying them. The limits keep frequently
loaded guidance concise; move supporting detail to its documentation home when compacting."""

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

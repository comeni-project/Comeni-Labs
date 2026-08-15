"""Every relative markdown link in `docs/` and the root resolves to a file that exists.

Nothing checked this before issue #41, which is why the move it was written for is worth doing
*with* a checker rather than without one: a mechanical repair verified by hand is a repair
nobody can re-verify next time.

**Two scoping decisions, both learned by running it first.**

Fenced code blocks are skipped. `assert x == [actual, expected]` is not a link, and a first
draft reported eleven of them — a checker whose output is mostly noise is a checker people stop
reading.

`notes/` is not checked, only `docs/` and the root. A plan naming a file its own tasks create is
*correct* at the moment it executes and broken until then, so checking the record would make
`make check` red for the duration of every plan. The cost of a broken link also differs by
audience: in `docs/` a reader hits a 404, and in `notes/` a future reader meets a dated document
that already says it describes work not yet done.

Anchors (`#section`) are not checked — that needs a markdown parser, and the failure mode is a
reader scrolling rather than a reader hitting a 404.
"""

import pathlib
import re

ROOT = pathlib.Path(__file__).parent.parent
LINK = re.compile(r"\[[^\]]*\]\((?!https?:|mailto:|#)([^)#]+)")


def _prose(text: str) -> str:
    """The file with fenced code blocks blanked out."""
    kept, fenced = [], False
    for line in text.splitlines():
        if line.lstrip().startswith("```"):
            fenced = not fenced
            continue
        kept.append("" if fenced else line)
    return "\n".join(kept)


def _markdown() -> list[pathlib.Path]:
    return sorted((ROOT / "docs").rglob("*.md")) + sorted(ROOT.glob("*.md"))


def broken() -> list[str]:
    found = []
    for path in _markdown():
        for target in LINK.findall(_prose(path.read_text())):
            if not (path.parent / target.strip()).exists():
                found.append(f"{path.relative_to(ROOT)} -> {target.strip()}")
    return found


def main() -> int:
    found = broken()
    for line in found:
        print(line)
    print(f"{len(found)} broken link(s) in docs/ and the root")
    return 1 if found else 0


if __name__ == "__main__":
    raise SystemExit(main())

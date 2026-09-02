"""Every relative markdown link in `docs/`, `.github/`, `.design/` and the root resolves.

Nothing checked this before issue #41, which is why the move it was written for is worth doing
*with* a checker rather than without one: a mechanical repair verified by hand is a repair
nobody can re-verify next time.

**Two scoping decisions, both learned by running it first.**

Fenced code blocks are skipped. `assert x == [actual, expected]` is not a link, and a first
draft reported eleven of them — a checker whose output is mostly noise is a checker people stop
reading.

`.github/` and `.design/` are checked, both added 2026-09-02 when the sanitization moved files
into them. `.design/`'s four READMEs are the index of every design canvas and the record of the
Artifact URL each was published at — and moving three directories there broke three of their
links at once, none of which any gate could see. A directory whose whole job is pointing at
things is the last place to leave unchecked.
That move was only safe *because* the checker followed them: a community health file is one
GitHub renders and a stranger reads, so its links have exactly the audience the paragraph below
says `docs/` has, and leaving them unchecked would have traded a tidier root for a page of dead
links nobody would notice.

`notes/` is not checked, only `docs/`, `.github/` and the root. A plan naming a file its own
tasks create is *correct* at the moment it executes and broken until then, so checking it makes
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
    return (
        sorted((ROOT / "docs").rglob("*.md"))
        + sorted((ROOT / ".github").rglob("*.md"))
        + sorted((ROOT / ".design").rglob("*.md"))
        + sorted(ROOT.glob("*.md"))
    )


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
    print(f"{len(found)} broken link(s) in docs/, .github/, .design/ and the root")
    return 1 if found else 0


if __name__ == "__main__":
    raise SystemExit(main())

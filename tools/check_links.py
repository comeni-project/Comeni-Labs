"""Check local Markdown link targets in maintained docs and repository entry points.

Scan docs/, .github/, .design/ and root Markdown files. Exclude working notes and plans,
whose historical or forward references are deliberate. Links to gitignored generated
pages under docs/ are exempt; the strict site build checks the generated catalogue.
This exemption cannot detect a typo inside the generated tree until the site is built.
Section anchors are not checked. External links are outside this local check.
"""

import pathlib
import re
import subprocess

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


# Provenance, both of them: the notes are append-only history, and the specs link forward to
# plans that may not exist yet. Neither is published, so a stale link inside them costs a
# future reader a moment rather than costing a user a 404.
EXCLUDED = (ROOT / "docs" / "notes", ROOT / "docs" / "superpowers")


def _markdown() -> list[pathlib.Path]:
    return (
        [
            p
            for p in sorted((ROOT / "docs").rglob("*.md"))
            if not any(e in p.parents for e in EXCLUDED)
        ]
        + sorted((ROOT / ".github").rglob("*.md"))
        + sorted((ROOT / ".design").rglob("*.md"))
        + sorted(ROOT.glob("*.md"))
    )


DOCS = ROOT / "docs"


def _generated(paths: set[pathlib.Path]) -> set[pathlib.Path]:
    """Of `paths`, the ones a make target writes — asked of git, in one call.

    **Absent is not the same as ignored**, which is the whole distinction: a page that will be
    rendered into a checkout is ignored, and a page somebody deleted or misspelled is not.

    Returns nothing rather than raising when git cannot answer. A checker that dies because it
    is being run outside a checkout is worse than one that reports a generated page as broken,
    and the tests below are what stop that degradation from being silent.
    """
    under_docs = sorted(p for p in paths if DOCS in p.parents)
    if not under_docs:
        return set()
    try:
        result = subprocess.run(
            ["git", "-C", str(ROOT), "check-ignore", "--stdin"],
            # Feed repository-relative paths. Git's stdin interface treats absolute paths
            # differently across versions and runner environments; relative paths also make
            # the output stable to parse below.
            input="\n".join(p.relative_to(ROOT).as_posix() for p in under_docs),
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return set()
    # `check-ignore` exits 1 when nothing matched, which is an ordinary answer and not an error.
    if result.returncode not in (0, 1):
        return set()
    return {(ROOT / line).resolve() for line in result.stdout.splitlines() if line}


def broken() -> list[str]:
    seen: list[tuple[pathlib.Path, str, pathlib.Path]] = []
    for path in _markdown():
        for raw in LINK.findall(_prose(path.read_text())):
            target = raw.strip()
            resolved = path.parent / target
            if not resolved.exists():
                seen.append((path, target, resolved.resolve()))
    generated = _generated({resolved for _, _, resolved in seen})
    return [
        f"{path.relative_to(ROOT)} -> {target}"
        for path, target, resolved in seen
        if resolved not in generated
    ]


def main() -> int:
    found = broken()
    for line in found:
        print(line)
    print(f"{len(found)} broken link(s) in docs/, .github/, .design/ and the root")
    return 1 if found else 0


if __name__ == "__main__":
    raise SystemExit(main())

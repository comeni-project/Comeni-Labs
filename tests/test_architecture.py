"""Every path `ARCHITECTURE.md` names exists.

The whole argument for grouping `comeni-core` by lifecycle stage is that a reader's document
and their directory agree — so the document naming a directory that is not there is the one
failure that would make the grouping pointless.

Prose that names a path is prose that goes stale. That is what `CLAUDE.md`'s two stale counts
were (A71, A72), what `registry.yml:kinds` was until Plan 1.15, and what
`check_registry_drift.py`'s hand-written `KINDS` was until it could not see `roles/`. The
answer each time was the same: derive it, or check it.

Issue #41.
"""

import pathlib
import re

ROOT = pathlib.Path(__file__).parent.parent
SOURCE = ROOT / "packages"
PATH = re.compile(r"`((?:comeni_core|mendel_resolver|mendel_compiler)/[\w./]+)`")

PACKAGE_OF = {
    "comeni_core": "comeni-core",
    "mendel_resolver": "mendel-resolver",
    "mendel_compiler": "mendel-compiler",
}


def _resolve(named: str) -> pathlib.Path:
    package = PACKAGE_OF[named.split("/")[0]]
    return SOURCE / package / "src" / named


def test_every_path_architecture_names_exists():
    named = sorted(set(PATH.findall((ROOT / "ARCHITECTURE.md").read_text())))
    assert named, (
        "ARCHITECTURE.md names no module path at all — §1's `Lives in` column is how a reader "
        "gets from a stage to a directory, and it has gone"
    )
    missing = [name for name in named if not _resolve(name).exists()]
    assert missing == [], (
        "ARCHITECTURE.md names paths that do not exist:\n  " + "\n  ".join(missing)
    )


def test_the_five_packages_are_all_named():
    """A stage whose directory the document does not name is a stage a reader cannot find."""
    text = (ROOT / "ARCHITECTURE.md").read_text()
    missing = [
        f"comeni_core/{group}/"
        for group in ("declared", "goal", "plan", "artifact", "spell")
        if f"comeni_core/{group}/" not in text
    ]
    assert missing == [], f"ARCHITECTURE.md does not name these packages: {missing}"


def test_no_document_or_tool_still_says_docs_internal():
    """The working notes moved to `notes/` on 2026-08-16, and a stale reference to their old
    home is a link that goes nowhere or a tool that reads nothing.

    `make links` covers markdown links in `docs/` and the root. It cannot cover a path built
    from segments — `ROOT / "docs" / "internal" / "audits"` in `guard_residue.py` survived the
    move and nothing noticed, because `make residue` is not a gate. This is the check that
    sees both shapes.

    The plan for issue #41 is exempt: it *describes* the move, so `git mv docs/internal notes`
    appears in it correctly.
    """
    root = pathlib.Path(__file__).parent.parent
    exempt = {
        # describes the move, so `git mv docs/internal notes` appears in it correctly
        "notes/plans/2026-08-16-code-and-documentation-organisation.md",
        # says where the notes used to live, which is the point of saying it
        "notes/README.md",
        # holds the string it searches for
        "tests/test_architecture.py",
    }
    stale = []
    for pattern in ("*.md", "*.py"):
        for path in sorted(root.rglob(pattern)):
            relative = path.relative_to(root)
            # **Skipped by their position under `root`, not by `path.parts`.** The first
            # version tested `{".venv", ".worktrees", …} & set(path.parts)` — and this
            # repository's plans are executed in `.worktrees/<name>/`, so every path contained
            # `.worktrees` and the scan skipped the entire repository. It reported zero and
            # passed, including on a file that holds the string it searches for.
            #
            # Same defect as `make drift`'s `REGISTRY ?= ../comeni-registry`, which resolved to
            # `.worktrees/comeni-registry` and silently skipped: a check written against the
            # repository root is a check that does nothing in the one place `CLAUDE.md`
            # requires the work to happen.
            if {".venv", ".git", "node_modules", "build"} & set(relative.parts):
                continue
            if str(relative) in exempt:
                continue
            text = path.read_text()
            if "docs/internal" in text or '"docs" / "internal"' in text:
                stale.append(str(relative))
    assert stale == [], (
        "these still name `docs/internal`, which no longer exists:\n  " + "\n  ".join(stale)
    )

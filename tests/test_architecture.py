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
    # `notes/` is not scanned, for the same reason `make links` does not check it: the record
    # legitimately names things that no longer exist. The guard ledger's own row about this
    # move says `docs/internal`, correctly and for ever.
    #
    # What *is* scanned is everything a reader or a tool follows now: `docs/`, the root,
    # `packages/`, `tests/`, `tools/`.
    scanned = ("docs", "packages", "tests", "tools")
    exempt = {"tests/test_architecture.py"}  # holds the string it searches for
    paths = [
        path
        for top in scanned
        for pattern in ("*.md", "*.py")
        for path in sorted((root / top).rglob(pattern))
    ] + sorted(root.glob("*.md"))
    # A scan that reaches nothing reports nothing and passes. Emptying `scanned` was watched
    # doing exactly that, which is the same defect the comment above describes — so the count
    # is asserted rather than trusted.
    assert len(paths) > 100, f"the scan reached only {len(paths)} files; it is not scanning"

    stale = []
    for path in paths:
        relative = path.relative_to(root)
        # **Enumerated from named roots, not filtered out of an rglob of everything.** The
        # first version scanned the whole tree and skipped by `{".venv", ".worktrees", …} &
        # set(path.parts)` — and this repository's plans are executed in `.worktrees/<name>/`,
        # so every path contained `.worktrees`, the scan skipped the entire repository, and it
        # passed while sitting on a file that holds the string it searches for.
        #
        # Same defect as `make drift`'s `REGISTRY ?= ../comeni-registry`, which resolved to
        # `.worktrees/comeni-registry` and printed "skipped": a check written against the
        # repository root does nothing in the one place `CLAUDE.md` requires the work to
        # happen. Naming the roots removes the question rather than answering it carefully.
        if str(relative) in exempt:
            continue
        text = path.read_text()
        if "docs/internal" in text or '"docs" / "internal"' in text:
            stale.append(str(relative))
    assert stale == [], (
        "these still name `docs/internal`, which no longer exists:\n  " + "\n  ".join(stale)
    )


def test_every_documented_clone_command_gets_the_submodule():
    """A `git clone` in the docs without `--recurse-submodules` hands a stranger an empty
    `registry/`.

    `registry/` became a git submodule in issue #46. The refusal in `layers.load()` and the
    `make check` prerequisite both name the fix, so nobody is stuck — but a documented
    command that produces a broken checkout is a documented command that is wrong, and the
    person reading the README is the person least able to tell.

    Checked rather than trusted because this is prose, and the two places that were wrong
    after the move were both prose: the README's quickstart had no clone line at all, and
    its registry paragraph still called `registry/` "the copy here".
    """
    root = pathlib.Path(__file__).parent.parent
    offenders = []
    for path in sorted(root.glob("*.md")) + sorted((root / "docs").rglob("*.md")):
        for number, line in enumerate(path.read_text().splitlines(), start=1):
            stripped = line.strip()
            if not stripped.startswith("git clone"):
                continue
            if "Comeni-Labs" not in stripped:
                continue  # cloning some other repository is not our business
            if "--recurse-submodules" not in stripped:
                offenders.append(f"{path.relative_to(root)}:{number}: {stripped}")
    assert offenders == [], (
        "these clone Comeni-Labs without --recurse-submodules, so registry/ would be empty:\n    "
        + "\n    ".join(offenders)
    )

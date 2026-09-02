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
import sys

from support.paths import ROOT

# **The record is not documentation, and since 2026-09-02 it lives inside the documentation
# tree.** `notes/` moved to `docs/notes/` by the operator's decision, and every guard that walks
# `docs/` inherited it: this file's two scans both went red immediately, on entries that are
# *correct* — the guard ledger's own row about the `docs/internal` move names `docs/internal`,
# for ever, and a plan describing a clone quotes the command it described.
#
# While the notes had their own top-level directory that separation was structural. It is now an
# exception, which is a weaker guarantee in a specific direction: a scan can no longer
# accidentally include the record, but a *new* documentation directory nested under this prefix
# would be silently skipped. `test_notes_are_the_only_docs_exclusion` is what holds that.
#: The record, and the fixtures — both legitimately name paths that no longer exist. The guard
#: ledger is append-only provenance whose oldest rows describe the `docs/internal` move itself,
#: and it moved under `tests/` on 2026-09-02 when the working notes were pruned and `make
#: residue` still needed to read it. A fixture is data, not a document.
RECORD = pathlib.Path("docs") / "notes"
FIXTURES = pathlib.Path("tests") / "fixtures"


def _is_record(relative: pathlib.Path) -> bool:
    return RECORD in relative.parents or FIXTURES in relative.parents


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
    root = ROOT
    # `notes/` is not scanned, for the same reason `make links` does not check it: the record
    # legitimately names things that no longer exist. The guard ledger's own row about this
    # move says `docs/internal`, correctly and for ever.
    #
    # What *is* scanned is everything a reader or a tool follows now: `docs/`, the root,
    # `packages/`, `tests/`, `tools/`.
    scanned = ("docs", "packages", "tests", "tools")
    # `*.yml` was added on 2026-09-02, and it found a violation immediately: the band table in
    # `comeni_core/diagnostics.yml` cited `docs/internal/specs/…`, and this guard — written for
    # exactly that class of error — could not see it, because it scanned only `*.md` and `*.py`.
    # A guard that names the two extensions it happened to be written against is a guard with a
    # hole the shape of every other extension. Declared data is the one that matters here:
    # `diagnostics.yml` is the source every diagnostic code and
    # `docs/handbook/reference/diagnostics.md` are generated from, so a dead path in it is a
    # dead path in generated documentation.
    # This file itself, spelled from `__file__` rather than written out: the hard-coded
    # path went stale the day the suite was arranged into directories, and a guard that
    # fails on its own move teaches nothing.
    exempt = {str(pathlib.Path(__file__).resolve().relative_to(root))}
    paths = [
        path
        for top in scanned
        for pattern in ("*.md", "*.py", "*.yml", "*.yaml")
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
        if str(relative) in exempt or _is_record(relative):
            continue
        text = path.read_text()
        # A boundary, not a bare substring: `docs/internals/` — the fifth book, added
        # 2026-09-02 — contains `docs/internal` as a substring, and every correct reference to
        # it was tripping this guard. `(?!s)` is the boundary: it rejects the character that
        # turns the retired directory into the new one, on both spellings this guard checks.
        if re.search(r"docs/internal(?!s)", text) or re.search(r'"docs" / "internal"(?!s)', text):
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
    root = ROOT
    offenders = []
    for path in sorted(root.glob("*.md")) + sorted((root / "docs").rglob("*.md")):
        if _is_record(path.relative_to(root)):
            continue
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


def test_notes_are_the_only_docs_exclusion():
    """`docs/notes/` and `docs/superpowers/` are skipped by the link checker, and **nothing
    else under `docs/` is.**

    This exists because of the direction the 2026-09-02 move weakened. While the working notes
    were a top-level `notes/`, `check_links._markdown()` enumerated `docs/` and could not reach
    them — the separation was a property of the tree. Now the notes are inside `docs/` and are
    skipped by a path prefix, so the failure mode inverted: the old shape could not accidentally
    check the record, and this one can accidentally stop checking real documentation, silently,
    the moment anything is nested under that prefix or the prefix is widened.

    `docs/superpowers/` joined the exclusion in Task 4 — the specs there link forward to plans
    that may not exist yet, same reasoning as the notes, same risk: two prefixes are still a
    blocklist, and this test is what keeps that list from growing by accident.

    A prefix exclusion is a blocklist, and this repository has learned twice what a blocklist
    costs — `test_every_payload_field_is_a_declared_shape` became an allowlist because a
    blocklist can only forbid what somebody named. So this asserts the complement: every
    markdown file under `docs/` that is not in one of the two exclusions **is** checked.
    """
    root = ROOT
    sys.path.insert(0, str(root / "tools"))
    import check_links

    scanned = set(check_links._markdown())
    everything = set((root / "docs").rglob("*.md"))
    exclusions = (root / "docs" / "notes", root / "docs" / "superpowers")
    record = {p for p in everything if any(e in p.parents for e in exclusions)}

    missed = sorted(str(p.relative_to(root)) for p in (everything - record) - scanned)
    assert missed == [], (
        "these documentation files are not link-checked, and only `docs/notes/` and "
        "`docs/superpowers/` should be exempt:\n  " + "\n  ".join(missed)
    )
    leaked = sorted(str(p.relative_to(root)) for p in record & scanned)
    assert leaked == [], (
        "the record is being link-checked, which makes `make check` red for the duration of "
        "every plan:\n  " + "\n  ".join(leaked)
    )
    # A scan that reaches nothing proves nothing — the same assertion the guard above makes.
    assert len(everything - record) > 20, "the documentation scan is not scanning"

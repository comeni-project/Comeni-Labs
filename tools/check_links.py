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

`docs/notes/` and `docs/superpowers/` are **excluded**, and they are the only two. The working
notes moved under `docs/` on 2026-09-02, and the reason they were never checked did not move
with them: a plan naming a file its own tasks create is *correct* at the moment it executes and
broken until then, so checking them makes `make check` red for the duration of every plan. The
cost of a broken link also differs by audience — in `docs/` a reader hits a 404; in the notes a
future reader meets a dated document that already says it describes work not yet done.
`docs/superpowers/` holds the same kind of provenance — plans and specs — and joined the
exclusion in Task 4 for the same reason: a spec links forward to a plan, or a plan to a task,
that may not exist yet.

**The exclusion is a path prefix, and that is a weaker guarantee than it was.** While the notes
sat in their own top-level directory the separation was structural: `_markdown()` enumerated
`docs/` and never reached them. Now a new directory under `docs/` is checked by default and the
notes are checked by exception, so the failure mode inverts — the old shape could not
accidentally check the notes, and this one can accidentally stop checking a real documentation
directory whose name someone nests under `docs/notes/` or `docs/superpowers/`.
`test_notes_are_the_only_docs_exclusion` holds the exclusion to exactly these two prefixes.

**A generated page is checked for being generated, not for being present.** `docs/tools/` is
written by `make wiki-tools` — `mendel docs` renders one page per tool and
`generate_tools_catalogue.py` renders the catalogue that groups them — so those files exist in
a built site and not in a checkout. `docs/tools/index.md` linking to `catalogue.md` is
*correct*, and reporting it costs somebody the ten minutes it takes to discover that.

The question is asked of **git, not of a list here**: a path under `docs/` that git ignores is
one a make target writes, because that is what those ignore rules exist to say
(`.gitignore` §"The tool catalogue is generated from the registry"). A second list naming the
generated pages would be a second thing to keep honest, and this repository has a Dockerfile
that went wrong three times for exactly that reason.

**What this costs, stated rather than discovered.** The ignore rule is `/docs/tools/*.md` plus
`/docs/tools/**/*.md`, so it covers the whole directory — which means a link *into* `docs/tools/`
naming a page the generator does not produce is no longer reported either. That blind spot was
found by breaking the checker on purpose and watching it stay green, not by reading this.

It is accepted because the alternative is worse and because the same limit is already accepted
next door: `mkdocs.yml`'s `not_in_nav: tools/*/*.md` exists because the page set is a function
of `--registry` and *cannot be known ahead of time*. A checkout genuinely does not hold the
answer to "is there a page for this tool"; only a build does. Reporting every correct link as
broken to catch a hypothetical typo is the trade that made somebody spend ten minutes on
`catalogue.md`.

The blind spot is bounded and pinned. `docs/tools/` is the only directory under `docs/` where
any `.md` is ignored, and `test_the_generated_exemption_covers_only_the_generated_tree` fails
if a second one appears — so this cannot spread to a real documentation directory the way a
prefix exclusion silently can. Outside that tree an absent page is still reported, which
`test_a_missing_page_is_still_reported` holds.

It is scoped to `docs/` deliberately. Elsewhere an ignored target is more likely to be a build
artifact somebody linked by mistake than a page a target renders.

Anchors (`#section`) are not checked — that needs a markdown parser, and the failure mode is a
reader scrolling rather than a reader hitting a 404.
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
            input="\n".join(str(p) for p in under_docs),
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return set()
    # `check-ignore` exits 1 when nothing matched, which is an ordinary answer and not an error.
    if result.returncode not in (0, 1):
        return set()
    return {pathlib.Path(line) for line in result.stdout.splitlines() if line}


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

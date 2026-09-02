"""What on these pages is vision, and what is real — derived, never asserted.

`Start here`, `Handbook` and `Registry` are written in the present tense to the product as it
will be, with a marker wherever reality has not caught up. That is only honest if the markers
are enforced, because a claim maintained by remembering is a claim that goes stale — which is
the failure this repository has had from stale counts three times.

So: every marker must name a plan, and every marker must say what happens today instead. Both
are build failures, and `docs/status.md` is generated from the same scan.

`Internals` is the other register. It is written to what exists, and its pages carry a
`Serves:` line naming which part of the loop they belong to — accuracy was never the problem
with the old documentation, orphaning was.
"""

from __future__ import annotations

import argparse
import dataclasses
import pathlib
import re
import sys

# `!!!` is a plain admonition; pymdownx.details also allows `???` (collapsed by
# default) and `???+` (collapsed but rendered expanded) for the identical block — a
# marker written either way must be exactly as enforced.
MARKER = re.compile(r'^\s*(?:!!!|\?\?\?\+?)\s+\w+\s+"Not built yet"\s*$')
PLAN = re.compile(r"\b(Plan [0-9]+(?:\.[0-9]+)?[A-Z]?|#[0-9]+|issue [0-9]+)\b", re.IGNORECASE)
SERVES = re.compile(r"^\s*>?\s*\*?Serves:", re.MULTILINE)
# What follows "Serves:" on that line, up to the sentence's close — captures the
# step name so it can be checked against STEPS rather than merely detected.
STEP_NAME = re.compile(r"Serves:\s*\*{0,2}([^*\n.]+?)\*{0,2}\s*\.")

# The loop a page may serve. Spec §2 — these are the product's four verbs plus the registry
# loop that everything else stands on.
STEPS = {"describe", "build", "run", "watch", "registry", "all four steps"}

TITLE = "Not built yet"


@dataclasses.dataclass(frozen=True)
class Marker:
    page: str
    line: int
    body: str
    plan: str | None


def _body_of(lines: list[str], start: int) -> str:
    """An admonition's body is the indented block under its title line."""
    out: list[str] = []
    for line in lines[start + 1 :]:
        if line.strip() and not line.startswith((" ", "\t")):
            break
        out.append(line.strip())
    return " ".join(part for part in out if part)


def scan(root: pathlib.Path) -> list[Marker]:
    """Every `Not built yet` marker under `root`, in path order."""
    found: list[Marker] = []
    for path in sorted(root.rglob("*.md")):
        rel = path.relative_to(root).as_posix()
        if rel.startswith(("notes/", "superpowers/", "tools/")):
            continue
        lines = path.read_text(encoding="utf-8").splitlines()
        for i, line in enumerate(lines):
            if MARKER.match(line):
                body = _body_of(lines, i)
                hit = PLAN.search(body)
                found.append(Marker(rel, i + 1, body, hit.group(1) if hit else None))
    return found


def problems(markers: list[Marker], root: pathlib.Path | None = None) -> list[str]:
    """Every reason the documentation's honesty claim does not hold."""
    out: list[str] = []
    for m in markers:
        where = f"{m.page}:{m.line}"
        if m.plan is None:
            out.append(
                f"{where}: a `{TITLE}` marker names no plan or issue, so nobody can "
                "schedule or retire it. Add 'Tracked in Plan N' or an issue number."
            )
        # "What happens today instead" is prose, so the check is a floor rather than a
        # judgement: a body short enough to be only an absence cannot also be an alternative.
        without_plan = PLAN.sub("", m.body).strip(" .")
        if len(without_plan.split()) < 8:
            out.append(
                f"{where}: a `{TITLE}` marker must say what happens today instead. "
                "A marker that only reports an absence strands the reader."
            )
    if root is not None:
        for path in sorted((root / "internals").rglob("*.md")):
            text = path.read_text(encoding="utf-8")
            rel = path.relative_to(root).as_posix()
            if not SERVES.search(text):
                out.append(
                    f"{rel}: an Internals page needs a `Serves:` line naming which part of "
                    f"the loop it belongs to — one of {sorted(STEPS)}."
                )
                continue
            # The line exists — now check it names a real step rather than just
            # confirming the string "Serves:" is present, which proves nothing about
            # what it claims.
            step_match = STEP_NAME.search(text)
            step = step_match.group(1).strip() if step_match else None
            if step is None or step.lower() not in STEPS:
                out.append(
                    f"{rel}: its `Serves:` line names a step not in {sorted(STEPS)} "
                    f"(got {step!r}) — a page can only orphan-proof itself by naming a "
                    "step that is actually part of the loop."
                )
    return out


def render(markers: list[Marker]) -> str:
    """`docs/status.md` — one page answering 'how much of this is real'."""
    head = (
        "---\n"
        "title: What is not built yet\n"
        "description: Every page that describes something the product does not do yet.\n"
        "---\n\n"
        "# What is not built yet\n\n"
        "Comeni Labs is **Alpha, pre-MVP**. The user-facing books are written to the product "
        "as it will be, and every place reality has not caught up carries a marker. This page "
        "is generated from those markers, so it cannot go stale.\n\n"
    )
    if not markers:
        return head + "Nothing is marked. Every page describes something that exists.\n"
    rows = "\n".join(
        f"| [{m.page}]({m.page}) | {m.plan or '—'} | {m.body} |" for m in markers
    )
    return (
        head
        + f"**{len(markers)} marked** across the books.\n\n"
        + "| Page | Tracked in | What happens today |\n|---|---|---|\n"
        + rows
        + "\n"
    )


def main() -> int:
    ap = argparse.ArgumentParser(prog="docs_status.py")
    ap.add_argument("--check", action="store_true", help="write nothing; fail on a problem")
    args = ap.parse_args()

    root = pathlib.Path(__file__).parent.parent / "docs"
    markers = scan(root)
    found = problems(markers, root=root)
    if found:
        print(f"{len(found)} problem(s) with the documentation's markers:")
        for p in found:
            print(f"  {p}")
        return 1

    page = render(markers)
    out = root / "status.md"
    if args.check:
        if not out.is_file() or out.read_text(encoding="utf-8") != page:
            print("docs/status.md is stale — run `make docs-status`")
            return 1
        print(f"docs/status.md is current ({len(markers)} marked)")
        return 0

    out.write_text(page, encoding="utf-8")
    print(f"docs/status.md written ({len(markers)} marked)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

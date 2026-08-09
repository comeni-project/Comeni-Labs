#!/usr/bin/env python
"""Render the diagnostics table in `docs/reference/cli.md` from `comeni_core/diagnostics.yml`.

One source, two consumers: `Diagnostic` validates its `code` against the registry, and this
renders the public table from it. Before this, the long form lived in a Python dict and the
table was maintained by hand, so a code could exist in one and not the other — and nothing
would say so.

`--check` is what CI runs, on pull requests through `make check` and against `main` through the
nightly workflow. **Nothing commits the regenerated file.** An Action that fixed `main`
automatically would need push rights to a protected branch, and a bypass exists forever and for
everything; worse, a self-healing `main` means nobody ever sees the drift — someone hand-edits
the generated table, a bot silently reverts them, and they learn nothing about why the file is
generated. A failing check teaches.

Deliberately the same shape as `tools/generate_types.py`: compare, print the command that fixes
it, exit 1. A second convention for one job is how one of them rots.
"""

import sys
from pathlib import Path

from comeni_core.diagnostics import REGISTRY, DiagnosticSpec

DOC = Path(__file__).parent.parent / "docs" / "reference" / "cli.md"
BEGIN = "<!-- BEGIN GENERATED DIAGNOSTICS -->"
END = "<!-- END GENERATED DIAGNOSTICS -->"

HEADINGS: dict[str, str] = {
    "conformance": "A contract disagrees with its module",
    "pipeline-file": "The pipeline file — a setting, an override, or the format",
    "routing": "Routing and resolution",
    "gates": "Gates and emission",
}
"""Section titles per `concern`, in the order they are rendered.

Declared here rather than derived from the registry so the document's order is stable and
readable — sorting concerns alphabetically would put "gates" before "conformance", which is
neither the order a reader meets them in nor the order of the bands.
"""


def _rows(specs: list[DiagnosticSpec]) -> list[str]:
    return [f"| `{spec.code}` | {spec.says} |" for spec in sorted(specs, key=lambda s: s.code)]


def table() -> str:
    """The whole generated block, grouped by concern.

    A concern with no codes renders nothing rather than an empty table: the bands are reserved
    ahead of use, and an empty section reads as a gap rather than as a reservation.
    """
    lines: list[str] = []
    for concern, heading in HEADINGS.items():
        specs = [spec for spec in REGISTRY.values() if spec.concern == concern]
        if not specs:
            continue
        lines += [f"#### {heading}", "", "| Code | Says |", "|---|---|", *_rows(specs), ""]

    unknown = sorted({s.concern for s in REGISTRY.values()} - set(HEADINGS))
    if unknown:
        raise SystemExit(
            f"diagnostics.yml declares concerns with no heading in this file: {unknown}. "
            "Add them to HEADINGS, in the order a reader should meet them."
        )
    return "\n".join(lines).rstrip("\n")


def rendered() -> str:
    current = DOC.read_text()
    head, _, rest = current.partition(BEGIN)
    _, _, tail = rest.partition(END)
    return f"{head}{BEGIN}\n\n{table()}\n\n{END}{tail}"


def main() -> int:
    generated = rendered()
    if "--check" in sys.argv:
        if DOC.read_text() != generated:
            print(
                f"{DOC.relative_to(DOC.parent.parent.parent)} is stale — run: "
                "uv run python tools/generate_diagnostics_doc.py"
            )
            return 1
        return 0
    DOC.write_text(generated)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

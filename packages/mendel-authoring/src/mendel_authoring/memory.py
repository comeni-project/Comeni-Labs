"""Render current recorded knowledge for conversational prompts.

Prompts receive this deterministic projection of decisions rather than reconstructing state from
the transcript. The record remains authoritative when conversation wording is ambiguous.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict


class KnownItem(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    label: str
    """What it is, by name: *sequencing reads (FASTQ)*, *read length*."""
    value: str | None = None
    """*yes*, *150 bp*; none for an input held or a want."""
    source: Literal["said", "measured", "read_by_ai", "open", "model"]
    heard: str | None = None
    """The person's own words it was taken from, when it was heard."""


class Known(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    wants: list[KnownItem] = []
    constraints: list[KnownItem] = []
    not_offered: list[str] = []
    inputs: list[KnownItem] = []
    facts: list[KnownItem] = []
    suggested: list[str] = []
    open: list[str] = []
    confirmed: bool = False


_SOURCE = {
    "said": "you said",
    "measured": "measured from your sample",
    "read_by_ai": "read by AI from your sample",
    "open": "unknown",
    "model": "the model's reading",
}


def _item(item: KnownItem) -> str:
    line = f"- {item.label}" + (f": {item.value}" if item.value is not None else "")
    line += f" · {_SOURCE[item.source]}"
    return line + (f' · "{item.heard}"' if item.heard else "")


def render(known: Known) -> str:
    sections = [
        ("What you want", [_item(i) for i in known.wants]),
        ("Asked for but not offered here", [f"- {p}" for p in known.not_offered]),
        ("Constraints", [_item(i) for i in known.constraints]),
        ("Inputs you have", [_item(i) for i in known.inputs]),
        ("Facts about your data", [_item(i) for i in known.facts]),
        ("Suggested, waiting for you", [f"- {s}" for s in known.suggested]),
        ("Still open", [f"- {o}" for o in known.open]),
    ]
    lines = ["What is known (recorded; do not ask for it again):"]
    shown = [(title, items) for title, items in sections if items]
    if not shown:
        lines.append("Nothing is known yet.")
    for title, items in shown:
        lines += ["", f"{title}:", *items]
    if known.confirmed:
        lines += ["", "The goal is confirmed; changes are offered to the person before they apply."]
    return "\n".join(lines) + "\n"

"""Locate a model-supplied quote in the person's normalized conversation turns.

A matching quote proves only that the words occurred, so the resulting interpretation still
retains the quote for review on the goal card.
"""

from collections.abc import Sequence

QUOTE_FLOOR = 3
"""The shortest quote that proves anything: `bp` and `PE` are in too many sentences."""


def _fold(text: str) -> str:
    return " ".join(text.split()).casefold()


def find(quote: str | None, turns: Sequence[tuple[int, str]]) -> int | None:
    """The `seq` of the first of the person's turns holding the quote — case-folded, runs of
    whitespace compared as one — or `None`. One turn: a quote never joins two."""
    if quote is None:
        return None
    wanted = _fold(quote)
    if len(wanted) < QUOTE_FLOOR:
        return None
    return next((seq for seq, text in turns if wanted in _fold(text)), None)

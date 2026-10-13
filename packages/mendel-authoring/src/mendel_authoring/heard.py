"""Whether the person said it: a quote of their own words (Part I.0 spec §5.3).

A model may hand over a change *heard* only by quoting what the person typed, and the engine
checks the quote here before anything is recorded. A quote proves the words were typed, not that
they were read right — *"not paired-end"* holds *"paired-end"* — which is why a heard fact is
still shown with its quote on the goal card, where a misreading is caught."""

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

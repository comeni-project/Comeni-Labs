"""Define the outcomes and accumulator interface implemented by measures.

A measure returns either a value with supporting evidence or an undetermined result with a reason.
It does not substitute a best guess when its declared threshold is unmet.
"""

from typing import NamedTuple, Protocol

from comeni_inspect.records import SequenceRecord


class Value(NamedTuple):
    value: int | float | bool | str
    evidence: dict


class Undetermined(NamedTuple):
    reason: str
    evidence: dict


class Accumulator(Protocol):
    """Consume one side-by-side record row at a time and produce one outcome.

    ``decided`` contains the piece's declared thresholds. ``files`` contains sample filenames for
    evidence or explanations; filenames do not determine the measured value.
    """

    def __init__(self, decided: dict, files: list[str]) -> None: ...

    def add(self, row: tuple[SequenceRecord, ...]) -> None: ...

    def result(self) -> Value | Undetermined: ...

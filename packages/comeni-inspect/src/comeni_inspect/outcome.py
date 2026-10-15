"""What a measure answers: a value with its evidence, or undetermined with a reason.

**Nothing is guessed** (spec §5). A measure below its declared threshold says so, with what it
saw, rather than returning its best guess; the person is asked instead.
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
    """One measure, fed one row at a time: a record from each file, side by side.

    `decided` holds the piece's declared thresholds. `files` are the sample's file names, which
    a measure may quote in a reason but **never decides on** (spec §5).
    """

    def __init__(self, decided: dict, files: list[str]) -> None: ...

    def add(self, row: tuple[SequenceRecord, ...]) -> None: ...

    def result(self) -> Value | Undetermined: ...

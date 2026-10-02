"""What a format yields: one record per read, in the shape every measure reads."""

from typing import NamedTuple


class SequenceRecord(NamedTuple):
    """One read. `name` stops at the first space; any `/1` `/2` suffix is kept, because
    stripping it is the `paired` measure's rule, declared there, not the format's."""

    name: str
    sequence: bytes
    quality: bytes | None

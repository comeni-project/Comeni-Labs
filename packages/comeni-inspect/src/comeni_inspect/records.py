"""What a format yields: one record per read, in the shape every measure reads."""

from typing import NamedTuple


class SequenceRecord(NamedTuple):
    """One read. `name` stops at the first space; any `/1` `/2` suffix is kept, because
    stripping it is the `paired` measure's rule, declared there, not the format's."""

    name: str
    sequence: bytes
    quality: bytes | None


class Malformed(Exception):
    """Raised by a format at a record it can see whole and cannot read: `record 3: no name`.

    **Not a cut head**: a head is always cut somewhere, and a record the cut shortened ends the
    stream quietly. This is a complete record that is wrong, with bytes after it. The runner
    keeps what came before and writes `stopped: malformed <message>` on every fact (issue 224).
    """

"""Define the sequence-record shape shared by formats and measures."""

from typing import NamedTuple


class SequenceRecord(NamedTuple):
    """One read, retaining pair suffixes for the paired-read measure to interpret.

    Formats stop ``name`` at the first space but preserve suffixes such as ``/1`` and ``/2``.
    """

    name: str
    sequence: bytes
    quality: bytes | None


class Malformed(Exception):
    """Report a complete record that a format cannot parse.

    A record truncated by the bounded head ends the stream normally. For a malformed complete
    record, the runner retains earlier measurements and adds ``stopped: malformed <message>`` to
    each fact's evidence.
    """

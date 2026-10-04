"""The characteriser (14.7.7): what a model is shown of a sample, whether one may read it, and
the reading itself.

**The excerpt is the smallest thing that can leave** (spec §5): the first stretch of readable
text in the decoded head, at most 8 KB and 200 lines. Nothing here writes it anywhere; the job
that carries it to the worker keeps no result.
"""

import zlib
from typing import NamedTuple

from comeni_core.spell.marks import EXCERPT_BYTES, EXCERPT_LINES

DECODED_CAP = 64 * 1024
"""The most decompressed before looking for text, so a bomb costs 64 KB (spec §5)."""
MIN_TEXT = 200
"""Fewer readable bytes than this in a row, and there is nothing worth sending."""
_GZIP = b"\x1f\x8b"


class Excerpt(NamedTuple):
    text: str
    binary_before: bool
    """Binary bytes came before the text: a BAM's header, not a SAM file."""


def available() -> bool:
    """Whether a model may read a sample here: the level allows it, and a model answers it.
    The one seam a test replaces."""
    from mendel_api.services import protection
    from mendel_api.settings import model_access

    return (
        protection.allows(protection.Crossing.CHARACTERISE)
        and model_access("builder", "characterise") is not None
    )


def _decoded(head: bytes) -> bytes:
    """The head, gunzipped when its first bytes say gzip — through every member, never past
    `DECODED_CAP`, and as far as a truncated member goes."""
    if not head.startswith(_GZIP):
        return head[:DECODED_CAP]
    out = bytearray()
    rest = head
    while rest.startswith(_GZIP) and len(out) < DECODED_CAP:
        member = zlib.decompressobj(wbits=31)
        try:
            out += member.decompress(rest, DECODED_CAP - len(out))
        except zlib.error:
            break
        if not member.eof:
            break  # truncated, or the cap reached
        rest = member.unused_data
    return bytes(out)


def _texty(byte: int) -> bool:
    return byte in (9, 10, 13) or 32 <= byte < 127 or byte >= 128


def _first_text(data: bytes) -> tuple[int, bytes] | None:
    start = None
    for i, byte in enumerate(data):
        if _texty(byte):
            if start is None:
                start = i
        else:
            if start is not None and i - start >= MIN_TEXT:
                return start, data[start:i]
            start = None
    if start is not None and len(data) - start >= MIN_TEXT:
        return start, data[start:]
    return None


def _bounded(text: bytes) -> str:
    """Whole lines while they fit; a first line longer than the bound is cut at it."""
    kept, size = [], 0
    # Lines are what `\n` separates, as `marks.SampleText` counts them (issue 237).
    lines = [part + b"\n" for part in text.split(b"\n")]
    lines[-1] = lines[-1][:-1]
    for line in [line for line in lines if line][:EXCERPT_LINES]:
        if size + len(line) > EXCERPT_BYTES:
            if not kept:
                kept.append(line[:EXCERPT_BYTES])
            break
        kept.append(line)
        size += len(line)
    # `ignore` drops a character cut in half at the bound, so the text never grows past it.
    return b"".join(kept).decode("utf-8", errors="ignore")


def excerpt(head: bytes) -> Excerpt | None:
    """What a model may be shown of a sample's head, or `None`: nothing worth sending."""
    found = _first_text(_decoded(head))
    if found is None:
        return None
    start, text = found
    return Excerpt(text=_bounded(text), binary_before=start > 0)

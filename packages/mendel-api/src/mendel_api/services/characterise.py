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


class Sealed(str):
    """The excerpt's text, as it rides in a job's arguments. **Its `repr` says nothing of it**:
    ARQ logs a job's arguments by their `repr` when the job starts (issue 241)."""

    def __repr__(self) -> str:
        return f"<excerpt, {len(self.encode())} bytes>"

    def __reduce__(self):
        return (Sealed, (str(self),))


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


_NO_ANSWER = frozenset({"MI0106", "MA0002", "MA0003", "MA0007"})
"""Codes meaning *no answer could be had*: `authoring_jobs.UNREACHABLE`'s set."""


def read_sample(
    session_id: str,
    proposal_id: str,
    attempt: int,
    text: str,
    binary_before: bool,
    *,
    client_for,
) -> str:
    """Read one sample through door 6: families, then the type; record what was admitted.
    **Never raises for a refusal**; every way out is a reading state the card shows. Returns it.

    `client_for(purpose)` is the job's model seam, `authoring_jobs._client`.
    """
    from mendel_authoring import commands as c

    from mendel_api import identity
    from mendel_api.services import authoring_ai, protection, registry, session
    from mendel_api.settings import settings
    from mendel_api.stages import gathering, samples

    if not samples.reading_open(proposal_id, attempt):
        # A second delivery, a reading that already ended, or a question answered meanwhile:
        # no call is spent (issue 241).
        return "stale"
    if not protection.allows(protection.Crossing.DOOR_6):
        # Refused before the payload is built (spec §4): above level 0 nothing composes.
        session.perform(c.ReadingFailed(proposal_id, attempt, "refused", "MI0213"))
        return "refused"

    stack = registry.stack()
    request = authoring_ai.compose_characterise(
        text, binary_before=binary_before, registry=registry.digest()
    )
    families = None
    if len(stack.vocabulary.types) >= settings.family_step_from:
        first = authoring_ai.characterise_families(
            request,
            stack=stack,
            session_id=session_id,
            client=client_for(authoring_ai.Purpose.CHARACTERISE_FAMILY),
        )
        if not first.admitted:
            return _failed(proposal_id, attempt, first)
        if not first.reply.families:
            session.perform(c.ReadingFailed(proposal_id, attempt, "could_not_tell", None))
            return "could_not_tell"
        families = first.reply.families
    second = authoring_ai.characterise(
        request,
        stack=stack,
        families=families,
        session_id=session_id,
        client=client_for(authoring_ai.Purpose.CHARACTERISE),
    )
    if not second.admitted:
        return _failed(proposal_id, attempt, second)
    if second.reply.type_id is None:
        session.perform(c.ReadingFailed(proposal_id, attempt, "could_not_tell", None))
        return "could_not_tell"
    _, read_by_engine = gathering._inspectable(stack)
    handed = second.reply.type_id in read_by_engine
    session.perform(
        c.ReadingAnswered(
            proposal_id,
            attempt,
            second.reply.model_dump(mode="json"),
            identity.default_author(),
            handed,
        )
    )
    return "hand_back" if handed else "read"


def _failed(proposal_id: str, attempt: int, outcome) -> str:
    from mendel_authoring import commands as c

    from mendel_api.services import session

    state = "no_answer" if outcome.code in _NO_ANSWER or outcome.code is None else "refused"
    session.perform(c.ReadingFailed(proposal_id, attempt, state, outcome.code))
    return state

"""When a curator last looked at the queue."""

from datetime import UTC, datetime

from sqlalchemy import select

from mendel_api.db import session_scope
from mendel_api.identity import default_author
from mendel_api.models import QueueVisit


def mark(who: str | None = None) -> datetime:
    """Stamp now as seen, and return the stamp.

    **A separate act from reading the queue.** If a GET recorded a visit, the next GET would
    have a baseline of a moment ago and "what changed since I last looked" would be
    permanently empty — the filter would work exactly once and then answer nothing forever.
    """
    seen_at = datetime.now(UTC)
    with session_scope() as session:
        session.add(QueueVisit(who=who or default_author(), seen_at=seen_at))
    return seen_at


def last(who: str | None = None) -> datetime | None:
    """The most recent visit, or `None` if this person has never been here.

    `None` means *show everything*, not *show nothing*: a first-time reader who filtered by
    "what changed" and got an empty queue would conclude there is no work.
    """
    name = who or default_author()
    with session_scope() as session:
        return session.scalar(
            select(QueueVisit.seen_at)
            .where(QueueVisit.who == name)
            .order_by(QueueVisit.seen_at.desc())
            .limit(1)
        )

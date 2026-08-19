"""What the API remembers.

**One table in slice 1, and the restraint is the point.** The registry is files by decision
(issue #43), and `pipeline.yml` is the artifact rather than a projection of rows. What is
genuinely not recoverable from disk is *when a check last ran*, so that is what is stored.

`test_the_registry_is_not_in_the_database` holds it: a second table is a deliberate act
rather than a drift.
"""

from datetime import datetime

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from mendel_api.db import Base


class SourceCheck(Base):
    __tablename__ = "source_check"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ran_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    checked: Mapped[int] = mapped_column(Integer)
    drifted: Mapped[int] = mapped_column(Integer)
    skipped: Mapped[int] = mapped_column(Integer)


class QueueVisit(Base):
    """When a curator last looked at the queue.

    **The second table, and the first one's docstring said that would be a deliberate act.**
    This is that act. What is not recoverable from disk is when a person last looked — the
    registry is files, the drafts are files, and neither records a reader.

    `who` is ATTRIBUTION, not authentication. It comes from `git config user.name` through
    `identity.default_author()`, so a shared installation gives every curator the same
    baseline unless they configure git differently. Real accounts replace this column's
    source and nothing else.
    """

    __tablename__ = "queue_visit"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    who: Mapped[str] = mapped_column(String(200), index=True)
    seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)

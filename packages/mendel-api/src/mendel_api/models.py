"""What the API remembers.

**One table in slice 1, and the restraint is the point.** The registry is files by decision
(issue #43), and `pipeline.yml` is the artifact rather than a projection of rows. What is
genuinely not recoverable from disk is *when a check last ran*, so that is what is stored.

`test_the_registry_is_not_in_the_database` holds it: a second table is a deliberate act
rather than a drift.
"""

from datetime import datetime

from sqlalchemy import DateTime, Integer
from sqlalchemy.orm import Mapped, mapped_column

from mendel_api.db import Base


class SourceCheck(Base):
    __tablename__ = "source_check"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ran_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    checked: Mapped[int] = mapped_column(Integer)
    drifted: Mapped[int] = mapped_column(Integer)
    skipped: Mapped[int] = mapped_column(Integer)

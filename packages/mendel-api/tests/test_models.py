"""What slice 1 persists, and what it deliberately does not.

A drift check is a fact about a moment — it ran, it looked at N contracts, M disagreed.
Nothing else in the system remembers that, which is why it is the one table.
"""

from datetime import UTC, datetime

from mendel_api.models import SourceCheck


def test_a_source_check_records_when_and_what():
    c = SourceCheck(ran_at=datetime.now(UTC), checked=58, drifted=4, skipped=0)
    assert c.checked == 58
    assert c.drifted == 4


def test_the_registry_is_not_in_the_database():
    """Issue #43 decided declared data is files. A table holding contracts, types or
    roles would be that decision quietly reversed."""
    import mendel_api.models as m

    tables = {v.__tablename__ for v in vars(m).values() if hasattr(v, "__tablename__")}
    assert tables == {"source_check", "queue_visit"}, f"unexpected: {tables}"

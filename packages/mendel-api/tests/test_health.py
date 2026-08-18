"""The queue's health strip, and the one fact behind it.

`ops.check` can say how many contracts agree with their source. Only the database can say
WHEN that was last true, which is the whole reason slice 1 has a table.
"""

from datetime import UTC, datetime, timedelta

from mendel_api.routes.health import strip_from


def test_the_strip_reports_the_last_check():
    ran = datetime.now(UTC) - timedelta(minutes=4)
    strip = strip_from(contracts=58, checked=58, drifted=4, unverifiable=0,
                       types=22, last_check=ran)
    assert strip.contracts == 58
    assert strip.matching == 54
    assert strip.checked_at == ran


def test_a_registry_never_checked_says_so_rather_than_guessing():
    """`None` is not "0 minutes ago". A strip that implies a check happened when none did
    is the kind of quiet falsehood the whole artifact design exists to avoid."""
    strip = strip_from(contracts=58, checked=0, drifted=0, unverifiable=0,
                       types=22, last_check=None)
    assert strip.checked_at is None


def test_a_contract_nothing_could_read_is_not_counted_as_matching():
    """Found by running it: the real registry has 12 contracts and `ops.check` reads 10,
    because two `comeni/` contracts have no adapter. The first version reported 12
    matching, which is the exact failure CheckResult.skipped's docstring warns about —
    a contract nothing checks looks like a contract that agrees."""
    strip = strip_from(contracts=12, checked=10, drifted=0, unverifiable=2,
                       types=22, last_check=datetime.now(UTC))
    assert strip.matching == 10
    assert strip.unverifiable == 2
    assert strip.matching + strip.unverifiable == strip.contracts

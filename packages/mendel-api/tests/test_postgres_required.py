"""A test that needs Postgres skips without it on a laptop and fails without it in CI.

Every database test here skipped itself in CI for months because nothing was reachable there,
so a green run said nothing about storage. `COMENI_REQUIRE_DB` is what CI sets to make an
unreachable database a failure rather than a skip (issue 279).
"""

import mendel_postgres
import pytest


def _down():
    raise OSError("connection refused")


def test_an_unreachable_database_skips_where_it_is_not_required(monkeypatch):
    monkeypatch.delenv(mendel_postgres.REQUIRED, raising=False)
    assert mendel_postgres.reachable(_down) is False


def test_an_unreachable_database_fails_where_it_is_required(monkeypatch):
    monkeypatch.setenv(mendel_postgres.REQUIRED, "1")
    with pytest.raises(RuntimeError, match="COMENI_REQUIRE_DB"):
        mendel_postgres.reachable(_down)

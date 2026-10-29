"""The stored catalogue and its sync (forge part 1 spec, §3–4)."""

import pytest
import sqlalchemy as sa
from mendel_api.db import session_scope
from mendel_api.models import CatalogueModule
from mendel_api.services import catalogue
from mendel_api_tests.catalogue import FakeSource
from mendel_api_tests.database import reachable

pytestmark = pytest.mark.skipif(not reachable(), reason="no database")


@pytest.fixture(autouse=True)
def empty():
    with session_scope() as db:
        db.execute(sa.text("DELETE FROM catalogue_module"))
        db.execute(sa.text("DELETE FROM catalogue_sync"))


def _rows() -> dict[str, CatalogueModule]:
    with session_scope() as db:
        return {row.path: row for row in db.scalars(sa.select(CatalogueModule))}


def test_a_sync_stores_every_module():
    done = catalogue.run_sync(FakeSource(["fastqc", "star/align"]))
    assert done.outcome == "ok"
    assert done.modules == 2
    rows = _rows()
    assert sorted(rows) == ["fastqc", "star/align"]
    star = rows["star/align"]
    assert star.tool_version == "2.7.11b"
    assert "alignment" in star.topics
    assert "bam" in star.formats
    assert "align reads" in star.search
    assert star.document["tools"][0]["name"] == "star"
    assert star.seen_in == done.id


def test_a_module_gone_upstream_is_marked_not_deleted():
    catalogue.run_sync(FakeSource(["fastqc", "star/align"]))
    catalogue.run_sync(FakeSource(["fastqc"], commit="c2"))
    rows = _rows()
    assert rows["star/align"].gone is True
    assert rows["fastqc"].gone is False


def test_a_failing_source_leaves_the_catalogue_whole():
    first = catalogue.run_sync(FakeSource(["fastqc", "star/align"]))
    second = catalogue.run_sync(FakeSource(["bwa/mem", "fastqc"], commit="c2", fail_after=1))
    assert second.outcome == "failed"
    assert "the network went away" in second.error
    rows = _rows()
    assert sorted(rows) == ["fastqc", "star/align"]
    assert {row.seen_in for row in rows.values()} == {first.id}
    assert catalogue.last_good_sync().id == first.id
    assert catalogue.last_sync().id == second.id


def test_a_module_with_problems_is_stored_and_counted():
    done = catalogue.run_sync(FakeSource(["broken-meta", "fastqc"]))
    assert done.outcome == "ok"
    assert done.problems == 1
    assert _rows()["broken-meta"].document["problems"][0]["code"] == "MF0500"



def test_a_sync_that_reads_no_modules_fails_and_changes_nothing():
    """An upstream that moved its modules, or a broken checkout, must not mark everything gone."""
    catalogue.run_sync(FakeSource(["fastqc", "star/align"]))
    empty = catalogue.run_sync(FakeSource([], commit="c2"))
    assert empty.outcome == "failed"
    assert "no modules" in empty.error
    assert {row.gone for row in _rows().values()} == {False}


def test_an_over_long_format_or_topic_is_dropped_not_fatal(monkeypatch):
    from mendel_forge.nfcore import parse as parse_module

    real = parse_module.formats_of
    monkeypatch.setattr(parse_module, "formats_of", lambda channels: [*real(channels), "x" * 80])
    done = catalogue.run_sync(FakeSource(["fastqc"]))
    assert done.outcome == "ok"
    assert all(len(f) <= 32 for f in _rows()["fastqc"].formats)


def _hold_the_source():
    """Another sync, as far as the database can tell: its claim on the source."""
    from mendel_api.db import engine

    connection = engine.connect()
    assert connection.execute(sa.text("SELECT pg_try_advisory_lock(:k)"),
                              {"k": catalogue.claim_key("nf-core")}).scalar()
    return connection


def test_a_sync_while_another_holds_the_source_starts_nothing():
    """The daily run and *Sync now* can meet; only one may touch the clone."""
    held = _hold_the_source()
    try:
        assert catalogue.run_sync(FakeSource(["fastqc"])) is None
        assert catalogue.sync_running() is True
    finally:
        held.invalidate()  # close the real connection: a pooled one would keep the lock
    assert catalogue.last_sync() is None, "no sync row was written"
    assert catalogue.sync_running() is False


def test_a_sync_a_crash_left_running_is_closed_by_the_next():
    from datetime import UTC, datetime

    from mendel_api.models import CatalogueSync

    with session_scope() as db:
        db.add(CatalogueSync(source="nf-core", started_at=datetime.now(UTC), outcome="running"))
    assert catalogue.sync_running() is False, "a row is not a claim: nothing holds the source"
    done = catalogue.run_sync(FakeSource(["fastqc"]))
    assert done.outcome == "ok"
    with session_scope() as db:
        outcomes = db.scalars(sa.select(CatalogueSync.outcome).order_by(CatalogueSync.id)).all()
    assert outcomes == ["failed", "ok"]

"""The stored catalogue and its sync (forge part 1 spec, §3–4)."""

from collections.abc import Iterator
from pathlib import Path

import pytest
import sqlalchemy as sa
from mendel_api.db import session_scope
from mendel_api.models import CatalogueModule, CatalogueSync
from mendel_api.services import catalogue
from mendel_api_tests.database import reachable
from mendel_forge.model import UpstreamModule
from mendel_forge.nfcore.parse import parse_module
from mendel_forge.source import Snapshot, SourceUnavailable
from support.paths import ROOT

pytestmark = pytest.mark.skipif(not reachable(), reason="no database")
FIXTURES = ROOT / "packages" / "mendel-forge" / "tests" / "fixtures" / "nf-core"


class FakeSource:
    """Yields fixture modules; `fail_after` raises once that many have been yielded."""

    name = "nf-core"

    def __init__(self, paths: list[str], commit: str = "c1", fail_after: int | None = None):
        self.paths, self.commit, self.fail_after = paths, commit, fail_after

    def sync(self, cache: Path) -> Snapshot:
        return Snapshot(source=self.name, commit=self.commit, root=FIXTURES)

    def modules(self, snapshot: Snapshot) -> Iterator[UpstreamModule]:
        for n, path in enumerate(self.paths):
            if self.fail_after is not None and n == self.fail_after:
                raise SourceUnavailable("the network went away")
            yield parse_module(FIXTURES / path, path)


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


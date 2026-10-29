"""The catalogue over HTTP: filtered, searched, paged, counted (forge part 1 spec, §3 and §5)."""

import pytest
import sqlalchemy as sa
from fastapi.testclient import TestClient
from mendel_api import jobs
from mendel_api.db import session_scope
from mendel_api.main import create_app
from mendel_api.services import catalogue
from mendel_api_tests.catalogue import FakeSource
from mendel_api_tests.database import reachable

pytestmark = pytest.mark.skipif(not reachable(), reason="no database")
ALL = ["fastqc", "star/align", "samtools/sort", "bwa/mem", "two-tools", "broken-meta"]


@pytest.fixture
def client() -> TestClient:
    with session_scope() as db:
        db.execute(sa.text("DELETE FROM catalogue_module"))
        db.execute(sa.text("DELETE FROM catalogue_sync"))
    catalogue.run_sync(FakeSource(ALL))
    return TestClient(create_app())


def _page(client, **query) -> dict:
    answer = client.get("/api/forge/catalogue", params=query)
    assert answer.status_code == 200, answer.text
    return answer.json()


def test_filters_by_state_and_counts(client):
    page = _page(client, state="imported")
    assert [row["path"] for row in page["rows"]] == ["star/align"]
    assert page["rows"][0]["contract_id"] == "nf-core/star/align@2.7.11b"
    updates = _page(client, state="update_available")
    assert sorted(row["path"] for row in updates["rows"]) == ["fastqc", "samtools/sort"]
    assert updates["rows"][0]["registry_version"] in ("0.12.1", "1.24")
    states = page["counts"]["states"]
    assert states["imported"] == 1 and states["update_available"] == 2
    assert states["not_imported"] == 3
    assert page["registry_at"]


def test_topic_and_format_filters_are_any_of(client):
    aligned = {row["path"] for row in _page(client, topic="alignment")["rows"]}
    assert {"star/align", "bwa/mem"} <= aligned
    either = {row["path"] for row in _page(client, format=["gtf", "html"])["rows"]}
    assert {"star/align", "fastqc"} <= either
    assert "bwa/mem" not in either


def test_best_puts_held_modules_first(client):
    order = [row["state"] for row in _page(client)["rows"]]
    assert order[:3] == ["update_available", "update_available", "imported"]
    assert set(order[3:]) == {"not_imported"}


def test_search_matches_description_and_ranks(client):
    rows = _page(client, q="star")["rows"]
    assert rows, "star finds something"
    assert rows[0]["path"] == "star/align"


def test_search_wildcards_are_literal(client):
    assert _page(client, q="%")["rows"] == []
    assert _page(client, q="_")["total"] == 0
    assert client.get("/api/forge/catalogue", params={"q": "'"}).status_code == 200


def test_pages_are_stable(client):
    first = _page(client, limit=4)
    assert first["next_offset"] == 4
    second = _page(client, limit=4, offset=4)
    assert second["next_offset"] is None
    paths = [row["path"] for row in first["rows"] + second["rows"]]
    assert sorted(paths) == sorted(ALL)


def test_pull_request_states_are_present_as_zero(client):
    states = _page(client)["counts"]["states"]
    assert states["in_review"] == 0 and states["merged_not_released"] == 0


def test_a_module_s_detail(client):
    answer = client.get("/api/forge/catalogue/nf-core/star/align")
    assert answer.status_code == 200
    detail = answer.json()
    assert detail["row"]["state"] == "imported"
    assert detail["module"]["tools"][0]["name"] == "star"


def test_unknown_module_is_MF0503(client):
    answer = client.get("/api/forge/catalogue/nf-core/no/such")
    assert answer.status_code == 404
    assert answer.json()["detail"].startswith("MF0503")


def test_a_held_module_gone_upstream_is_listed(client):
    catalogue.run_sync(FakeSource([p for p in ALL if p != "star/align"], commit="c2"))
    rows = _page(client, state="gone_upstream")["rows"]
    assert [(row["path"], row["contract_id"]) for row in rows] == [
        ("star/align", "nf-core/star/align@2.7.11b")
    ]
    assert _page(client)["counts"]["states"]["gone_upstream"] == 1


def test_second_sync_request_says_already_queued(client, monkeypatch):
    async def refused(*args, **kwargs):
        return False

    monkeypatch.setattr(jobs, "enqueue", refused)
    answer = client.post("/api/forge/catalogue/sync")
    assert answer.status_code == 202
    assert answer.json() == {"queued": False}


def test_a_queue_that_cannot_be_reached_is_MF0502(client, monkeypatch):
    async def down(*args, **kwargs):
        raise ConnectionError("redis is down")

    monkeypatch.setattr(jobs, "enqueue", down)
    answer = client.post("/api/forge/catalogue/sync")
    assert answer.status_code == 503
    assert answer.json()["detail"].startswith("MF0502")


def test_last_sync_and_stale(client):
    catalogue.run_sync(FakeSource(["fastqc"], commit="c3", fail_after=0))
    page = _page(client)
    assert page["last"]["outcome"] == "failed" and page["last"]["stale"] is True
    assert page["last_good"]["commit"] == "c1"


def test_sync_now_while_a_sync_runs_starts_nothing(client, monkeypatch):
    from datetime import UTC, datetime

    from mendel_api.models import CatalogueSync

    async def must_not_queue(*args, **kwargs):
        raise AssertionError("a second sync was queued")

    monkeypatch.setattr(jobs, "enqueue", must_not_queue)
    with session_scope() as db:
        db.add(CatalogueSync(source="nf-core", started_at=datetime.now(UTC), outcome="running"))
    answer = client.post("/api/forge/catalogue/sync")
    assert answer.status_code == 202
    assert answer.json() == {"queued": False}

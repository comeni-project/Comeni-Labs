"""Browsing contracts, over HTTP."""

from fastapi.testclient import TestClient
from mendel_api.main import create_app

client = TestClient(create_app(), raise_server_exceptions=False)


def test_the_list_comes_back_sorted_worst_first():
    r = client.get("/api/contracts")
    assert r.status_code == 200
    body = r.json()
    assert body["total"] > 0
    assert sum(body["counts"].values()) == body["total"]


def test_a_facet_narrows_the_rows():
    r = client.get("/api/contracts?against=unverifiable")
    assert r.status_code == 200
    rows = r.json()["rows"]
    assert rows, "this registry has unverifiable contracts"
    assert all(row["status"] == "unverifiable" for row in rows)


def test_a_status_that_is_not_one_is_refused_rather_than_ignored():
    """A typo'd facet must not silently return everything — the URL is what a curator sends
    somebody, and it has to describe the screen they saw."""
    assert client.get("/api/contracts?against=broken").status_code == 422


def test_a_contract_id_with_slashes_reaches_the_route():
    """`nf-core/samtools/index@1.21.0` has two slashes. Without `{id:path}` FastAPI matches
    only `nf-core` and answers 404."""
    r = client.get("/api/contracts/nf-core/fastqc@0.12.1")
    assert r.status_code == 200
    assert r.json()["id"] == "nf-core/fastqc@0.12.1"


def test_an_unknown_contract_is_a_coded_refusal():
    r = client.get("/api/contracts/nf-core/nonsense@1.0.0")
    assert r.status_code == 422
    assert "not in this registry" in r.json()["detail"]


def test_there_is_no_way_to_write_a_contract():
    """Read-only stays read-only — design §7. Contracts change through the queue or through
    drift resolution, both of which record why. This is the structural half of that claim."""
    from mendel_api.routes import contracts as routes

    methods = {m for route in routes.router.routes for m in getattr(route, "methods", set())}
    assert methods <= {"GET", "HEAD"}, f"a write verb reached the contracts router: {methods}"

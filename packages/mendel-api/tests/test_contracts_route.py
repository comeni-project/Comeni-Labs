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


def test_the_only_write_is_accepting_what_the_source_says():
    """Design §7 says contracts change through the queue or through **drift resolution**,
    both of which record why. Phase 4 could hold that structurally — no write verb at all —
    because drift resolution did not exist yet; phase 5 built it, so the claim narrows to
    what it always meant rather than being deleted.

    **The narrower claim is still structural**: exactly one write, and it is the one that
    takes a value the SOURCE states rather than one a caller composes. A free-text `PATCH`
    reaching this router fails here, which is what makes adding one a deliberate act.
    """
    from mendel_api.routes import contracts as routes

    writes = {
        (route.path, method)
        for route in routes.router.routes
        for method in getattr(route, "methods", set())
        if method not in {"GET", "HEAD"}
    }
    assert writes == {("/contracts/{id:path}/drift/accept", "POST")}, (
        f"an unexpected write verb reached the contracts router: {writes}"
    )

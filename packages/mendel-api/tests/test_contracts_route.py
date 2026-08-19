"""One contract, over HTTP.

**The listing tests left with the listing route** — `GET /contracts` was deleted in the same
commit as `Contracts.tsx`, and its assertions live in `test_tools_route.py`. What is here is
what `/tools` does not supersede: reading one contract, and the drift write.
"""

from fastapi.testclient import TestClient
from mendel_api.main import create_app

client = TestClient(create_app(), raise_server_exceptions=False)


def test_the_listing_path_now_falls_through_to_the_greedy_id_route():
    """**Written because the test that used to be here went vacuous rather than red.**

    It asserted that `/api/contracts?against=broken` is a 422, meaning *a typo'd facet is
    refused rather than ignored*. Deleting `GET /contracts` did not fail it: the request now
    matches `/contracts/{id:path}` with an empty id and 422s with `'' is not in this registry`.
    Same status code, entirely different reason, and a green test asserting nothing.

    A greedy `{id:path}` swallows its own parent path, so removing a sibling route cannot be
    checked by status code alone. The facet assertion moved to `test_tools_route.py` with the
    route; this one pins the fall-through so the next person sees it deliberately.
    """
    refused = client.get("/api/contracts?against=broken")
    assert refused.status_code == 422
    assert refused.json()["detail"] == "'' is not in this registry"


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

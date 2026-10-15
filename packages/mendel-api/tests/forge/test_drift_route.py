"""Route order, an id with slashes, and the refusal on the wire."""

from fastapi.testclient import TestClient
from mendel_api.main import create_app

CONTRACT = "nf-core/fastqc@0.12.1"


def test_the_drift_route_is_not_swallowed_by_the_contract_route():
    """`/{id:path}` is greedy. Registered after it, this route can never match — and the
    failure is a 200 with the WRONG BODY rather than a 404, which no other test would see."""
    client = TestClient(create_app())
    response = client.get(f"/api/contracts/{CONTRACT}/drift")
    assert response.status_code == 200
    assert "verdict" in response.json()
    assert "emits_total" not in response.json()  # that is the module page's shape


def test_the_report_carries_all_three_groups():
    client = TestClient(create_app())
    body = client.get(f"/api/contracts/{CONTRACT}/drift").json()
    assert {c["field"] for c in body["checks"]} == {"nf_process", "nf_include", "container"}
    assert {u["field"] for u in body["unchecked"]} >= {"consumes", "roles", "priority"}
    assert body["says"]


def test_an_unknown_contract_refuses_with_its_code():
    client = TestClient(create_app())
    response = client.get("/api/contracts/nf-core/nonesuch@1.0.0/drift")
    assert response.status_code == 422
    assert "MF0106" in response.json()["detail"]


def test_accepting_refuses_rather_than_raising():
    """The default configuration IS a detached HEAD — `registry/` is a submodule — and the
    shipped registry has no drift, so **both** refusals are correct here and which one fires
    depends on check order. Asserting one exactly would be asserting an implementation detail;
    what the route owes a caller is a coded 422 rather than a stack trace."""
    client = TestClient(create_app())
    response = client.post(
        f"/api/contracts/{CONTRACT}/drift/accept",
        json={"field": "nf_process", "by": "rafael", "why": "x"},
    )
    assert response.status_code == 422
    detail = response.json()["detail"]
    assert "MF0104" in detail or "MF0105" in detail

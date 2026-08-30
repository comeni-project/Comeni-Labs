"""The agent and the browser call the same verb. That is the whole point of it being here.

**There is no shared `client` fixture** — `conftest.py` has `clean_db` and
`broken_registry_copy` and nothing else. Every route test file builds its own, and this follows
that rather than adding a shared one nobody asked for.
"""

import pytest
from fastapi.testclient import TestClient
from mendel_api.main import create_app

STAR = "nf-core/star/align@1.11.0"
COUNTS = "nf-core/subread/featurecounts@2.0.6"
SORT = "nf-core/samtools/sort@1.21.0"


@pytest.fixture
def client():
    return TestClient(create_app(), raise_server_exceptions=False)


def test_an_illegal_graph_comes_back_with_its_findings(client):
    body = {
        "nodes": [
            {"id": "align", "contract_id": STAR},
            {"id": "counts", "contract_id": COUNTS},
        ],
        "edges": [
            {"from_node": "align", "from_port": "bam", "to_node": "counts", "to_port": "bam"}
        ],
    }
    response = client.post("/api/pipeline/validate", json=body)
    assert response.status_code == 200
    codes = {f["code"] for f in response.json()["findings"]}
    assert "MD0504" in codes


def test_validate_is_200_even_when_the_graph_is_wrong(client):
    """**It reports; it does not refuse.** A 422 here would make three problems into one."""
    body = {"nodes": [{"id": "x", "contract_id": STAR}], "edges": []}
    assert client.post("/api/pipeline/validate", json=body).status_code == 200


def test_an_unknown_contract_is_a_finding_not_a_500(client):
    body = {"nodes": [{"id": "x", "contract_id": "nf-core/nothing/here@1.0.0"}], "edges": []}
    response = client.post("/api/pipeline/validate", json=body)
    assert response.status_code == 200
    assert "MD0509" in {f["code"] for f in response.json()["findings"]}


def test_a_finding_names_each_end_of_the_wire(client):
    """The canvas draws findings onto wires; a finding with no anchor is a log line."""
    body = {
        "nodes": [
            {"id": "align", "contract_id": STAR},
            {"id": "counts", "contract_id": COUNTS},
        ],
        "edges": [
            {"from_node": "align", "from_port": "bam", "to_node": "counts", "to_port": "bam"}
        ],
    }
    findings = client.post("/api/pipeline/validate", json=body).json()["findings"]
    bad = next(f for f in findings if f["code"] == "MD0504")
    assert bad["source"] == "align.bam"
    assert bad["target"] == "counts.bam"


def test_the_index_carries_an_etag(client):
    first = client.get("/api/pipeline/compatibility")
    assert first.status_code == 200
    etag = first.headers["etag"]
    again = client.get("/api/pipeline/compatibility", headers={"If-None-Match": etag})
    assert again.status_code == 304


def test_a_stale_etag_gets_the_body(client):
    """A 304 on a digest that is not current would serve a client its own stale copy forever."""
    response = client.get("/api/pipeline/compatibility", headers={"If-None-Match": '"nonsense"'})
    assert response.status_code == 200
    assert response.json()["emits"]


def test_the_index_and_the_verb_agree_through_the_api(client):
    """The agreement test again, at the boundary — a serialiser can lose a state set."""
    index = client.get("/api/pipeline/compatibility").json()
    star = index["emits"][f"{STAR}#bam"]
    counts = index["requires"][f"{COUNTS}#bam"]
    assert not set(counts) & set(index["satisfies"][star])
    sorted_bam = index["emits"][f"{SORT}#bam"]
    assert set(counts) & set(index["satisfies"][sorted_bam])


def test_a_drawn_graph_lays_out_like_a_resolved_one(client):
    """**No new canvas.** `/draw` returns the same `BuiltPipeline` `/pipeline` does, so Plan 3C's
    canvas renders a hand-drawn graph without a component changing."""
    body = {
        "nodes": [
            {"id": "align", "contract_id": STAR},
            {"id": "sort", "contract_id": SORT},
        ],
        "edges": [
            {"from_node": "align", "from_port": "bam", "to_node": "sort", "to_port": "bam"}
        ],
    }
    view = client.post("/api/pipeline/draw", json=body).json()
    assert [n["id"] for n in view["layout"]["nodes"]] == ["align", "sort"]
    # **`x`, since Plan 4 phase 6** — the graph runs left to right, so two ranks differ along x
    # and a `y` assertion here would be checking for the downward layout that was replaced.
    assert view["layout"]["nodes"][0]["x"] != view["layout"]["nodes"][1]["x"], "not laid out"
    assert len(view["layout"]["wires"]) == 1


def test_a_drawn_graph_is_honest_about_its_tiers(client):
    """Every module choice a person made exits at tier 4 — they had a choice and made it.
    Invariant 6: flagged always, even when the person was certain."""
    body = {
        "nodes": [
            {"id": "align", "contract_id": STAR},
            {"id": "sort", "contract_id": SORT},
        ],
        "edges": [
            {"from_node": "align", "from_port": "bam", "to_node": "sort", "to_port": "bam"}
        ],
    }
    view = client.post("/api/pipeline/draw", json=body).json()
    assert set(view["needs_review"]) == {"align", "sort"}
    assert view["settled_share"] < 1.0

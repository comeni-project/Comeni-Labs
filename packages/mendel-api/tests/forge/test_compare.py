"""What Galaxy does not do. Legality is the floor; this is the screen's argument.

The alignment is a *judgement* — deciding that HISAT2 where Mendel put STAR is the same slot
rather than two unrelated steps — and that is why it is one endpoint rather than two calls
stitched together in the browser. Stitched in the browser, the judgement lives somewhere the
agent cannot reach, and then there are two answers to *how does my pipeline differ from
Mendel's*.
"""

from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient
from mendel_api.main import create_app

GOAL = yaml.safe_load(Path("examples/rnaseq-goal.yml").read_text())

STAR = "nf-core/star/align@1.11.0"
HISAT2 = "nf-core/hisat2/align@2.2.2"
SORT = "nf-core/samtools/sort@1.21.0"
COUNTS = "nf-core/subread/featurecounts@2.0.6"
GENOME = "nf-core/star/genomegenerate@1.11.0"


@pytest.fixture
def client():
    return TestClient(create_app(), raise_server_exceptions=False)


def _spine(align=STAR, index=GENOME):
    """The four-node spine, without the trimmer the resolver adds."""
    return {
        "nodes": [
            {"id": "index", "contract_id": index},
            {"id": "align", "contract_id": align},
            {"id": "sort", "contract_id": SORT},
            {"id": "counts", "contract_id": COUNTS},
        ],
        "edges": [
            {"from_node": "index", "from_port": "index", "to_node": "align", "to_port": "index"},
            {"from_node": "align", "from_port": "bam", "to_node": "sort", "to_port": "bam"},
            {"from_node": "sort", "from_port": "bam", "to_node": "counts", "to_port": "bam"},
        ],
    }


def _rows(client, graph, goal=None):
    body = {"graph": graph, "goal": goal or GOAL}
    response = client.post("/api/pipeline/compare", json=body)
    assert response.status_code == 200, response.text
    return response.json()


def test_the_missing_trimmer_is_reported_as_mendel_only(client):
    """**The real case, measured in Task 7.** The hand-drawn spine and `mendel build` differ by
    exactly one include — TRIMGALORE, which the resolver adds because `star/align.reads`
    declares `state_required_conventional: [trimmed]`. That difference is what this screen is
    for."""
    body = _rows(client, _spine())
    missing = [r for r in body["alignment"] if r["state"] == "mendel-only"]
    assert any("trimgalore" in (r["mendel_contract"] or "") for r in missing), missing


def test_it_carries_your_verdict_too(client):
    """One call, both answers."""
    body = _rows(client, _spine())
    assert "findings" in body["yours"]
    assert "steps" in body["mendel"]


def test_a_different_aligner_is_differs_not_two_unrelated_rows(client):
    """HISAT2 and STAR both emit `alignment.bam` with no state, so they fill one slot. Reporting
    them as `yours-only` plus `mendel-only` would make the screen say *add STAR, remove HISAT2*
    when what happened is *you chose differently*."""
    body = _rows(client, _spine(align=HISAT2))
    differs = [r for r in body["alignment"] if r["state"] == "differs"]
    assert any(
        (r["yours_contract"] or "").startswith("nf-core/hisat2")
        and (r["mendel_contract"] or "").startswith("nf-core/star")
        for r in differs
    ), body["alignment"]


def test_a_differing_row_carries_the_resolver_s_own_reason(client):
    """Why they differ, in the resolver's words rather than words this endpoint invented."""
    body = _rows(client, _spine(align=HISAT2))
    differs = [r for r in body["alignment"] if r["state"] == "differs"]
    assert all(r["why"] for r in differs), differs


def test_an_identical_graph_is_all_same(client):
    """Build the goal, turn the result back into a draft, compare it with itself. Nothing may
    read `differs` — if it does, the alignment rule is asymmetric and the diff shows noise."""
    built = client.post("/api/pipeline", json=GOAL).json()
    graph = {
        "nodes": [{"id": s["id"], "contract_id": s["contract_id"]} for s in built["steps"]],
        "edges": [
            {
                "from_node": w["from_node"],
                "from_port": w["from_port"],
                "to_node": w["to_node"],
                "to_port": w["to_port"],
            }
            for w in built["layout"]["wires"]
        ],
    }
    body = _rows(client, graph)
    assert {r["state"] for r in body["alignment"]} == {"same"}, body["alignment"]


def test_the_alignment_is_deterministic(client):
    """Same inputs, same order. A diff that reorders between two calls is unreadable."""
    first = _rows(client, _spine())
    again = _rows(client, _spine())
    assert first["alignment"] == again["alignment"]


def test_an_extra_step_of_yours_is_yours_only(client):
    """`samtools/index` produces a BAI nothing in the goal asks for. Not an error — you may
    want it — but the resolver did not reach for it and the screen should say so."""
    graph = _spine()
    graph["nodes"].append({"id": "idx", "contract_id": "nf-core/samtools/index@1.21.0"})
    graph["edges"].append(
        {"from_node": "sort", "from_port": "bam", "to_node": "idx", "to_port": "bam"}
    )
    body = _rows(client, graph)
    yours = [r for r in body["alignment"] if r["state"] == "yours-only"]
    assert any("samtools/index" in (r["yours_contract"] or "") for r in yours), body["alignment"]

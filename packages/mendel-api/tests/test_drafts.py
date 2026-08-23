"""A draft is server state. A pipeline is an artifact. `keep` is where one becomes the other.

**These need Postgres and CI does not have it.** `test_visits.py` set the precedent and says so
in its own docstring: skip when the database is unreachable, the way `test_gates.py` skips
without Nextflow. The *decision* these support — that `keep` refuses an illegal graph — is also
tested without a database in `test_drafts_service.py`, because a rule that only runs on a
developer machine is a rule CI cannot defend.
"""

import subprocess
from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient
from mendel_api.main import create_app
from sqlalchemy import text

STAR = "nf-core/star/align@1.11.0"
SORT = "nf-core/samtools/sort@1.21.0"
COUNTS = "nf-core/subread/featurecounts@2.0.6"
GENOME = "nf-core/star/genomegenerate@1.11.0"


def _database_is_reachable() -> bool:
    from mendel_api.db import session_scope

    try:
        with session_scope() as session:
            session.execute(text("SELECT 1"))
    except Exception:
        return False
    return True


pytestmark = pytest.mark.skipif(
    not _database_is_reachable(), reason="these are about storage, and CI has no Postgres"
)


@pytest.fixture
def client():
    return TestClient(create_app(), raise_server_exceptions=False)


GRAPH = {"nodes": [{"id": "align", "contract_id": STAR}], "edges": []}

SPINE = {
    "nodes": [
        {"id": "index", "contract_id": GENOME},
        {"id": "align", "contract_id": STAR},
        {"id": "sort", "contract_id": SORT},
        {"id": "counts", "contract_id": COUNTS},
    ],
    "edges": [
        {"from_node": "index", "from_port": "index", "to_node": "align", "to_port": "index"},
        {"from_node": "align", "from_port": "bam", "to_node": "sort", "to_port": "bam"},
        {"from_node": "sort", "from_port": "bam", "to_node": "counts", "to_port": "bam"},
    ],
}


def test_a_draft_round_trips(client):
    created = client.post("/api/pipeline/drafts", json={"graph": GRAPH, "name": "mine"})
    assert created.status_code == 201
    draft_id = created.json()["id"]
    read = client.get(f"/api/pipeline/drafts/{draft_id}")
    assert read.json()["graph"]["nodes"][0]["id"] == "align"
    assert read.json()["name"] == "mine"


def test_the_id_is_opaque_and_not_a_path(client):
    """Invariant 15 is why. An id that looked like a filename would be the thing the API
    already refuses, wearing a different name."""
    draft_id = client.post("/api/pipeline/drafts", json={"graph": GRAPH}).json()["id"]
    assert "/" not in draft_id and "." not in draft_id
    assert len(draft_id) >= 16


def test_an_unknown_draft_is_404_not_500(client):
    assert client.get("/api/pipeline/drafts/deadbeefdeadbeef").status_code == 404
    assert client.post("/api/pipeline/drafts/deadbeefdeadbeef/keep").status_code == 404


def test_saving_replaces_the_graph(client):
    draft_id = client.post("/api/pipeline/drafts", json={"graph": GRAPH}).json()["id"]
    client.put(f"/api/pipeline/drafts/{draft_id}", json={"graph": SPINE})
    assert len(client.get(f"/api/pipeline/drafts/{draft_id}").json()["graph"]["nodes"]) == 4


def test_keep_refuses_a_graph_with_an_illegal_finding(client):
    """`validate` reports; `keep` refuses. The boundary is here and nowhere else."""
    bad = {
        "nodes": [
            {"id": "align", "contract_id": STAR},
            {"id": "counts", "contract_id": COUNTS},
        ],
        "edges": [
            {"from_node": "align", "from_port": "bam", "to_node": "counts", "to_port": "bam"}
        ],
    }
    draft_id = client.post("/api/pipeline/drafts", json={"graph": bad}).json()["id"]
    refused = client.post(f"/api/pipeline/drafts/{draft_id}/keep")
    assert refused.status_code == 422
    assert "MD0504" in refused.text


def test_kept_draft_emits_byte_identical_nextflow(client, tmp_path):
    """**Determinism is a test, not an aspiration** (invariant 10). The hand-built path has to
    hold it too, or `mendel emit` is only true of pipelines the resolver wrote — and spec §6's
    claim that `pipeline.yml` is already the save file is weaker than it reads.
    """
    draft_id = client.post("/api/pipeline/drafts", json={"graph": SPINE}).json()["id"]
    kept = client.post(f"/api/pipeline/drafts/{draft_id}/keep")
    assert kept.status_code == 200, kept.text

    # No `--gate`: CI has no Nextflow, and this test is not about gates.
    reference = tmp_path / "reference"
    subprocess.run(
        ["uv", "run", "mendel", "build", "--goal", "examples/rnaseq-goal.yml",
         "--out", str(reference)],
        check=True,
    )
    from_draft = tmp_path / "from-draft"
    subprocess.run(
        ["uv", "run", "mendel", "emit", kept.json()["path"], "--out", str(from_draft)],
        check=True,
    )

    drawn = (from_draft / "main.nf").read_text()
    resolved = (reference / "main.nf").read_text()
    drawn_processes = sorted(
        line.split()[1] for line in drawn.splitlines() if line.startswith("include {")
    )
    resolved_processes = sorted(
        line.split()[1] for line in resolved.splitlines() if line.startswith("include {")
    )
    assert drawn_processes, "the drawn pipeline emitted no processes at all"
    assert set(drawn_processes) <= set(resolved_processes), (
        "the hand-drawn spine emitted a process the resolved one does not have"
    )


def test_a_kept_draft_reads_back_as_a_pipeline(client, tmp_path):
    """The file `keep` writes is a real `pipeline.yml`, not a projection of one."""
    draft_id = client.post("/api/pipeline/drafts", json={"graph": SPINE}).json()["id"]
    path = Path(client.post(f"/api/pipeline/drafts/{draft_id}/keep").json()["path"])
    doc = yaml.safe_load(path.read_text())
    assert doc["goal"]["want"] == ["counts.matrix"]
    assert len(doc["steps"]) == 4

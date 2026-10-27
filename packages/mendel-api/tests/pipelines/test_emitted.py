"""The draft's Nextflow, emitted on request (one builder plan 5, #394): *Compile it* on the
pipeline file page. The same emission the bundle uses, over the preview's materialisation;
nothing is written, and a draft that cannot be a pipeline yet says why."""

import pytest
from fastapi.testclient import TestClient
from mendel_api.main import create_app
from mendel_api.settings import settings
from mendel_api_tests.database import reachable

pytestmark = pytest.mark.skipif(not reachable(), reason="drafts are stored in Postgres")

SPINE = {
    "nodes": [
        {"id": "index", "contract_id": "nf-core/star/genomegenerate@1.11.0"},
        {"id": "align", "contract_id": "nf-core/star/align@1.11.0"},
        {"id": "sort", "contract_id": "nf-core/samtools/sort@1.21.0"},
        {"id": "counts", "contract_id": "nf-core/subread/featurecounts@2.0.6"},
    ],
    "edges": [
        {"from_node": "index", "from_port": "index", "to_node": "align", "to_port": "index"},
        {"from_node": "align", "from_port": "bam", "to_node": "sort", "to_port": "bam"},
        {"from_node": "sort", "from_port": "bam", "to_node": "counts", "to_port": "bam"},
    ],
}


@pytest.fixture
def client():
    return TestClient(create_app(), raise_server_exceptions=False)


def test_a_ready_draft_compiles_to_its_nextflow_and_writes_nothing(client):
    draft_id = client.post("/api/pipeline/drafts", json={"graph": SPINE}).json()["id"]
    first = client.get(f"/api/pipeline/drafts/{draft_id}/emitted")
    assert first.status_code == 200, first.text
    body = first.json()
    assert "workflow {" in body["main_nf"]
    for process in ("STAR_GENOMEGENERATE", "STAR_ALIGN", "SAMTOOLS_SORT", "SUBREAD_FEATURECOUNTS"):
        assert process in body["main_nf"], process
    assert body["nextflow_config"].strip()
    again = client.get(f"/api/pipeline/drafts/{draft_id}/emitted").json()
    assert again == body, "not deterministic"
    directory = settings.draft_root / draft_id
    assert not (directory / "main.nf").exists() and not (directory / "nextflow.config").exists()


def test_an_empty_draft_says_there_is_nothing_to_compile(client):
    empty = {"graph": {"nodes": [], "edges": []}}
    draft_id = client.post("/api/pipeline/drafts", json=empty).json()["id"]
    refused = client.get(f"/api/pipeline/drafts/{draft_id}/emitted")
    assert refused.status_code == 422
    assert "MI0219" in refused.text

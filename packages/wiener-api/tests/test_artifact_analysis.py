"""Which analysis sent a run, carried across the courier (#536).

Runs were matched to their analysis by the pipeline's digest, so any change to the pipeline after
a run (one setting) orphaned every earlier run: *Runs of this analysis* lost them and *Run 1*
became *Run e02d4db2*. The browser sends the analysis it is in with the upload, as it sends the
name; optional, so a hand upload is ordinary.
"""

import io
import zipfile


def _bundle() -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("main.nf", "workflow {}\n")
    return buffer.getvalue()


def test_a_run_says_which_analysis_sent_it(client):
    stored = client.post("/api/artifacts", files={"bundle": ("run.zip", _bundle())},
                         data={"name": "yeast", "analysis": "3a0fe354aa1f0e8c46813af09781cf3f"})
    assert stored.status_code == 201, stored.text
    run_id = client.post("/api/runs", json={"artifact_id": stored.json()["artifact_id"],
                                            "params": {}}).json()["run_id"]
    row = next(r for r in client.get("/api/runs").json()["runs"] if r["id"] == run_id)
    assert row["analysis"] == "3a0fe354aa1f0e8c46813af09781cf3f"


def test_a_hand_upload_has_no_analysis(client):
    stored = client.post("/api/artifacts", files={"bundle": ("run.zip", _bundle())})
    run_id = client.post("/api/runs", json={"artifact_id": stored.json()["artifact_id"],
                                            "params": {}}).json()["run_id"]
    row = next(r for r in client.get("/api/runs").json()["runs"] if r["id"] == run_id)
    assert row["analysis"] == ""


def test_an_analysis_is_an_id_not_text(client):
    """Only an id shape is kept: a path or a sentence is refused, so nothing else rides along."""
    refused = client.post("/api/artifacts", files={"bundle": ("run.zip", _bundle())},
                          data={"analysis": "../../etc/passwd"})
    assert refused.status_code == 422

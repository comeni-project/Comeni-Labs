"""The default view's endpoint. **It answers where `/graph` refuses** — A192."""

import json
from pathlib import Path

FIXTURE = Path(__file__).parents[3] / "tests/fixtures/weblog/failing-run.jsonl"


def _ingest(ingest_client, a_run):
    for line in FIXTURE.read_text().splitlines():
        if line.strip():
            ingest_client.post(f"/events/{a_run.id}/{a_run.ingest_secret}",
                               json=json.loads(line))


def test_an_unreadable_artifact_still_answers(client, ingest_client, a_run):
    """A192. `/graph` 404s here and this must not: the counts are folded from events and are
    worth showing. A 404 on the DEFAULT view turns a readable run into a blank page."""
    _ingest(ingest_client, a_run)

    assert client.get(f"/api/runs/{a_run.id}/graph").status_code == 404, (
        "the premise: this run's artifact cannot be read"
    )
    answer = client.get(f"/api/runs/{a_run.id}/overview")
    assert answer.status_code == 200
    body = answer.json()
    assert body["steps_declared"] == 0
    assert body["rows"] and all(row["declared"] is False for row in body["rows"])


def _spine_bundle() -> bytes:
    """The real emitted spine, zipped — the overview needs an artifact it can read."""
    import io
    import zipfile

    spine = Path(__file__).parents[3] / "tests/fixtures/pipeline/rnaseq-spine.yml"
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("pipeline.yml", spine.read_text())
        archive.writestr("main.nf", "workflow {}\n")
        archive.writestr("nextflow.config", "params {\n    input = null\n}\n")
    return buffer.getvalue()


def test_every_declared_step_is_a_row_before_the_run_starts(client):
    """The front door's shape is known at submission. A run that has done nothing still
    answers with its whole pipeline, which is where the reader learns what it will do."""
    artifact = client.post("/api/artifacts",
                           files={"bundle": ("p.zip", _spine_bundle())}).json()
    run_id = client.post("/api/runs", json={"artifact_id": artifact["artifact_id"],
                                            "params": {"input": "x"}}).json()["run_id"]

    body = client.get(f"/api/runs/{run_id}/overview").json()
    assert body["steps_declared"] == 5 and body["steps_finished"] == 0
    assert len(body["rows"]) == 5
    assert all(row["declared"] and not row["reached"] for row in body["rows"])
    assert all(row["memory_peak_bytes"] is None for row in body["rows"]), "absent, not zero"


def test_an_unknown_run_has_no_overview(client):
    assert client.get("/api/runs/nope/overview").status_code == 404

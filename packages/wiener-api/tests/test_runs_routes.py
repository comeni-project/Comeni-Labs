"""Upload, submit, read. The public surface — `docs/design/wiener.md` §13."""

import io
import zipfile


def test_an_uploaded_artifact_is_content_addressed(client, a_bundle):
    response = client.post("/api/artifacts", files={"bundle": ("p.zip", a_bundle)})
    assert response.status_code == 201
    assert len(response.json()["digest"]) == 71  # "sha256:" + 64


def test_the_digest_is_over_the_tree_and_not_over_the_zip(client, a_bundle):
    """Two archives of the same files, built differently, must agree — the whole reason the
    digest walks sorted (path, sha256) pairs rather than hashing the upload."""
    other = io.BytesIO()
    with zipfile.ZipFile(other, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("nextflow.config", "params {\n    input = null\n    fasta = null\n}\n")
        archive.writestr("pipeline.yml", "schema_version: 5\n")   # reversed order, compressed
        archive.writestr("main.nf", "workflow {}\n")

    first = client.post("/api/artifacts", files={"bundle": ("a.zip", a_bundle)}).json()
    second = client.post("/api/artifacts", files={"bundle": ("b.zip", other.getvalue())}).json()
    assert first["digest"] == second["digest"]
    assert first["artifact_id"] != second["artifact_id"]


def test_an_archive_that_escapes_its_directory_is_refused(client):
    """The upload is authenticated by nothing in W1 (§12.1), so a member named `../` is
    checked here rather than trusted to whoever posts it."""
    hostile = io.BytesIO()
    with zipfile.ZipFile(hostile, "w") as archive:
        archive.writestr("../escaped.txt", "no")
    assert client.post(
        "/api/artifacts", files={"bundle": ("evil.zip", hostile.getvalue())}
    ).status_code == 422


def test_submitting_a_run_returns_an_opaque_id_and_queues_work(client, a_bundle):
    artifact = client.post("/api/artifacts", files={"bundle": ("p.zip", a_bundle)}).json()
    params = {"input": "s3://lab/sheet.csv", "fasta": "s3://refs/GRCh38.fa"}
    response = client.post("/api/runs", json={"artifact_id": artifact["artifact_id"],
                                              "params": params, "executor": "local"})
    assert response.status_code == 202 and len(response.json()["run_id"]) == 32
    assert client.queued == [("launch_job", (response.json()["run_id"], params))]


def test_a_key_the_artifact_never_declared_is_refused(client, a_bundle):
    """**The artifact is the schema.** Mendel emits `= null` for every value only the lab can
    supply, so a submission fills precisely those — and a typo, or a parameter this pipeline
    does not have, is refused rather than silently ignored by Nextflow."""
    artifact = client.post("/api/artifacts", files={"bundle": ("p.zip", a_bundle)}).json()
    response = client.post("/api/runs", json={
        "artifact_id": artifact["artifact_id"],
        "params": {"input": "x", "fasta": "y", "gtf": "z"},   # this artifact has no gtf hole
    })
    assert response.status_code == 422
    assert response.json()["detail"]["unknown"] == ["gtf"]


def test_a_hole_left_unfilled_is_refused(client, a_bundle):
    """The other direction. Nextflow would fail deep inside the run with `Missing fromPath
    parameter`; refusing at submit says which parameter, before anything is launched."""
    artifact = client.post("/api/artifacts", files={"bundle": ("p.zip", a_bundle)}).json()
    response = client.post("/api/runs", json={"artifact_id": artifact["artifact_id"],
                                              "params": {"input": "x"}})
    assert response.status_code == 422
    assert response.json()["detail"] == {
        "message": "a run fills exactly the parameters the artifact leaves null",
        "declared": ["fasta", "input"], "unknown": [], "missing": ["fasta"],
    }


def test_the_params_reach_a_params_file_and_the_argv(client, a_bundle, session, tmp_path,
                                                     monkeypatch):
    """End of the path: submit -> job argument -> params.json -> `-params-file`.

    A **list** value survives, which a `--input` splice could not carry — the emitted spine
    reads `params.input instanceof List`, so this is not hypothetical.
    """
    import json

    from wiener_api import repository
    from wiener_api.services import launcher
    from wiener_api.settings import settings

    artifact = client.post("/api/artifacts", files={"bundle": ("p.zip", a_bundle)}).json()
    params = {"input": ["r1.fastq.gz", "r2.fastq.gz"], "fasta": "/refs/GRCh38.fa"}
    run_id = client.post("/api/runs", json={"artifact_id": artifact["artifact_id"],
                                            "params": params}).json()["run_id"]
    _, (queued_id, queued_params) = client.queued[0]
    assert (queued_id, queued_params) == (run_id, params)

    monkeypatch.setattr(launcher, "_spawn", lambda argv, cwd: None)
    launcher.launch(run_id, queued_params)

    workdir = launcher.work_dir(run_id)
    assert json.loads((workdir / "params.json").read_text()) == params
    run = repository.run(session, settings.lab_id, run_id)
    argv = launcher.command(run, workdir=str(workdir), has_params=True)
    assert argv[argv.index("-params-file") + 1] == f"{workdir}/params.json"


def test_no_route_accepts_a_server_path(client, a_bundle):
    """§12: Wiener chooses where things live. A client naming a directory is the defect Plan
    3A phase 6 deleted a whole transport over."""
    artifact = client.post("/api/artifacts", files={"bundle": ("p.zip", a_bundle)}).json()
    assert client.post("/api/runs", json={"artifact_id": artifact["artifact_id"],
                                          "params": {"input": "x", "fasta": "y"},
                                          "work_dir": "/etc"}).status_code == 422


def test_submitting_an_unknown_artifact_is_refused(client):
    assert client.post("/api/runs", json={"artifact_id": "0" * 32,
                                          "params": {}}).status_code == 404


def test_an_executor_nothing_has_run_on_is_refused(client, a_bundle):
    """`Literal["local"]` until W5 — an enum offering `awsbatch` before anything has run there
    is a lie the API tells its own generated client, which would put it in a dropdown."""
    artifact = client.post("/api/artifacts", files={"bundle": ("p.zip", a_bundle)}).json()
    assert client.post("/api/runs", json={"artifact_id": artifact["artifact_id"],
                                          "params": {"input": "x", "fasta": "y"},
                                          "executor": "awsbatch"}).status_code == 422


def test_the_board_lists_runs_newest_first(client, a_bundle):
    artifact = client.post("/api/artifacts", files={"bundle": ("p.zip", a_bundle)}).json()
    ids = [client.post("/api/runs", json={"artifact_id": artifact["artifact_id"],
                                          "params": {"input": "x", "fasta": "y"}}).json()["run_id"]
           for _ in range(3)]
    assert [row["id"] for row in client.get("/api/runs").json()] == list(reversed(ids))


def _spine_bundle() -> bytes:
    """The real emitted spine, zipped — the graph route needs an artifact it can read."""
    import io
    import zipfile
    from pathlib import Path

    spine = Path(__file__).parents[3] / "tests/fixtures/pipeline/rnaseq-spine.yml"
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("pipeline.yml", spine.read_text())
        archive.writestr("main.nf", "workflow {}\n")
        archive.writestr("nextflow.config", "params {\n    input = null\n}\n")
    return buffer.getvalue()


def test_the_graph_is_the_pipelines_own_layout(client, session):
    """§9.1: nothing new is computed. Five steps in, five placed nodes out, and a producer
    above its consumer — the same arithmetic the builder's canvas draws."""
    artifact = client.post("/api/artifacts",
                           files={"bundle": ("p.zip", _spine_bundle())}).json()
    run_id = client.post("/api/runs", json={"artifact_id": artifact["artifact_id"],
                                            "params": {"input": "x"}}).json()["run_id"]

    graph = client.get(f"/api/runs/{run_id}/graph").json()
    assert len(graph["nodes"]) == 5 and graph["wires"]
    by_id = {node["id"]: node for node in graph["nodes"]}
    assert by_id["trimgalore"]["y"] < by_id["star_align"]["y"] < by_id["samtools_sort"]["y"]
    assert graph["width"] > 0 and graph["height"] > 0


def test_a_graph_for_a_run_that_has_done_nothing_still_draws_every_step(client):
    """A run that failed early still has a whole pipeline, and the steps that never started are
    what tell you where it stopped."""
    artifact = client.post("/api/artifacts",
                           files={"bundle": ("p.zip", _spine_bundle())}).json()
    run_id = client.post("/api/runs", json={"artifact_id": artifact["artifact_id"],
                                            "params": {"input": "x"}}).json()["run_id"]

    graph = client.get(f"/api/runs/{run_id}/graph").json()
    assert all(node["total"] == 0 for node in graph["nodes"])
    assert not any(wire["active"] for wire in graph["wires"]), "nothing is running"


def test_the_graph_carries_no_lab_string(client):
    """§8's rule is about span attributes and the reason behind it is not: `script`, `workdir`
    and `tag` are the fields a laboratory's own words reach, and a graph is a screenshot people
    paste into tickets."""
    artifact = client.post("/api/artifacts",
                           files={"bundle": ("p.zip", _spine_bundle())}).json()
    run_id = client.post("/api/runs", json={"artifact_id": artifact["artifact_id"],
                                            "params": {"input": "/data/PT-4471/sheet.csv"}}
                         ).json()["run_id"]

    body = client.get(f"/api/runs/{run_id}/graph").text
    assert "PT-4471" not in body and ".csv" not in body


def test_an_unknown_run_has_no_graph(client):
    assert client.get("/api/runs/nope/graph").status_code == 404

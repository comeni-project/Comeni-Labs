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
    response = client.post("/api/runs", json={"artifact_id": artifact["artifact_id"],
                                              "samplesheet": "s3://lab/sheet.csv",
                                              "executor": "local"})
    assert response.status_code == 202 and len(response.json()["run_id"]) == 32
    assert client.queued == [("launch_job", (response.json()["run_id"], "s3://lab/sheet.csv"))]


def test_the_samplesheet_reaches_the_command_line(client, a_bundle, session):
    """**Nothing else carries it.** §7.1 forbids a column, so the value rides in the job
    argument and must land on the head process's argv as `--input`. The plan accepted a
    samplesheet at this route and passed it to nothing; Checkpoint 2's own script submits
    `"-"`, so no step in this phase would have caught that.
    """
    from wiener_api import repository
    from wiener_api.services.launcher import command
    from wiener_api.settings import settings

    artifact = client.post("/api/artifacts", files={"bundle": ("p.zip", a_bundle)}).json()
    run_id = client.post("/api/runs", json={"artifact_id": artifact["artifact_id"],
                                            "samplesheet": "/data/sheet.csv"}).json()["run_id"]
    _, (queued_id, samplesheet) = client.queued[0]
    assert queued_id == run_id

    run = repository.run(session, settings.lab_id, run_id)
    argv = command(run, workdir="/tmp/x", samplesheet=samplesheet)
    assert argv[argv.index("--input") + 1] == "/data/sheet.csv"


def test_no_route_accepts_a_server_path(client, a_bundle):
    """§12: Wiener chooses where things live. A client naming a directory is the defect Plan
    3A phase 6 deleted a whole transport over."""
    artifact = client.post("/api/artifacts", files={"bundle": ("p.zip", a_bundle)}).json()
    assert client.post("/api/runs", json={"artifact_id": artifact["artifact_id"],
                                          "samplesheet": "x",
                                          "work_dir": "/etc"}).status_code == 422


def test_submitting_an_unknown_artifact_is_refused(client):
    assert client.post("/api/runs", json={"artifact_id": "0" * 32,
                                          "samplesheet": "x"}).status_code == 404


def test_an_executor_nothing_has_run_on_is_refused(client, a_bundle):
    """`Literal["local"]` until W5 — an enum offering `awsbatch` before anything has run there
    is a lie the API tells its own generated client, which would put it in a dropdown."""
    artifact = client.post("/api/artifacts", files={"bundle": ("p.zip", a_bundle)}).json()
    assert client.post("/api/runs", json={"artifact_id": artifact["artifact_id"],
                                          "samplesheet": "x",
                                          "executor": "awsbatch"}).status_code == 422


def test_the_board_lists_runs_newest_first(client, a_bundle):
    artifact = client.post("/api/artifacts", files={"bundle": ("p.zip", a_bundle)}).json()
    ids = [client.post("/api/runs", json={"artifact_id": artifact["artifact_id"],
                                          "samplesheet": "x"}).json()["run_id"]
           for _ in range(3)]
    assert [row["id"] for row in client.get("/api/runs").json()] == list(reversed(ids))

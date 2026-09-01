"""What a person called a pipeline, carried across the courier — Plan 6 phase 2.

**The name was never missing; it was dropped in transit.** `mendel_api.models`'
`PipelineDraft.name` has held it since Plan 3E and `Pipeline` has none, so the name existed at
one end of the courier, was wanted at the other, and nothing carried it. The run header read
`run aa11bb22` while the builder in the next tab called the same thing `rnaseq-counts`.

**Optional at every point, and these tests are mostly about that.** An air-gapped site
uploading a `mendel build` artifact with `curl -F bundle=@run.zip` is invariant 13's customer,
not a degraded one — so the absence of a name has to be an ordinary state rather than an error
or an empty-looking bug.
"""

import io
import zipfile
from datetime import UTC, datetime

from wiener_api import repository
from wiener_api.models import RunArtifact
from wiener_api.settings import settings


def _bundle() -> bytes:
    """The smallest thing `store()` accepts — this is about the name, not the artifact."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("main.nf", "workflow {}\n")
    return buffer.getvalue()


def test_the_name_reaches_both_the_board_and_the_run(client, session):
    """**The whole claim, end to end.** Upload with a name, run it, and read the name back off
    the two screens that show it — the board row and the run header. Asserting only that the
    upload took would pass with the column written and nothing reading it, which is the shape
    of a field that exists and is invisible.
    """
    stored = client.post("/api/artifacts", files={"bundle": ("run.zip", _bundle())},
                         data={"name": "rnaseq-counts"})
    assert stored.status_code == 201, stored.text
    artifact_id = stored.json()["artifact_id"]

    accepted = client.post("/api/runs", json={"artifact_id": artifact_id, "params": {}})
    assert accepted.status_code == 202, accepted.text
    run_id = accepted.json()["run_id"]

    board = client.get("/api/runs").json()
    row = next(r for r in board["runs"] if r["id"] == run_id)
    assert row["name"] == "rnaseq-counts"

    assert client.get(f"/api/runs/{run_id}").json()["name"] == "rnaseq-counts"


def test_a_run_whose_artifact_has_no_name_says_so_with_an_empty_string(client):
    """`run <id>` is what the header draws then — the same thing it drew before this existed.
    **Never a name derived from the digest**: a name nobody chose is worse than none, because
    a reader cannot tell the two apart."""
    stored = client.post("/api/artifacts", files={"bundle": ("run.zip", _bundle())})
    accepted = client.post("/api/runs",
                           json={"artifact_id": stored.json()["artifact_id"], "params": {}})
    run_id = accepted.json()["run_id"]

    assert client.get(f"/api/runs/{run_id}").json()["name"] == ""
    row = next(r for r in client.get("/api/runs").json()["runs"] if r["id"] == run_id)
    assert row["name"] == ""


def test_an_upload_without_a_name_is_ordinary_and_not_an_error(client):
    """**`curl -F bundle=@run.zip` has no name to send** and must keep working. A required
    field here would make an air-gapped upload a 422 — invariant 13, self-hosted is not a
    degraded tier."""
    got = client.post("/api/artifacts", files={"bundle": ("run.zip", _bundle())})
    assert got.status_code == 201, got.text


def test_an_unnamed_artifact_is_absent_from_the_map_rather_than_empty(session):
    """Absence and `""` are one fact and must have one spelling, so the caller has one rule:
    `names.get(id, "")` and draw `run <id>`. Two spellings is what a reader has to remember."""
    repository.add(session, settings.lab_id, RunArtifact(
        id="a" * 32, uploaded_by="operator", uploaded_at=datetime.now(UTC),
        digest="sha256:" + "0" * 64, size_bytes=1, name="",
    ))
    repository.add(session, settings.lab_id, RunArtifact(
        id="b" * 32, uploaded_by="operator", uploaded_at=datetime.now(UTC),
        digest="sha256:" + "1" * 64, size_bytes=1, name="rnaseq-counts",
    ))
    session.flush()

    got = repository.artifact_names(session, settings.lab_id, ["a" * 32, "b" * 32])
    assert got == {"b" * 32: "rnaseq-counts"}


def test_a_name_is_not_folded_into_the_projection(session):
    """**`RunState` is what `wiener-core` folded from the events, and a name is not an event.**

    A field on the pure type that no event can produce is how a projection stops being
    replayable from its own record — §7.1's whole claim. The route attaches it beside the
    dump; the fold never sees it.
    """
    from wiener_core.state import RunState

    assert "name" not in RunState.model_fields, (
        "a name came off an upload, not out of the record — it cannot live on the fold"
    )


def test_the_name_is_bounded(client):
    """The column is `String(200)` and a form field is whatever somebody posts. Truncating at
    the boundary means the database never refuses a row for a reason the API could have
    handled, which is a 500 where a 201 belongs."""
    got = client.post("/api/artifacts", files={"bundle": ("run.zip", _bundle())},
                      data={"name": "x" * 500})
    assert got.status_code == 201, got.text

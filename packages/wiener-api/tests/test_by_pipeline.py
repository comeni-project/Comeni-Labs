"""`vs usual` — the board's best number, and the `GROUP BY` the repository could not do.

`rn-board`: *a median in the abstract is trivia; the same median beside a run is a judgement.*
It earned its place only by moving onto a row, and it needs a key that survives the trip between
the two halves — which is what `RunArtifact.pipeline_digest` is for.
"""

from datetime import UTC, datetime, timedelta

from wiener_api import repository
from wiener_api.models import Run, RunArtifact
from wiener_api.settings import settings


def _artifact(session, digest: str | None) -> str:
    import secrets

    artifact_id = secrets.token_hex(16)
    session.add(RunArtifact(
        id=artifact_id, lab_id=settings.lab_id, uploaded_by="test",
        uploaded_at=datetime.now(UTC), digest="sha256:" + "0" * 64,
        pipeline_digest=digest, size_bytes=1, note="",
    ))
    session.commit()
    return artifact_id


def _finished(session, artifact_id: str, minutes: int) -> None:
    import secrets

    started = datetime.now(UTC) - timedelta(days=1)
    session.add(Run(
        id=secrets.token_hex(16), lab_id=settings.lab_id, artifact_id=artifact_id,
        submitted_by="test", submitted_at=started, phase="succeeded", executor="local",
        ingest_secret="x", ended_at=started + timedelta(minutes=minutes),
    ))
    session.commit()


def test_a_median_is_grouped_by_pipeline_and_not_by_artifact(session):
    """Two uploads of the SAME pipeline are one pipeline.

    That is the whole reason the key is a content digest rather than an artifact id: the browser
    re-uploads on every run, so grouping by `artifact_id` would give every run its own group and
    every group a sample of one.
    """
    digest = "sha256:" + "a" * 64
    for minutes in (10, 20, 30):
        _finished(session, _artifact(session, digest), minutes)

    medians = repository.durations_by_pipeline(session, settings.lab_id)
    assert medians[digest] == 20 * 60 * 1000


def test_a_median_needs_enough_runs_to_be_one(session):
    """**Absent, not a number.** *Usually 38m* over two runs is one figure wearing the clothes
    of a distribution, and a page that showed it would invite a reader to treat noise as a
    baseline."""
    digest = "sha256:" + "b" * 64
    _finished(session, _artifact(session, digest), 10)
    _finished(session, _artifact(session, digest), 90)

    assert digest not in repository.durations_by_pipeline(session, settings.lab_id, floor=3)
    assert digest in repository.durations_by_pipeline(session, settings.lab_id, floor=2)


def test_a_run_that_never_finished_is_not_a_fast_run(session):
    """`board_summary` already makes this argument for the instance-wide median; the same
    mistake per pipeline would be the same lie four times over."""
    digest = "sha256:" + "c" * 64
    for minutes in (10, 20, 30):
        _finished(session, _artifact(session, digest), minutes)

    import secrets
    session.add(Run(
        id=secrets.token_hex(16), lab_id=settings.lab_id,
        artifact_id=_artifact(session, digest), submitted_by="test",
        submitted_at=datetime.now(UTC), phase="running", executor="local", ingest_secret="x",
    ))
    session.commit()

    assert repository.durations_by_pipeline(session, settings.lab_id)[digest] == 20 * 60 * 1000


def test_an_artifact_with_no_key_is_left_out_rather_than_lumped_together(session):
    """Artifacts uploaded before the key was recorded have `None`, and `None` is not a pipeline.

    Grouping them would put every unattributable run in one bucket and report a median for a
    "pipeline" that is really the set of everything we cannot identify.
    """
    for minutes in (10, 20, 30):
        _finished(session, _artifact(session, None), minutes)

    assert None not in repository.durations_by_pipeline(session, settings.lab_id)


def test_the_summary_carries_the_medians(client, session):
    digest = "sha256:" + "d" * 64
    for minutes in (10, 20, 30):
        _finished(session, _artifact(session, digest), minutes)

    body = client.get("/api/runs/summary").json()
    assert body["by_pipeline"][digest] == 20 * 60 * 1000

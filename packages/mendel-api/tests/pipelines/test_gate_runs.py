"""A gate's row, from the ask to an end state it always reaches (issue 278).

`test_gate_service.py` holds what a gate does with no database. These hold what the row says:
a gate that breaks, is cancelled or is lost lands `failed` with a reason, and one draft has at
most one live gate. They need Postgres, and skip without it, as `test_drafts.py` does.
"""

import asyncio
from datetime import UTC, datetime, timedelta

import pytest
from comeni_core.artifact.gates import Gate
from mendel_api.db import session_scope
from mendel_api.models import GateRun, PipelineDraft
from mendel_api.services import gates
from mendel_api_tests.database import reachable, truncate
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

pytestmark = pytest.mark.skipif(
    not reachable(), reason="these are about storage, and CI has no Postgres"
)


@pytest.fixture
def clean():
    """No gates, and two drafts, `d1` and `d2`, for them to belong to: a gate's draft is a key
    (issue 274). Everything that references `pipeline_draft` goes in the one `TRUNCATE`."""
    now = datetime.now(UTC)
    with session_scope() as session:
        session.execute(
            truncate(
                "TRUNCATE TABLE gate_run, pipeline_authoring_proposal, pipeline_authoring_turn, "
                "pipeline_authoring_session, pipeline_draft, gate_run"
            )
        )
        for draft_id in ("d1", "d2"):
            session.add(PipelineDraft(id=draft_id, who="ana", graph={}, updated_at=now))
    yield


def _row(run_id: str) -> GateRun:
    with session_scope() as session:
        row = session.get(GateRun, run_id)
        session.expunge(row)
        return row


def _raising(error: BaseException):
    def of(directory, gate):
        raise error

    return of


def test_a_gate_that_breaks_lands_failed_with_its_reason(clean, monkeypatch, tmp_path):
    """`execute` caught only `ValueError`, so anything else left the row `running` forever."""
    monkeypatch.setattr(gates, "_directory", lambda draft_id: tmp_path)
    monkeypatch.setattr(gates, "of", _raising(OSError("disk full")))
    run_id = gates.request("d1", Gate.LINT, "ana")

    asyncio.run(gates.execute(run_id))

    row = _row(run_id)
    assert row.state == "failed" and row.finished_at is not None
    assert "MI0002" in row.output and "disk full" in row.output


def test_a_cancelled_gate_lands_failed_and_the_cancellation_goes_on(clean, monkeypatch, tmp_path):
    """A worker shutting down cancels the job; the row must not stay `running` behind it."""
    monkeypatch.setattr(gates, "_directory", lambda draft_id: tmp_path)
    monkeypatch.setattr(gates, "of", _raising(asyncio.CancelledError()))
    run_id = gates.request("d1", Gate.STUB, "ana")

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(gates.execute(run_id))

    row = _row(run_id)
    assert row.state == "failed" and "MI0002" in row.output


def test_a_second_gate_on_a_draft_with_one_live_is_refused(clean):
    """Two gates in one directory both write `main.nf` and both stamp `pipeline.yml`."""
    gates.request("d1", Gate.LINT, "ana")
    with pytest.raises(ValueError, match="MI0003"):
        gates.request("d1", Gate.STUB, "ana")
    gates.request("d2", Gate.LINT, "ana")  # another draft is not held up


def test_the_database_holds_one_live_gate_per_draft_against_a_race(clean):
    """The service's check can be raced by two requests; the partial unique index cannot."""
    now = datetime.now(UTC)
    with pytest.raises(IntegrityError), session_scope() as session:
        for run_id in ("r1", "r2"):
            session.add(
                GateRun(
                    id=run_id,
                    draft_id="d1",
                    who="ana",
                    gate="lint",
                    state="queued",
                    output="",
                    queued_at=now,
                )
            )


def test_a_finished_gate_does_not_hold_up_the_next(clean, monkeypatch, tmp_path):
    monkeypatch.setattr(gates, "_directory", lambda draft_id: tmp_path)
    monkeypatch.setattr(gates, "of", _raising(OSError("x")))
    asyncio.run(gates.execute(gates.request("d1", Gate.LINT, "ana")))
    gates.request("d1", Gate.LINT, "ana")


def test_the_sweep_fails_a_gate_past_its_limit_and_leaves_a_recent_one(clean):
    """A gate has a hard limit (`nextflow` is killed at it), so a row still live long past it is
    dead: its worker died, or Redis lost the job. Without the sweep the one-live index would
    hold that draft's gates up for good."""
    old = datetime.now(UTC) - timedelta(seconds=gates.LOST_AFTER + 60)
    with session_scope() as session:
        session.add(
            GateRun(
                id="lost",
                draft_id="d1",
                who="ana",
                gate="test",
                state="running",
                output="",
                queued_at=old,
            )
        )
    recent = gates.request("d2", Gate.STUB, "ana")

    assert gates.sweep() == ["lost"]

    assert _row("lost").state == "failed" and "MI0004" in _row("lost").output
    assert _row(recent).state == "queued"
    gates.request("d1", Gate.LINT, "ana")  # the draft is free again


def test_the_database_refuses_a_state_outside_gate_state(clean):
    """Issue 274. Raw SQL, because SQLAlchemy refuses an unknown value before the database is
    asked; this is the half that holds for any other writer."""
    with pytest.raises(IntegrityError, match="ck_gate_run_state"), session_scope() as session:
        session.execute(
            text(
                "INSERT INTO gate_run (id, draft_id, who, gate, state, output, queued_at) "
                "VALUES ('r1', 'd1', 'ana', 'lint', 'sideways', '', now())"
            )
        )


def test_a_gate_for_a_draft_that_does_not_exist_is_refused(clean):
    """Issue 274: `draft_id` named a draft by convention only, and nine gates in the dev
    database outlived theirs."""
    with pytest.raises(IntegrityError, match="gate_run_draft_id_fkey"), session_scope() as session:
        session.add(
            GateRun(
                id="r1",
                draft_id="nope",
                who="ana",
                gate="lint",
                state="queued",
                output="",
                queued_at=datetime.now(UTC),
            )
        )

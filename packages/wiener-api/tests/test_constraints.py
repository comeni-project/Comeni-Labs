"""What Wiener's database refuses on its own (issue 274).

On SQLite, which enforces CHECK constraints as Postgres does. Raw SQL, because SQLAlchemy
refuses an unknown value in Python first; these are the half that holds for any other writer.
"""

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError


def test_the_database_refuses_a_phase_outside_run_phase(session, a_run):
    with pytest.raises(IntegrityError, match="ck_run_phase"):
        session.execute(text("UPDATE run SET phase = 'sideways' WHERE id = :id"), {"id": a_run.id})


def _event(session, *, run_id: str, lab_id: str) -> None:
    session.execute(text(
        "INSERT INTO run_event (run_id, lab_id, seq, kind, at_ms, payload, received_at) "
        "VALUES (:run, :lab, 0, 'heartbeat', 0, '{}', '2026-01-01')"
    ), {"run": run_id, "lab": lab_id})


def test_an_event_for_a_run_that_does_not_exist_is_refused(session):
    with pytest.raises(IntegrityError, match="FOREIGN KEY"):
        _event(session, run_id="nope", lab_id="local")


# Each key's child row, written for a run that exists in `local` but claiming `another-lab`.
OTHER_LAB = {
    "run_event": "INSERT INTO run_event (run_id, lab_id, seq, kind, at_ms, payload, received_at) "
                 "VALUES (:run, 'another-lab', 0, 'heartbeat', 0, '{}', '2026-01-01')",
    "run_task": "INSERT INTO run_task (run_id, lab_id, task_id, process, status, attempts, "
                "last_change_ms, labels) VALUES (:run, 'another-lab', 1, 'P', 'RUNNING', '[]', 0, "
                "'[]')",
    "run_intent": "INSERT INTO run_intent (id, lab_id, run_id, kind, because, who, at, why, "
                  "prior_phase, outcome) VALUES ('i9', 'another-lab', :run, 'cancel', "
                  "'operator_request', 'op', '2026-01-01', '', 'running', 'signalled')",
    "run_intent.resulting_run_id": "INSERT INTO run_intent (id, lab_id, run_id, kind, because, "
                  "who, at, why, prior_phase, resulting_run_id, outcome) VALUES ('i8', 'local', "
                  ":run, 'relaunch', 'operator_request', 'op', '2026-01-01', '', 'failed', "
                  "'nope', 'signalled')",
    "run.artifact_id": "INSERT INTO run (id, lab_id, artifact_id, submitted_by, submitted_at, "
                       "phase, executor, ingest_secret, last_seq, terminal_seen) VALUES ('r9', "
                       "'another-lab', (SELECT artifact_id FROM run WHERE id = :run), 't', "
                       "'2026-01-01', 'queued', 'local', 's', -1, '[]')",
}


@pytest.mark.parametrize("key", sorted(OTHER_LAB))
def test_a_child_in_another_lab_than_its_parent_is_refused(session, a_run, key):
    """`lab_id` was copied onto every child and nothing made it equal its parent's: the leak
    the models' docstrings name. Each key is `(lab_id, …)`, so the other lab has no such parent
    (issue 274; every key here since issue 297)."""
    with pytest.raises(IntegrityError, match="FOREIGN KEY"):
        session.execute(text(OTHER_LAB[key]), {"run": a_run.id})


def test_an_intent_with_no_resulting_run_is_accepted(session, a_run):
    """A null `resulting_run_id` skips its key (`MATCH SIMPLE`): a cancel results in no run."""
    session.execute(text(
        "INSERT INTO run_intent (id, lab_id, run_id, kind, because, who, at, why, prior_phase, "
        "resulting_run_id, outcome) VALUES ('i1', :lab, :run, 'cancel', 'operator_request', "
        "'op', '2026-01-01', '', 'running', NULL, 'signalled')"
    ), {"lab": a_run.lab_id, "run": a_run.id})

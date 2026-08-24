"""Every query on a tenant-scoped table, and there are no others.

`docs/design/wiener.md` §7.1 names the cost of a tenant column plainly: **a filter you can
forget is a leak**, and it is the class of bug that stays invisible until it is a disclosure.
So the guard is not "remember the filter" — it is that a query lives here or it does not exist,
and every function here takes `lab_id` as its first parameter after the session.
`tests/test_tenancy.py` holds both halves. A177.

**Writes live here too**, though the scan only enforces reads. A row inserted with the wrong
`lab_id` is the same leak arriving a day later, and splitting reads from writes across two
files would mean two answers to *where does the database get touched*.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from wiener_api.models import Run, RunArtifact, RunEventRow, RunTask


def run(session: Session, lab_id: str, run_id: str) -> Run | None:
    return session.scalar(select(Run).where(Run.lab_id == lab_id, Run.id == run_id))


def runs(session: Session, lab_id: str, limit: int = 50) -> list[Run]:
    return list(session.scalars(
        select(Run).where(Run.lab_id == lab_id).order_by(Run.submitted_at.desc()).limit(limit)
    ))


def unfinished(session: Session, lab_id: str) -> list[Run]:
    """Runs that have not reached a terminal phase — what the heartbeat timer walks."""
    return list(session.scalars(
        select(Run).where(Run.lab_id == lab_id,
                          Run.phase.notin_(("succeeded", "failed", "cancelled", "lost")))
    ))


def artifact(session: Session, lab_id: str, artifact_id: str) -> RunArtifact | None:
    return session.scalar(
        select(RunArtifact).where(RunArtifact.lab_id == lab_id, RunArtifact.id == artifact_id)
    )


def events(session: Session, lab_id: str, run_id: str) -> list[RunEventRow]:
    """The record, in order. Everything else about a run is derivable from this."""
    return list(session.scalars(
        select(RunEventRow)
        .where(RunEventRow.lab_id == lab_id, RunEventRow.run_id == run_id)
        .order_by(RunEventRow.seq)
    ))


def next_seq(session: Session, lab_id: str, run_id: str) -> int:
    """The order Wiener received things in, which is the honest claim — §6.2.

    Not the order Nextflow emitted them in, which nothing can promise over a network.
    """
    highest = session.scalar(
        select(RunEventRow.seq)
        .where(RunEventRow.lab_id == lab_id, RunEventRow.run_id == run_id)
        .order_by(RunEventRow.seq.desc())
        .limit(1)
    )
    return 0 if highest is None else highest + 1


def task(session: Session, lab_id: str, run_id: str, task_id: int) -> RunTask | None:
    return session.scalar(
        select(RunTask).where(
            RunTask.lab_id == lab_id, RunTask.run_id == run_id, RunTask.task_id == task_id
        )
    )


def add(session: Session, lab_id: str, row) -> None:
    """Insert, with the laboratory stamped here rather than at the call site."""
    row.lab_id = lab_id
    session.add(row)

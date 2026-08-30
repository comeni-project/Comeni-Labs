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

from datetime import UTC, datetime, timedelta

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from wiener_api.models import Run, RunArtifact, RunEventRow, RunTask


def run(session: Session, lab_id: str, run_id: str) -> Run | None:
    return session.scalar(select(Run).where(Run.lab_id == lab_id, Run.id == run_id))


def runs(session: Session, lab_id: str, limit: int = 50) -> list[Run]:
    return list(session.scalars(
        select(Run).where(Run.lab_id == lab_id).order_by(Run.submitted_at.desc()).limit(limit)
    ))


def runs_page(session: Session, lab_id: str, *, phase: str | None = None,
              who: str | None = None, executor: str | None = None,
              after: int = 0, limit: int = 25) -> tuple[list[Run], int]:
    """One page of the board, filtered — and **the total that matches the same filters**.

    A footer reading `1-7 of 49` while the filter says *failed only* would be counting a
    different question from the one the page answers, so both come from one `where`.
    """
    query = select(Run).where(Run.lab_id == lab_id)
    if phase:
        query = query.where(Run.phase == phase)
    if who:
        query = query.where(Run.submitted_by == who)
    if executor:
        query = query.where(Run.executor == executor)
    total = session.scalar(select(func.count()).select_from(query.subquery())) or 0
    page = list(session.scalars(
        query.order_by(Run.submitted_at.desc(), Run.id).offset(after).limit(min(limit, 200))
    ))
    return page, total


def task_counts(session: Session, lab_id: str, run_ids: list[str]) -> dict[str, tuple[int, int]]:
    """`{run_id: (done, seen)}` for a page of runs, in **one GROUP BY**.

    This is what `run_task` was built for. `Board.tsx` used to say progress could not be shown
    because it would mean folding every run's events on every page load — true before W2, when
    there was no projection to group over. There is one now, it is indexed on `run_id`, and
    this is an aggregate over one page rather than a fold over a history.

    **Tasks, not steps.** `steps_declared` lives in the artifact and reading one per row is the
    expensive thing the old comment was right about; how many tasks a run has SEEN is a column.
    """
    if not run_ids:
        return {}
    done = func.sum(case((RunTask.status.in_(("COMPLETED", "CACHED")), 1), else_=0))
    rows = session.execute(
        select(RunTask.run_id, done, func.count())
        .where(RunTask.lab_id == lab_id, RunTask.run_id.in_(run_ids))
        .group_by(RunTask.run_id)
    ).all()
    return {run_id: (int(finished or 0), int(seen or 0)) for run_id, finished, seen in rows}


def pipeline_digests(session: Session, lab_id: str, artifact_ids: list[str]) -> dict[str, str]:
    """`{artifact_id: pipeline_digest}` for a page of runs, in one query.

    **The join key, fetched the way `task_counts` fetches tallies** — one statement for the
    page rather than one per row. A run knows its artifact; the artifact knows which pipeline it
    is; the browser puts the run beside the pipeline. Neither server learns the other's
    identifiers, which is `wiener.md` §12's whole shape.

    Artifacts uploaded before 2026-08-30 have no digest recorded and are simply absent from the
    map. That is the honest answer — they show under *every run* without a pipeline rather than
    being guessed into somebody else's.
    """
    if not artifact_ids:
        return {}
    rows = session.execute(
        select(RunArtifact.id, RunArtifact.pipeline_digest).where(
            RunArtifact.lab_id == lab_id,
            RunArtifact.id.in_(artifact_ids),
            RunArtifact.pipeline_digest.isnot(None),
        )
    ).all()
    return {artifact_id: digest for artifact_id, digest in rows}


def durations_by_pipeline(session: Session, lab_id: str, *, days: int = 14,
                          floor: int = 3) -> dict[str, int]:
    """`{pipeline_digest: median_ms}` over finished runs — what *vs usual* is measured against.

    **`GROUP BY` the pipeline, which the repository could not do** until `pipeline_digest` was
    written. `rn-board` calls this the board's best number, and the reason is that a median in
    the abstract is trivia while the same median beside a run is a judgement.

    **Folded in Python, deliberately**, following `board_summary`'s stated argument rather than
    reopening it: a median has no portable SQL spelling across SQLite and Postgres, and the
    window is hundreds of runs.

    **A group below `floor` returns no median at all.** *Usually 38m* over two runs is not a
    usual — it is one number wearing the clothes of a distribution, and a page that showed it
    would invite a reader to treat noise as a baseline.
    """
    since = datetime.now(UTC) - timedelta(days=days)
    rows = session.execute(
        select(RunArtifact.pipeline_digest, Run.submitted_at, Run.ended_at)
        .join(RunArtifact, RunArtifact.id == Run.artifact_id)
        .where(
            Run.lab_id == lab_id,
            Run.submitted_at >= since,
            Run.ended_at.isnot(None),
            RunArtifact.pipeline_digest.isnot(None),
        )
    ).all()

    spans: dict[str, list[int]] = {}
    for digest, started, ended in rows:
        spans.setdefault(digest, []).append(int((ended - started).total_seconds() * 1000))

    return {
        digest: sorted(values)[len(values) // 2]
        for digest, values in spans.items()
        if len(values) >= floor
    }


def board_summary(session: Session, lab_id: str, *, days: int = 14) -> dict:
    """What the board's tiles and its fortnight of columns are counting.

    **Durations are folded in Python, deliberately.** A median and a p95 are the two numbers
    that say whether a run is behaving, and neither has a portable SQL spelling across SQLite
    and Postgres. The window is a fortnight of runs — hundreds, not millions — so pulling the
    finished ones back and sorting them is cheaper than a percentile expression that has to be
    written twice and tested on one.
    """
    since = datetime.now(UTC) - timedelta(days=days)
    window = select(Run).where(Run.lab_id == lab_id, Run.submitted_at >= since).subquery()

    by_phase = dict(session.execute(
        select(window.c.phase, func.count()).group_by(window.c.phase)
    ).all())

    # **Only runs that finished have a duration**, and an unfinished one is not a fast one.
    spans = sorted(
        int((ended - started).total_seconds() * 1000)
        for started, ended in session.execute(
            select(window.c.submitted_at, window.c.ended_at).where(window.c.ended_at.isnot(None))
        ).all()
    )

    def at(fraction: float) -> int | None:
        if not spans:
            return None
        return spans[min(len(spans) - 1, int(len(spans) * fraction))]

    # One bucket per day, oldest first, **including the days nothing ran** — a gap the chart
    # skipped would compress a quiet week into a busy-looking one.
    start = (datetime.now(UTC) - timedelta(days=days - 1)).date()
    buckets = {start + timedelta(days=n): {"succeeded": 0, "failed": 0} for n in range(days)}
    for submitted, phase in session.execute(
        select(window.c.submitted_at, window.c.phase)
    ).all():
        day = submitted.date()
        if day in buckets and phase in ("succeeded", "failed"):
            buckets[day][phase] += 1

    return {
        "window_days": days,
        "failed": by_phase.get("failed", 0),
        "running": by_phase.get("running", 0),
        "succeeded": by_phase.get("succeeded", 0),
        "total": sum(by_phase.values()),
        "median_ms": at(0.5),
        "p95_ms": at(0.95),
        "days": [{"day": day.isoformat(), **counts} for day, counts in sorted(buckets.items())],
    }


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


SORTS = {
    "-peak_rss_bytes": RunTask.peak_rss_bytes.desc().nullslast(),
    "peak_rss_bytes": RunTask.peak_rss_bytes.asc().nullsfirst(),
    "-realtime_ms": RunTask.realtime_ms.desc().nullslast(),
    "realtime_ms": RunTask.realtime_ms.asc().nullsfirst(),
    "task_id": RunTask.task_id.asc(),
}
"""A closed vocabulary, and a client-supplied column name is refused rather than interpolated.

**Nulls sort last on a descending sort**: absence is not a small number. A task that reported
no memory is not the task that used the least, and putting it at the bottom of *biggest first*
is the only reading that is not a claim.
"""


def _tasks_query(lab_id: str, run_id: str, process, status, retried_only, attempt=None):
    query = select(RunTask).where(RunTask.lab_id == lab_id, RunTask.run_id == run_id)
    if process:
        query = query.where(RunTask.process == process)
    if status:
        query = query.where(RunTask.status == status)
    if retried_only:
        query = query.where(func.json_array_length(RunTask.attempts) > 1)
    if attempt:
        # **This mirrors `TaskOut`'s `len(row.attempts or []) or 1` in SQL, exactly**, and
        # every piece is load-bearing. A task with no recorded attempt still had one:
        # `attempts` can be SQL NULL, the JSON value `null` (what SQLAlchemy stores for a
        # Python `None` in a JSON column) or `[]`, and `json_array_length` answers NULL, 0
        # and 0 to those three. A bare `= 1` therefore drops exactly the tasks *attempt 1*
        # asks for — silently, because an empty table looks like a filter that matched
        # nothing. `nullif(..., 0)` folds the two zeroes into NULL; the coalesce makes all
        # three 1.
        tries = func.coalesce(func.nullif(func.json_array_length(RunTask.attempts), 0), 1)
        query = query.where(tries >= 3 if attempt >= 3 else tries == attempt)
    return query


def tasks_page(session: Session, lab_id: str, run_id: str, *, process=None, status=None,
               retried_only=False, attempt=None, sort="task_id", after=0,
               limit=100) -> list[RunTask]:
    """One page of a run's tasks — filtered, sorted and paged in SQL.

    **A191.** `attempts` is a JSON blob, so ordering by peak memory across a 5,000-task run
    would mean loading 5,000 documents. The projection writes the three numbers into columns
    as it goes, so this is an `ORDER BY` over an index.

    `RunTask.task_id` is appended to every sort, because a page boundary needs a total order:
    two tasks with the same peak would otherwise be free to swap between page 1 and page 2.
    """
    query = (_tasks_query(lab_id, run_id, process, status, retried_only, attempt)
             .order_by(SORTS.get(sort, SORTS["task_id"]), RunTask.task_id)
             .offset(after).limit(min(limit, 500)))
    return list(session.scalars(query))


def tasks_total(session: Session, lab_id: str, run_id: str, *, process=None, status=None,
                retried_only=False, attempt=None) -> int:
    """How many the same filters match. A table that says *404 more* has to know."""
    query = _tasks_query(lab_id, run_id, process, status, retried_only, attempt)
    return session.scalar(
        select(func.count()).select_from(query.subquery())
    ) or 0


def add(session: Session, lab_id: str, row) -> None:
    """Insert, with the laboratory stamped here rather than at the call site."""
    row.lab_id = lab_id
    session.add(row)

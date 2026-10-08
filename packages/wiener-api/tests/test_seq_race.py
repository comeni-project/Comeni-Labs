"""Two writers appending to one run at once, on real Postgres (issue 282).

SQLite has no row locks, so this cannot run on the suite's database. It runs only when
`WIENER_TEST_DATABASE_URL` names a migrated, throwaway Wiener database — never the configured
one, which may be somebody's — and skips otherwise:

    WIENER_TEST_DATABASE_URL=postgresql+psycopg://…/wiener uv run pytest …/test_seq_race.py
"""

import secrets
import threading
import time
from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from wiener_api.models import Run
from wiener_api.services import projection
from wiener_api.settings import settings
from wiener_core.events import heartbeat
from wiener_postgres import URL, reachable

pytestmark = pytest.mark.skipif(not reachable(), reason="needs WIENER_TEST_DATABASE_URL (Postgres)")


@pytest.fixture
def sessions():
    engine = create_engine(URL)
    maker = sessionmaker(bind=engine, expire_on_commit=False)
    run_id = secrets.token_hex(16)
    with maker() as session:
        session.add(Run(
            id=run_id, lab_id=settings.lab_id, artifact_id=secrets.token_hex(16),
            submitted_by="test", submitted_at=datetime.now(UTC), phase="running",
            executor="local", ingest_secret=secrets.token_hex(16),
        ))
        session.commit()
    yield maker, run_id
    with engine.begin() as connection:
        for table in ("run_event", "run_task", "run"):
            column = "id" if table == "run" else "run_id"
            connection.execute(text(f"DELETE FROM {table} WHERE {column} = :r"), {"r": run_id})
    engine.dispose()


def test_two_writers_take_two_seqs(sessions):
    """`seq` was `max + 1` with no lock: the heartbeat and an ingest overlapping on one run
    took the same number, and the second failed on the primary key. The first writer here
    takes its number and holds its transaction open; the second must wait, then take the next."""
    maker, run_id = sessions
    failures: list[BaseException] = []

    def slow():
        try:
            with maker() as session:
                seq = projection.next_seq(session, settings.lab_id, run_id)
                time.sleep(0.5)
                projection.append(session, settings.lab_id, run_id,
                                  heartbeat(run_id=run_id, at_ms=1_800_000_000_000, seq=seq))
                session.commit()
        except BaseException as failed:  # noqa: BLE001 — the assertion below reports it
            failures.append(failed)

    def quick():
        try:
            with maker() as session:
                projection.beat(session, settings.lab_id, run_id, at_ms=1_800_000_000_001)
                session.commit()
        except BaseException as failed:  # noqa: BLE001
            failures.append(failed)

    first = threading.Thread(target=slow)
    first.start()
    time.sleep(0.1)
    second = threading.Thread(target=quick)
    second.start()
    first.join(10)
    second.join(10)

    assert failures == [], f"a writer failed: {failures!r}"
    with maker() as session:
        seqs = sorted(session.scalars(
            text("SELECT seq FROM run_event WHERE run_id = :r").bindparams(r=run_id)))
    assert seqs == [0, 1]

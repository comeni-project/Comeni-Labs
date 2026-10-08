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

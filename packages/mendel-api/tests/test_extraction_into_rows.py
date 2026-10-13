"""A session begun before Part I.0 carries on from the rows: its stored extraction becomes a
want row and suggestions, and the column goes (Part I.0 spec §6.1, Review Focus 4)."""

import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from secrets import token_hex

import pytest
from mendel_postgres import reachable

pytestmark = pytest.mark.skipif(not reachable(), reason="no database")

BEFORE = "c1d5f9b3e264"
EXTRACTION = """{"want": ["counts.matrix"], "constraints": {},
  "suggested": {"required_states": [{"type_id": "counts.matrix", "states": ["gene_level"]}]},
  "stated": [{"kind": "measurement", "subject": "paired", "value": true},
             {"kind": "input", "subject": "genome.fasta"}]}"""


def test_an_extraction_becomes_rows_and_suggestions_and_the_column_goes():
    from mendel_api import db
    from sqlalchemy import create_engine, inspect, text

    name = "mendel_extraction_test_" + token_hex(6)
    admin = create_engine(db.engine.url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    with admin.connect() as connection:
        connection.execute(text(f'CREATE DATABASE "{name}"'))
    clone_url = db.engine.url.set(database=name)
    clone = create_engine(clone_url)
    package = Path(__file__).resolve().parents[1]
    env = dict(os.environ, MENDEL_DATABASE_URL=clone_url.render_as_string(hide_password=False))

    def upgrade(target):
        done = subprocess.run([sys.executable, "-m", "alembic", "upgrade", target], cwd=package,
                              env=env, capture_output=True, text=True)
        assert done.returncode == 0, done.stderr

    try:
        upgrade(BEFORE)
        now = datetime.now(UTC)
        with clone.begin() as connection:
            connection.execute(text(
                "INSERT INTO pipeline_draft (id, who, name, graph, updated_at) "
                "VALUES ('d1', 'ana', 'old', '{\"nodes\": [], \"edges\": []}', :at)"), {"at": now})
            connection.execute(text(
                "INSERT INTO pipeline_authoring_session (id, draft_id, phase, at, blueprint, "
                "registry_digest, row_version, who, created_at, updated_at, extraction) "
                "VALUES ('s1', 'd1', 'gathering', 'reply', '{}', '', 3, 'ana', :at, :at, "
                "CAST(:extraction AS JSONB))"), {"at": now, "extraction": EXTRACTION})
        upgrade("head")
        with clone.begin() as connection:
            wants = connection.execute(text(
                "SELECT r.type_id, r.present, r.actor_kind, r.heard FROM pipeline_want w "
                "JOIN pipeline_want_revision r ON r.id = w.current_id WHERE w.draft_id = 'd1'"
            )).all()
            assert [tuple(w) for w in wants] == [("counts.matrix", True, "model", None)]
            offered = connection.execute(text(
                "SELECT change->>'kind', change->>'subject', state, heard "
                "FROM pipeline_authoring_suggestion WHERE session_id = 's1' "
                "ORDER BY change->>'subject'")).all()
            assert [tuple(o) for o in offered] == [
                ("require", "counts.matrix", "pending", False),
                ("input", "genome.fasta", "pending", False),
                ("measurement", "paired", "pending", False),
            ]
            phase = connection.execute(text(
                "SELECT phase, at, row_version FROM pipeline_authoring_session")).one()
            assert tuple(phase) == ("gathering", "reply", 3)
            confirmed = connection.execute(text(
                "SELECT confirmed_revision FROM pipeline_draft WHERE id = 'd1'")).scalar_one()
            assert confirmed is None
        columns = {c["name"] for c in inspect(clone).get_columns("pipeline_authoring_session")}
        assert "extraction" not in columns
    finally:
        clone.dispose()
        with admin.connect() as connection:
            connection.execute(text(f'DROP DATABASE "{name}" WITH (FORCE)'))
        admin.dispose()

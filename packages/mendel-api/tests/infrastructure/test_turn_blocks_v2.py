"""A turn stored at shape 1 is at shape 2 after `make migrate`, unchanged, and reads (#341; Part H
spec §3.3, §3.5's *an upgrade migration over a seeded old-shape row*)."""

import os
import subprocess
import sys
from datetime import UTC, datetime

import pytest
from mendel_api_tests.database import migration_database as migration_database
from mendel_api_tests.database import reachable
from support.paths import ROOT as REPOSITORY_ROOT

pytestmark = pytest.mark.skipif(not reachable(), reason="no database")

BEFORE = "d3b7f1a9c582"
AFTER = "a9d4e2c7b318"  # this migration, not `head`: later shapes move the stamp on
BLOCKS = """[{"kind": "text", "text": "5 steps; 1 needs you."},
  {"kind": "need", "subject": "strandedness", "need": "fact"}]"""


def test_a_shape_one_turn_is_stamped_two_and_left_as_it_was(migration_database):
    from sqlalchemy import create_engine, text

    clone_url = migration_database
    clone = create_engine(clone_url)
    package = REPOSITORY_ROOT / "packages" / "mendel-api"
    env = dict(os.environ, MENDEL_DATABASE_URL=clone_url.render_as_string(hide_password=False))

    def migrate(verb, target):
        done = subprocess.run([sys.executable, "-m", "alembic", verb, target], cwd=package,
                              env=env, capture_output=True, text=True)
        assert done.returncode == 0, done.stderr

    try:
        migrate("upgrade", BEFORE)
        now = datetime.now(UTC)
        with clone.begin() as connection:
            connection.execute(text(
                "INSERT INTO pipeline_draft (id, who, name, graph, updated_at) "
                "VALUES ('d1', 'ana', 'old', '{\"nodes\": [], \"edges\": []}', :at)"), {"at": now})
            connection.execute(text(
                "INSERT INTO pipeline_authoring_session (id, draft_id, phase, blueprint, "
                "registry_digest, row_version, who, created_at, updated_at) "
                "VALUES ('s1', 'd1', 'building', '{}', '', 1, 'ana', :at, :at)"), {"at": now})
            connection.execute(text(
                "INSERT INTO pipeline_authoring_turn (session_id, seq, role, state, blocks, "
                "text, base_revision, at) VALUES ('s1', 1, 'assistant', 'answered', "
                "CAST(:blocks AS JSONB), '', 0, :at)"), {"at": now, "blocks": BLOCKS})
        before = _row(clone)
        assert before[1] == 1

        migrate("upgrade", AFTER)
        after = _row(clone)
        assert after == (before[0], 2)

        migrate("downgrade", BEFORE)
        assert _row(clone) == (before[0], 1)
    finally:
        clone.dispose()


def _row(clone):
    from sqlalchemy import text

    with clone.connect() as connection:
        return tuple(connection.execute(
            text("SELECT blocks, shape_version FROM pipeline_authoring_turn")).one())

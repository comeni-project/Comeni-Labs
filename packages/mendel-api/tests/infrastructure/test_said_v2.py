"""A value the person stated is `said`, no longer `goal` (Part I.0 Plan B). Rows stored before
say `goal` inside their JSON; `make migrate` rewrites them and moves each table one shape on."""

import json
import os
import subprocess
import sys
from datetime import UTC, datetime

import pytest
from mendel_api_tests.database import migration_database as migration_database
from mendel_api_tests.database import reachable
from support.paths import ROOT as REPOSITORY_ROOT

pytestmark = pytest.mark.skipif(not reachable(), reason="no database")

BEFORE = "a9d4e2c7b318"
# A measurement the person stated, beside a premise whose `origin` is the other enum's `goal`.
STATED = {"measurement": "paired", "value": True, "source": "goal",
          "premise": {"origin": "goal"}}
SAID = {**STATED, "source": "said"}


def test_a_stated_source_is_said_after_migration_and_goal_after_downgrade(migration_database):
    from sqlalchemy import create_engine, text

    clone_url = migration_database
    clone = create_engine(clone_url)
    package = REPOSITORY_ROOT / "packages" / "mendel-api"
    env = dict(os.environ, MENDEL_DATABASE_URL=clone_url.render_as_string(hide_password=False))

    def migrate(verb, target):
        done = subprocess.run([sys.executable, "-m", "alembic", verb, target], cwd=package,
                              env=env, capture_output=True, text=True)
        assert done.returncode == 0, done.stderr

    nested = json.dumps({"profile": {"measurements": [STATED]}})
    try:
        migrate("upgrade", BEFORE)
        now = datetime.now(UTC)
        with clone.begin() as connection:
            connection.execute(text(
                "INSERT INTO pipeline_draft (id, who, name, graph, provenance, updated_at) "
                "VALUES ('d1', 'ana', 'old', CAST(:json AS JSONB), CAST(:json AS JSONB), :at)"),
                {"at": now, "json": nested})
            connection.execute(text(
                "INSERT INTO pipeline_authoring_session (id, draft_id, phase, blueprint, "
                "registry_digest, row_version, who, created_at, updated_at) "
                "VALUES ('s1', 'd1', 'building', CAST(:json AS JSONB), '', 1, 'ana', :at, :at)"),
                {"at": now, "json": nested})
            connection.execute(text(
                "INSERT INTO pipeline_authoring_proposal (id, session_id, kind, payload, state, "
                "draft_revision, created_at, preview_views) VALUES ('p1', 's1', 'goal', "
                "CAST(:json AS JSONB), 'pending', 0, :at, CAST(:json AS JSONB))"),
                {"at": now, "json": nested})
            connection.execute(text(
                "INSERT INTO pipeline_authoring_turn (session_id, seq, role, state, blocks, "
                "text, base_revision, at) VALUES ('s1', 1, 'assistant', 'answered', "
                "CAST(:json AS JSONB), '', 0, :at)"), {"at": now, "json": nested})
        assert _rows(clone) == [(STATED, 1)] * 5 + [(STATED, 2)]

        migrate("upgrade", "head")
        assert _rows(clone) == [(SAID, 2)] * 5 + [(SAID, 3)]

        migrate("downgrade", BEFORE)
        assert _rows(clone) == [(STATED, 1)] * 5 + [(STATED, 2)]
    finally:
        clone.dispose()


def _rows(clone):
    """Each rewritten column's stated measurement, with its table's stamp."""
    from sqlalchemy import text

    found = []
    with clone.connect() as connection:
        for table, column in (("pipeline_draft", "graph"),
                              ("pipeline_draft", "provenance"),
                              ("pipeline_authoring_session", "blueprint"),
                              ("pipeline_authoring_proposal", "payload"),
                              ("pipeline_authoring_proposal", "preview_views"),
                              ("pipeline_authoring_turn", "blocks")):
            value, stamp = connection.execute(
                text(f"SELECT {column}, shape_version FROM {table}")).one()
            found.append((value["profile"]["measurements"][0], stamp))
    return found

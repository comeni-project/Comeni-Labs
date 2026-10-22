"""A proposal's previews stored at shape 1 are at shape 2 after `make migrate`: each setting a
preview draws says whether it is optional, from its route (#384; Part H spec §3.3)."""

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

BEFORE = "89d3b4e5ab6f"
AFTER = "b7c3e9a1d204"  # this migration, not `head`: later shapes move the stamp on
SETTING = {"value": None, "tier": 4, "reason": "", "because": "", "axis_reason": "", "premise": []}
PREVIEWS = {"alt_1": {"option_id": "alt_1", "frame": {"steps": [{"id": "align", "settings": [
    {**SETTING, "name": "seq_platform", "via": "ext"},
    {**SETTING, "name": "star_ignore_sjdbgtf", "via": "positional"},
]}]}}}


def test_a_shape_one_preview_says_which_settings_are_optional(migration_database):
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
                "INSERT INTO pipeline_authoring_proposal (id, session_id, kind, payload, "
                "preview_views, state, draft_revision, created_at) VALUES ('p1', 's1', 'step', "
                "'{}', CAST(:previews AS JSONB), 'pending', 1, :at)"),
                {"at": now, "previews": json.dumps(PREVIEWS)})
        assert _row(clone)[1] == 1

        migrate("upgrade", AFTER)
        previews, stamp = _row(clone)
        settings = previews["alt_1"]["frame"]["steps"][0]["settings"]
        assert settings, "the seeded preview lost its settings"
        assert {s["name"]: s["optional"] for s in settings} == {
            "seq_platform": True, "star_ignore_sjdbgtf": False}
        assert stamp == 2

        migrate("downgrade", BEFORE)
        assert _row(clone) == (PREVIEWS, 1)
    finally:
        clone.dispose()


def _row(clone):
    from sqlalchemy import text

    with clone.connect() as connection:
        return tuple(connection.execute(
            text("SELECT preview_views, shape_version FROM pipeline_authoring_proposal")).one())

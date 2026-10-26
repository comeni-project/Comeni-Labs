"""The old forge is gone: package, routes, tables and every name (forge MVP part 0, #361).

The new forge is written from scratch (`docs/superpowers/specs/2026-10-19-forge-mvp-design.md`).
These hold that nothing of the old one is left to be confused with it.
"""

import importlib.util
import os
import subprocess
import sys

import pytest
from mendel_api_tests.database import migration_database as migration_database
from mendel_api_tests.database import reachable
from support.paths import ROOT as REPOSITORY_ROOT

OLD_TABLES = {
    "forge_message", "forge_event", "forge_revision", "forge_adaptation",
    "forge_catalogue_item", "forge_source_snapshot", "source_check", "queue_visit",
}
BEFORE = "a9d4e2c7b318"
AFTER = "89d3b4e5ab6f"  # the old forge's removal, not `head`: later migrations add tables


def test_the_package_is_gone():
    assert importlib.util.find_spec("mendel_forge") is None


def test_the_old_routes_are_gone_and_the_builder_s_remain():
    from mendel_api.main import create_app

    paths = list(create_app().openapi()["paths"])
    assert paths, "the app has no routes at all"
    gone = ("/api/forge", "/api/contracts", "/api/questions", "/api/sources", "/api/tools")
    assert [p for p in paths if p.startswith(gone)] == []
    assert "/api/attention" in paths
    assert any(p.startswith("/api/pipeline/authoring") for p in paths)


def test_the_models_declare_none_of_the_old_tables():
    from mendel_api.models import Base

    tables = set(Base.metadata.tables)
    assert "ai_invocation" in tables
    assert tables & OLD_TABLES == set()


def test_no_code_or_configuration_names_the_old_forge():
    skip = ("docs/notes/", "docs/superpowers/", ".git/", "node_modules/", "/migrations/versions/",
            ".venv/", "__pycache__/", "test_old_forge_gone.py", ".superpowers/")
    found = []
    for path in REPOSITORY_ROOT.rglob("*"):
        rel = path.relative_to(REPOSITORY_ROOT).as_posix()
        if not path.is_file() or any(s in "/" + rel for s in skip) or rel.startswith(tuple(skip)):
            continue
        scanned = {".py", ".toml", ".yml", ".yaml", ".ts", ".tsx"}
        if path.suffix not in scanned and path.name != "Makefile":
            continue
        text = path.read_text(errors="ignore")
        if "mendel_forge" in text or "mendel-forge" in text:
            found.append(rel)
    assert found == []


@pytest.mark.skipif(not reachable(), reason="no database")
def test_the_migration_drops_only_the_old_forge_tables(migration_database):
    from sqlalchemy import create_engine, inspect, text

    url = migration_database
    package = REPOSITORY_ROOT / "packages" / "mendel-api"
    env = dict(os.environ, MENDEL_DATABASE_URL=url.render_as_string(hide_password=False))

    def migrate(target):
        done = subprocess.run([sys.executable, "-m", "alembic", "upgrade", target], cwd=package,
                              env=env, capture_output=True, text=True)
        assert done.returncode == 0, done.stderr

    engine = create_engine(url)
    try:
        migrate(BEFORE)
        before = set(inspect(engine).get_table_names())
        assert before >= OLD_TABLES, "the old tables were not there to drop"
        with engine.begin() as db:
            db.execute(text(
                "INSERT INTO ai_invocation (id, agent, purpose, model, provider, prompt_id, "
                "prompt_version, prompt_digest, input_digests, state, failure_code, started_at) "
                "VALUES ('old-forge-call', 'forge', 'analysis', 'm', '', 'p', '', 'd', '{}', "
                "'succeeded', '', now())"))
        migrate(AFTER)
        after = set(inspect(engine).get_table_names())
        assert after == before - OLD_TABLES
        with engine.connect() as db:
            kept = db.execute(text("SELECT agent FROM ai_invocation WHERE id = 'old-forge-call'"))
            assert kept.scalar_one() == "forge"
    finally:
        engine.dispose()

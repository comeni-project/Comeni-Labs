"""Wiener's migrations and models describe the same database (issue 279).

Wiener had no migration test. Its behaviour tests build the schema with `create_all` on
SQLite, so a column a migration forgot was invisible to every one of them. These run against
the throwaway Postgres `make test-db` brings to head (CI has one too).
"""

import os
import subprocess
import sys
from pathlib import Path

import pytest
from wiener_api import models  # noqa: F401 — fills Base.metadata
from wiener_api.db import Base
from wiener_postgres import URL, reachable

PACKAGE = Path(__file__).resolve().parents[1]

needs_db = pytest.mark.skipif(
    not reachable(), reason="needs WIENER_TEST_DATABASE_URL (`make test-db`)"
)


def _alembic(*args: str) -> subprocess.CompletedProcess:
    env = {**os.environ, "WIENER_DATABASE_URL": URL or ""}
    return subprocess.run([sys.executable, "-m", "alembic", *args], cwd=PACKAGE, env=env,
                          capture_output=True, text=True, check=False)


def test_the_scan_reached_the_models():
    """A loop over an empty metadata passes while checking nothing (`tests/README.md`)."""
    assert len(Base.metadata.tables) >= 5, "the models were not imported; nothing below runs"


def test_the_chain_has_one_head():
    done = _alembic("heads")
    assert done.returncode == 0, done.stderr
    heads = [line for line in done.stdout.splitlines() if line.strip()]
    assert len(heads) == 1, f"the migration chain has forked: {heads}"


@needs_db
def test_the_models_match_the_migrated_database():
    current = _alembic("current")
    assert "(head)" in current.stdout, (
        "the test database is not at head, so a difference would be a phantom: `make test-db`"
    )
    done = _alembic("check")
    found = "\n".join(line for line in done.stderr.splitlines() if "Detected" in line)
    assert done.returncode == 0, f"the models and the migrations disagree:\n{found}"

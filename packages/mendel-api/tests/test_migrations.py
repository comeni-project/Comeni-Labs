"""The migrations and the models describe the same database.

**This is the check CI can actually run.** Every other claim about the schema needs Postgres and
is skipped on a pull request, which is the worst possible place for the failure mode this file
covers: a column added to `models.py` and forgotten in the migration is invisible to every unit
test — SQLAlchemy is happy, the model imports, and the first symptom is `UndefinedColumn` on a
deployed instance.

Alembic's **offline mode** is what makes it possible. `alembic upgrade head --sql` renders the
whole chain as PostgreSQL DDL with no server anywhere, so the comparison is against the real
dialect rather than against a SQLite approximation that silently drops a partial index.
"""

import re
import subprocess
import sys
from pathlib import Path

import pytest

# `models` is imported for its side effect: `Base.metadata` is empty until that module has been
# executed, and every "for each table" assertion below then passes over an empty collection. That
# is not hypothetical — this file's first run had the import missing, and only
# `test_every_migrated_table_is_still_a_model`, the direction that reads the DDL rather than the
# metadata, noticed. `test_the_scan_reached_the_models` is the standing version of that accident.
from mendel_api import models  # noqa: F401
from mendel_api.db import Base

PACKAGE = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def ddl() -> str:
    """The whole migration chain, rendered as PostgreSQL, without a database.

    `check=True` rather than reading a return code: a broken chain — a missing `down_revision`,
    two heads — makes alembic exit non-zero, and a test that parsed the empty output would
    report every table missing rather than the one sentence alembic printed.
    """
    done = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head", "--sql"],
        cwd=PACKAGE,
        capture_output=True,
        text=True,
        check=False,
    )
    assert done.returncode == 0, f"alembic refused:\n{done.stderr}"
    return done.stdout


def _created(ddl: str, table: str) -> str:
    """The body of one `CREATE TABLE`, or `""` when the migrations never create it."""
    found = re.search(rf"CREATE TABLE {table} \((.*?)\n\);", ddl, re.DOTALL)
    return found.group(1) if found else ""


def test_the_scan_reached_the_models():
    """`tests/README.md`: a loop is not an assertion. Every comparison below iterates
    `Base.metadata.tables`, and an empty mapping makes all of them pass while checking nothing.

    This is not a defensive flourish — it is what actually happened on this file's first run,
    and only the one test that reads the DDL instead of the metadata noticed.
    """
    assert len(Base.metadata.tables) >= 11, "the models were not imported; nothing below runs"


def test_the_chain_has_one_head():
    """Two heads is what happens when two branches each add a migration off the same parent.

    It is not caught by anything else here — both migrations render, both tables appear — and
    the symptom is `make migrate` refusing on somebody else's machine after a merge.
    """
    done = subprocess.run(
        [sys.executable, "-m", "alembic", "heads"],
        cwd=PACKAGE,
        capture_output=True,
        text=True,
        check=False,
    )
    assert done.returncode == 0, done.stderr
    heads = [line for line in done.stdout.splitlines() if line.strip()]
    assert len(heads) == 1, f"the migration chain has forked: {heads}"


def test_every_model_table_is_created_by_a_migration(ddl):
    missing = [name for name in sorted(Base.metadata.tables) if not _created(ddl, name)]
    assert missing == [], (
        f"these tables exist in models.py and in no migration: {missing}. "
        "`make migrate` would leave a deployed instance without them, and nothing else here "
        "would notice — a model imports fine against a table that does not exist."
    )


def test_every_model_column_is_created_by_a_migration(ddl):
    """The cheaper mistake, and the one this file is really for.

    A whole missing table is loud on the first request. A missing *column* is loud only on the
    first request that touches it, which for something like `failed_stage` is the first failure
    in production — the path nobody exercises while writing the feature.
    """
    missing = []
    for name, table in sorted(Base.metadata.tables.items()):
        body = _created(ddl, name)
        for column in table.columns:
            if not re.search(rf"^\s*{re.escape(column.name)}\s", body, re.MULTILINE):
                missing.append(f"{name}.{column.name}")
    assert missing == [], f"these columns exist in models.py and in no migration: {missing}"


def test_every_migrated_table_is_still_a_model(ddl):
    """The other direction: a table the migrations create and nothing declares.

    Not a correctness bug — it costs a table nobody reads — but it is how a rename lands as an
    addition, leaving the old table and its rows sitting in every database while the code reads
    a new one. `alembic_version` is alembic's own bookkeeping and is not a model.
    """
    created = set(re.findall(r"CREATE TABLE (\w+) \(", ddl)) - {"alembic_version"}
    orphaned = sorted(created - set(Base.metadata.tables))
    assert orphaned == [], (
        f"the migrations create {orphaned} and models.py declares no such table. If this is a "
        "rename, the old table is still there in every existing database."
    )


def test_the_partial_unique_index_survives_into_the_ddl(ddl):
    """`models.py` claims a partial unique index is what makes one-active-adaptation safe
    against two simultaneous requests. That claim is only true if the index reaches the
    database, and `postgresql_where` is exactly the kind of dialect-specific option that gets
    dropped by a round trip through autogenerate or a SQLite-based test.

    So this asserts the rendered SQL, not the model.
    """
    found = re.search(
        r"CREATE UNIQUE INDEX ix_forge_adaptation_one_active ON forge_adaptation "
        r"\(catalogue_item_id\) WHERE (.+);",
        ddl,
    )
    assert found is not None, "the one-active index is not partial, or is not unique, in the DDL"
    assert "published" in found.group(1) and "archived" in found.group(1)


def test_no_foreign_key_cascades(ddl):
    """`models.py` says archiving an adaptation never deletes revisions, events, messages or
    invocation audit — and that the way the rule stays true is that there is no cascade to
    break it with. This is that sentence rendered as SQL and read back.

    A single `ON DELETE CASCADE` added later for convenience would take an approved contract's
    provenance with the catalogue item it came from, silently, on one `DELETE`.
    """
    cascades = re.findall(r"FOREIGN KEY\((\w+)\)[^,\n]*ON DELETE CASCADE", ddl)
    assert cascades == [], f"these foreign keys cascade: {cascades}"

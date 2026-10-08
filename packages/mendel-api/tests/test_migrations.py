"""The migrations and the models describe the same database.

**The whole schema is compared by `alembic check`** against the throwaway Postgres
(`make test-db`; CI has one): tables, columns, types, nullability, indexes, unique and foreign
keys, and check constraints by name. Until issue 279 this file compared only tables and
columns, by regex over offline DDL, and two indexes the models did not declare went unseen.

**The offline DDL stays for what is about specific SQL.** `alembic upgrade head --sql` renders
the whole chain as PostgreSQL with no server, so the partial indexes, the absence of cascades
and the data migrations are asserted on the statements themselves.
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
from mendel_api.db import Base, session_scope
from mendel_postgres import reachable
from sqlalchemy import text
from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateTable

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


def _added(ddl: str, table: str) -> set[str]:
    """Columns the chain adds to a table *after* creating it.

    **The first `ALTER TABLE` in this schema is what found the gap.** Every migration until
    2026-09-05 created a fresh table, so reading only `CREATE TABLE` bodies was correct by
    accident — and the accident held for five migrations. A column added by a later migration
    read as a column no migration creates, which is the guard reporting the opposite of the
    truth: it would have sent somebody to write a migration that already existed.
    """
    return set(re.findall(rf"ALTER TABLE {table} ADD COLUMN (\w+)", ddl))


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


def test_the_one_live_gate_index_survives_into_the_ddl(ddl):
    """Issue 278: one live gate per draft holds only if the partial index reaches the database."""
    found = re.search(
        r"CREATE UNIQUE INDEX ix_gate_run_one_live ON gate_run \(draft_id\) WHERE (.+);", ddl
    )
    assert found is not None, "the one-live index is not partial, or is not unique, in the DDL"
    assert "queued" in found.group(1) and "running" in found.group(1)


def test_no_foreign_key_cascades(ddl):
    """`models.py` says archiving an adaptation never deletes revisions, events, messages or
    invocation audit — and that the way the rule stays true is that there is no cascade to
    break it with. This is that sentence rendered as SQL and read back.

    A single `ON DELETE CASCADE` added later for convenience would take an approved contract's
    provenance with the catalogue item it came from, silently, on one `DELETE`.
    """
    cascades = re.findall(r"FOREIGN KEY\((\w+)\)[^,\n]*ON DELETE CASCADE", ddl)
    assert cascades == [], f"these foreign keys cascade: {cascades}"


def test_stored_blueprints_lose_their_mode(ddl):
    """14.7.8.2: `Blueprint` has no `mode`, so a stored one holding it would fail to load."""
    assert "blueprint::jsonb - 'mode'" in ddl


def test_the_session_row_loses_mode_and_gains_pacing(ddl):
    assert "ALTER TABLE pipeline_authoring_session DROP COLUMN mode" in ddl
    assert "pacing" in _added(ddl, "pipeline_authoring_session")


def test_the_walks_place_is_the_steps_reviewed_and_one_policy(ddl):
    """14.7.8.3c (spec §14.6): the cursor and the pacing column give way to `reviewed` and one
    stored `policy` (pacing and whether gaps stop the walk)."""
    added = _added(ddl, "pipeline_authoring_session")
    assert "reviewed" in added and "policy" in added
    assert "ALTER TABLE pipeline_authoring_session DROP COLUMN cursor" in ddl
    assert "ALTER TABLE pipeline_authoring_session DROP COLUMN pacing" in ddl


needs_db = pytest.mark.skipif(not reachable(), reason="needs the test database (`make test-db`)")


def _alembic(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, "-m", "alembic", *args], cwd=PACKAGE,
                          capture_output=True, text=True, check=False)


def _found(done: subprocess.CompletedProcess) -> str:
    """What alembic detected, without its bookkeeping lines (plugins, SERIAL sequences)."""
    return "\n".join(line for line in done.stderr.splitlines()
                     if "Detected" in line and "sequence named" not in line)


@needs_db
def test_the_models_match_the_migrated_database():
    """Issue 279: the models and the migrations had drifted (two indexes the models did not
    declare), and nothing here compared indexes or nullability. `alembic check` compares
    tables, columns, types, nullability, indexes, unique and foreign keys, and checks by name,
    against the real dialect."""
    current = _alembic("current")
    assert "(head)" in current.stdout, (
        "the test database is not at head, so a difference would be a phantom: `make test-db`"
    )
    done = _alembic("check")
    assert done.returncode == 0, f"the models and the migrations disagree:\n{_found(done)}"


def _values(expression: str) -> set[str]:
    return set(re.findall(r"'([^']*)'", expression))


def _model_checks() -> dict[str, set[str]]:
    """Each CHECK the models declare, by name, as the quoted values it names."""
    found = {}
    for table in Base.metadata.sorted_tables:
        ddl = str(CreateTable(table).compile(dialect=postgresql.dialect()))
        for name, expression in re.findall(r"CONSTRAINT (\w+) CHECK \((.*)\)", ddl):
            found[name] = _values(expression)
    return found


@needs_db
def test_each_check_names_exactly_its_enum():
    """`alembic check` compares check constraints by name only. An enum that gains a member
    keeps the name and changes the values, so this compares what is inside (issue 274)."""
    with session_scope() as session:
        rows = session.execute(text(
            "SELECT conname, pg_get_constraintdef(oid) FROM pg_constraint "
            "WHERE contype = 'c' AND connamespace = 'public'::regnamespace"
        )).all()
    database = {name: _values(definition) for name, definition in rows}
    model = _model_checks()
    assert model, "the models declare no check constraint; nothing below compares anything"
    assert model == database

"""Whether the database answers, for the tests that need Postgres.

One helper instead of a copy per file. Without `COMENI_REQUIRE_DB` an unreachable database
skips those tests, as a laptop with no database expects; with it (CI sets it) the same answer
is a failure, so a run cannot go green by skipping storage (issue 279).
"""

import os

import pytest
from mendel_api.db import session_scope
from sqlalchemy import text

REQUIRED = "COMENI_REQUIRE_DB"


def _select_one() -> None:
    with session_scope() as session:
        session.execute(text("SELECT 1"))


def reachable(probe=_select_one) -> bool:
    try:
        probe()
    except Exception as failed:
        if os.environ.get(REQUIRED):
            raise RuntimeError(
                f"{REQUIRED} is set and the database did not answer: {failed!r}. "
                "Locally: `make test-db`."
            ) from failed
        return False
    return True


def truncate(statement: str):
    """Truncate test-owned draft decisions together with their parent, never by cascade.

    Read live table names so populated-baseline migration tests work before the additive
    schema exists. This helper is only in test support; production never truncates drafts.
    """
    from mendel_api.db import engine
    from sqlalchemy import inspect

    prefix = "TRUNCATE TABLE "
    if not statement.startswith(prefix):
        raise ValueError("expected a test truncation statement")
    tables = {name.strip() for name in statement[len(prefix) :].split(",")}
    if "pipeline_draft" in tables:
        tables.update(
            name
            for name in inspect(engine).get_table_names()
            if name.startswith("pipeline_") and not name.startswith("pipeline_authoring_")
        )
    live = set(inspect(engine).get_table_names())
    if "pipeline_authoring_session" in tables and "pipeline_authoring_suggestion" in live:
        # A session's suggestions go with it (Part I.0): they reference it, `RESTRICT`.
        tables.add("pipeline_authoring_suggestion")
    return text(prefix + ", ".join(sorted(tables)))


@pytest.fixture
def migration_database():
    """Create a disposable database owned by the app role, using test-only administration.

    Set MENDEL_TEST_ADMIN_DATABASE_URL when the application role cannot create databases.
    Legacy test servers may use the same administrative role for both connections.
    """
    from secrets import token_hex

    from mendel_api.db import engine
    from sqlalchemy import create_engine
    from sqlalchemy.engine import make_url

    admin_url = (
        make_url(os.environ["MENDEL_TEST_ADMIN_DATABASE_URL"])
        if os.environ.get("MENDEL_TEST_ADMIN_DATABASE_URL")
        else engine.url.set(database="postgres")
    )
    if (admin_url.host, admin_url.port) != (engine.url.host, engine.url.port):
        raise ValueError("Migration test administration must use the same isolated database server")
    admin = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    name = "mendel_migration_test_" + token_hex(6)
    quote = admin.dialect.identifier_preparer.quote_identifier
    created = False
    try:
        with admin.connect() as connection:
            connection.execute(
                text(f"CREATE DATABASE {quote(name)} OWNER {quote(engine.url.username)}")
            )
            created = True
            connection.execute(text(f"REVOKE ALL ON DATABASE {quote(name)} FROM PUBLIC"))
        yield engine.url.set(database=name)
    finally:
        try:
            if created:
                with admin.connect() as connection:
                    connection.execute(text(f"DROP DATABASE {quote(name)} WITH (FORCE)"))
        finally:
            admin.dispose()

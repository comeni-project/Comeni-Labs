"""Wiener's opt-in Postgres, for the tests SQLite cannot hold (row locks, the migrations).

`WIENER_TEST_DATABASE_URL` names a migrated, throwaway Wiener database — never the configured
one, which may be somebody's. Unset, these tests skip; unset or unreachable while
`COMENI_REQUIRE_DB` is set (CI), they fail (issue 279).
"""

import os

from sqlalchemy import create_engine, text

REQUIRED = "COMENI_REQUIRE_DB"
URL = os.environ.get("WIENER_TEST_DATABASE_URL")


def reachable() -> bool:
    try:
        if URL is None:
            raise LookupError("WIENER_TEST_DATABASE_URL is not set")
        engine = create_engine(URL)
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        engine.dispose()
    except Exception as failed:
        if os.environ.get(REQUIRED):
            raise RuntimeError(
                f"{REQUIRED} is set and Wiener's test database did not answer: {failed!r}. "
                "Locally: `make test-db`."
            ) from failed
        return False
    return True

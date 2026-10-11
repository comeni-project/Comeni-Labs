"""Whether the database answers, for the tests that need Postgres.

One helper instead of a copy per file. Without `COMENI_REQUIRE_DB` an unreachable database
skips those tests, as a laptop with no database expects; with it (CI sets it) the same answer
is a failure, so a run cannot go green by skipping storage (issue 279).
"""

import os

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
    tables = {name.strip() for name in statement[len(prefix):].split(",")}
    if "pipeline_draft" in tables:
        tables.update(
            name for name in inspect(engine).get_table_names()
            if name.startswith("pipeline_") and not name.startswith("pipeline_authoring_")
        )
    return text(prefix + ", ".join(sorted(tables)))

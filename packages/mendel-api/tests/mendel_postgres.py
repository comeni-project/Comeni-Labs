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

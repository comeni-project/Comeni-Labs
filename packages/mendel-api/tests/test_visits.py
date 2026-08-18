"""When a curator last looked at the queue.

The maintenance view asks "what moved since I was here", and that needs a "here". Stored
rather than kept in the browser — the operator's decision on 2026-08-18 — so it survives a
browser change and is the shape accounts will need.

**These are the first API tests that need Postgres**, and CI does not have it. They skip when
it is unreachable, the same way `test_gates.py` skips without Nextflow. The *decision* they
support — what "since my last visit" hides — is tested without a database in
`test_queue_service.py`, where `visits.last` is monkeypatched; what is here is the storage.
"""

from datetime import UTC, datetime

import pytest
from mendel_api.db import session_scope
from mendel_api.services import visits
from sqlalchemy import text


def _database_is_reachable() -> bool:
    try:
        with session_scope() as session:
            session.execute(text("SELECT 1"))
    except Exception:
        return False
    return True


pytestmark = pytest.mark.skipif(
    not _database_is_reachable(), reason="no database — run `docker compose up -d postgres`"
)


def test_nobody_has_visited_yet(clean_db):
    assert visits.last("rafael") is None


def test_marking_a_visit_makes_it_the_last_one(clean_db):
    before = datetime.now(UTC)
    stamped = visits.mark("rafael")
    assert stamped >= before
    assert visits.last("rafael") == stamped


def test_the_latest_visit_wins_rather_than_the_first(clean_db):
    visits.mark("rafael")
    second = visits.mark("rafael")
    assert visits.last("rafael") == second


def test_two_curators_do_not_share_a_baseline(clean_db):
    """Attribution is per name. It is weak — `default_author()` reads git config, so a
    shared install gives everyone the same name — but it must not be wrong on top of weak."""
    mine = visits.mark("rafael")
    visits.mark("someone-else")
    assert visits.last("rafael") == mine


def test_an_absent_name_falls_back_rather_than_writing_a_blank(clean_db, monkeypatch):
    monkeypatch.setattr("mendel_api.services.visits.default_author", lambda: "rafael")
    visits.mark(None)
    assert visits.last("rafael") is not None

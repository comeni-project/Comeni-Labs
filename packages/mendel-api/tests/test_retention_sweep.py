"""The sweep clears exactly what is past its limit, and records every pass (Part H spec §5.2)."""

from datetime import UTC, datetime, timedelta

import pytest
import sqlalchemy as sa
from mendel_api.db import session_scope
from mendel_api.models import AiInvocation, PipelineDraft, RetentionSweep
from mendel_api.services import retention
from mendel_postgres import reachable

pytestmark = pytest.mark.skipif(not reachable(), reason="no database")
NOW = datetime(2026, 10, 12, 4, 0, tzinfo=UTC)


def _call(id: str, age_days: float, agent="builder", purpose="ask"):
    with session_scope() as db:
        db.add(AiInvocation(id=id, agent=agent, purpose=purpose, model="m", prompt_id="p",
                            prompt_digest="d", state="succeeded", response="said",
                            started_at=NOW - timedelta(days=age_days)))


@pytest.fixture
def swept():
    with session_scope() as db:
        db.execute(sa.text("DELETE FROM retention_sweep"))
        db.execute(sa.text("DELETE FROM ai_invocation WHERE id LIKE 'ret-%'"))
    yield
    with session_scope() as db:
        db.execute(sa.text("DELETE FROM ai_invocation WHERE id LIKE 'ret-%'"))


def test_a_reply_past_thirty_days_is_cleared_and_a_younger_one_kept(swept):
    """Review Focus 4: the boundary, a day each side."""
    _call("ret-old", 31)
    _call("ret-young", 29)
    removed = retention.sweep(NOW)
    with session_scope() as db:
        old, young = db.get(AiInvocation, "ret-old"), db.get(AiInvocation, "ret-young")
        assert old.response is None and old.response_cleared == "retention"
        assert young.response == "said"
    assert removed["model_replies"] == 1


def test_the_forge_s_replies_are_not_swept(swept):
    _call("ret-forge", 400, agent="forge", purpose="chat")
    retention.sweep(NOW)
    with session_scope() as db:
        assert db.get(AiInvocation, "ret-forge").response == "said"


def test_a_pass_with_nothing_to_do_still_says_it_ran(swept):
    retention.sweep(NOW)
    with session_scope() as db:
        rows = db.scalars(sa.select(RetentionSweep)).all()
    assert {r.category for r in rows} == {"model_replies", "drafts"}
    assert all(r.removed == 0 for r in rows)


def test_drafts_are_kept_by_default_and_deleted_once_a_limit_is_set(g_case, swept, monkeypatch):
    with session_scope() as db:
        db.execute(sa.update(PipelineDraft).values(updated_at=NOW - timedelta(days=400)))
    retention.sweep(NOW)
    with session_scope() as db:
        assert db.scalar(sa.select(sa.func.count()).select_from(PipelineDraft)) > 0
    monkeypatch.setenv("COMENI_RETENTION_DRAFTS_DAYS", "365")
    assert retention.sweep(NOW)["drafts"] >= 1


def test_the_last_sweep_is_served(swept):
    from fastapi.testclient import TestClient
    from mendel_api.main import create_app

    client = TestClient(create_app())
    assert client.get("/api/settings/retention/last").json() is None
    _call("ret-served", 40)
    retention.sweep(NOW)
    last = client.get("/api/settings/retention/last").json()
    assert last["removed"]["model_replies"] == 1 and last["ran_at"].startswith("2026-10-12")

"""Deleting a draft leaves nothing that names it, keeps the record that its model calls happened,
and leaves a fork of it whole (Part H spec §5.1)."""

from datetime import UTC, datetime

import pytest
import sqlalchemy as sa
from mendel_api.db import Base, session_scope
from mendel_api.models import AiInvocation, GateRun, PipelineAuthoringSession, PipelineDraft
from mendel_api.services import decisions, deletion, session
from mendel_api.settings import settings
from mendel_postgres import reachable
from test_authoring_building import clean as clean
from test_correction_forks import _manual
from test_fact_corrections import _correct

pytestmark = pytest.mark.skipif(not reachable(), reason="no database")


def _draft_of(sid: str) -> str:
    with session_scope() as db:
        return db.get(PipelineAuthoringSession, sid).draft_id


def _naming(draft_id: str, sessions: list[str]) -> dict[str, int]:
    """Every row in every table that names the draft or one of its sessions — except
    `ai_invocation`, whose rows are kept on purpose."""
    found = {}
    with session_scope() as db:
        for table in Base.metadata.tables.values():
            for column, ids in (("draft_id", [draft_id]), ("session_id", sessions)):
                if column in table.c and table.name != "ai_invocation" and ids:
                    n = db.scalar(sa.select(sa.func.count()).select_from(table)
                                  .where(table.c[column].in_(ids)))
                    if n:
                        found[table.name] = n
        if db.get(PipelineDraft, draft_id):
            found["pipeline_draft"] = 1
    return found


def _call(sid: str, id: str = "inv-del") -> None:
    with session_scope() as db:
        db.add(AiInvocation(id=id, agent="builder", purpose="ask", model="m", prompt_id="p",
                            prompt_digest="d", state="succeeded", started_at=datetime.now(UTC),
                            response="the sample says R1", session_id=sid))


def test_a_deleted_draft_leaves_no_row_and_no_directory(g_case):
    draft_id = _draft_of(g_case.session_id)
    (settings.draft_root / draft_id).mkdir(parents=True, exist_ok=True)
    assert _naming(draft_id, [g_case.session_id]), "the walk wrote nothing — measuring nothing"
    deletion.delete_draft(draft_id)
    assert _naming(draft_id, [g_case.session_id]) == {}
    assert not (settings.draft_root / draft_id).exists()


def test_its_model_calls_keep_their_record_and_lose_their_text(g_case):
    _call(g_case.session_id)
    deletion.delete_draft(_draft_of(g_case.session_id))
    with session_scope() as db:
        call = db.get(AiInvocation, "inv-del")
        assert call is not None and call.response is None
        assert call.response_cleared == "deleted" and call.model == "m"


def test_a_fork_of_it_keeps_its_history_and_forgets_where_it_came_from(clean):
    """Review Focus 2. A corrected fork reads its parent's evidence through its own access rows
    (Part F); deleting the parent hands the observations the fork uses to the fork, so its own
    history and every current decision survive. The parent's history, which the fork showed by
    reference (`inherited`), goes with the parent: that is what deleting it means."""
    sid = _manual()
    parent = _draft_of(sid)
    child = _correct(sid, "read_length", 50)["draft_id"]

    def own():
        return [e for e in decisions.history(child, "read_length") if not e.get("inherited")]

    before, facts = own(), decisions.read(child).facts
    assert before, "the fork has no history of its own — measuring nothing"
    deletion.delete_draft(parent)
    with session_scope() as db:
        row = db.get(PipelineDraft, child)
        assert row is not None
        assert (row.forked_from, row.fork_key, row.fork_sequence, row.fork_at) == (None,) * 4
    assert own() == before
    assert decisions.read(child).facts == facts
    assert _naming(parent, []) == {}


def test_a_draft_with_a_gate_running_is_refused(g_case):
    draft_id = _draft_of(g_case.session_id)
    with session_scope() as db:
        db.add(GateRun(id="gate-live", draft_id=draft_id, who="t", gate="stub", state="running",
                       queued_at=datetime.now(UTC)))
    with pytest.raises(ValueError, match="MI0401"):
        deletion.delete_draft(draft_id)
    assert _naming(draft_id, [g_case.session_id])
    with session_scope() as db:
        db.execute(sa.delete(GateRun).where(GateRun.id == "gate-live"))


def test_the_route_deletes_and_a_second_delete_is_404(g_case):
    from fastapi.testclient import TestClient
    from mendel_api.main import create_app

    client = TestClient(create_app())
    draft_id = _draft_of(g_case.session_id)
    assert client.delete(f"/api/pipeline/drafts/{draft_id}").status_code == 204
    assert client.delete(f"/api/pipeline/drafts/{draft_id}").status_code == 404


def test_a_session_reads_its_cleared_call_as_cleared(g_case):
    """The call panel says why a reply is empty rather than showing nothing."""
    _call(g_case.session_id, "inv-kept")
    with session_scope() as db:
        deletion.clear_replies(db, AiInvocation.id == "inv-kept", "retention")
    calls = session.calls(g_case.session_id)
    cleared = next(c for c in calls if c["id"] == "inv-kept")
    assert cleared["response"] is None and cleared["cleared"] == "retention"


def test_a_reply_that_lands_after_its_draft_was_deleted_keeps_no_text(g_case):
    """Review finding 2: a model call already in flight when the draft goes must not leave the
    sample's quotes behind; its record is written cleared."""
    deletion.delete_draft(_draft_of(g_case.session_id))
    _call(g_case.session_id, "inv-late")
    with session_scope() as db:
        late = db.get(AiInvocation, "inv-late")
        assert late.response is None and late.response_cleared == "deleted"


def test_a_reply_for_a_live_session_keeps_its_text(g_case):
    _call(g_case.session_id, "inv-live")
    with session_scope() as db:
        assert db.get(AiInvocation, "inv-live").response == "the sample says R1"

"""`c.Change`: one command for any change to intent or facts, taken at the waiting nodes the
correction section already draws (Part I.0 spec §5.1)."""

import pytest
from mendel_api.db import session_scope
from mendel_api.models import PipelineAuthoringSession, PipelineDraft
from mendel_api.services import decisions, session
from mendel_authoring import commands as c
from mendel_authoring.payloads import Change
from test_authoring_building import (  # noqa: F401
    _answer_all,
    _resolving,
    authoring_setup,
)
from test_authoring_building import clean as clean


def _versions(sid):
    with session_scope() as db:
        row = db.get(PipelineAuthoringSession, sid)
        draft = db.get(PipelineDraft, row.draft_id)
        return row.draft_id, draft.decision_revision, draft.revision, row.row_version


def _change(sid, change: Change, *, stale=False):
    _draft_id, decision, revision, version = _versions(sid)
    return session.perform(c.Change(
        sid, change.model_dump(mode="json"), "ana",
        decision - 1 if stale else decision, revision, version,
    )).result


def test_a_change_at_a_step_re_resolves_like_a_correction(clean):
    sid = _resolving()
    _answer_all(sid, authoring_setup.start_building(sid))
    result = _change(sid, Change(kind="measurement", subject="read_length", value=50,
                                 heard="50 bp", heard_seq=1))
    assert result["phase"] == "building"
    draft_id = _versions(sid)[0]
    assert next(f.value for f in decisions.read(draft_id).facts
                if f.subject == "read_length") == 50
    assert decisions.heard_of(draft_id)[("fact", "read_length")] == ("50 bp", 1)


def test_a_tool_pinned_by_a_change_re_resolves(clean):
    sid = _resolving()
    _answer_all(sid, authoring_setup.start_building(sid))
    result = _change(sid, Change(kind="pin", subject="alignment.bam",
                                 value="nf-core/hisat2/align@2.2.2"))
    draft_id = _versions(sid)[0]
    assert decisions.read(draft_id).producers[0].contract == "nf-core/hisat2/align@2.2.2"
    assert result["phase"] in ("building", "complete")


def test_a_stale_change_is_refused(clean):
    sid = _resolving()
    _answer_all(sid, authoring_setup.start_building(sid))
    with pytest.raises(ValueError, match="MI0201"):
        _change(sid, Change(kind="measurement", subject="read_length", value=50), stale=True)


def test_an_undeclared_change_is_refused_and_nothing_moves(clean):
    sid = _resolving()
    _answer_all(sid, authoring_setup.start_building(sid))
    before = _versions(sid)
    with pytest.raises(ValueError, match="MI0204"):
        _change(sid, Change(kind="want", subject="made.up"))
    assert _versions(sid) == before


def test_the_route_answers_as_the_command_does(clean):
    from fastapi.testclient import TestClient
    from mendel_api.main import create_app

    sid = _resolving()
    _answer_all(sid, authoring_setup.start_building(sid))
    _draft_id, decision, revision, version = _versions(sid)
    answer = TestClient(create_app()).post(f"/api/pipeline/authoring/{sid}/changes", json={
        "change": {"kind": "measurement", "subject": "read_length", "value": 50},
        "expected_decision_revision": decision,
        "expected_draft_revision": revision,
        "expected_session_version": version,
    })
    assert answer.status_code == 200, answer.text
    assert answer.json()["phase"] == "building"


def test_a_change_while_gathering_closes_its_question(clean):
    """At `reply`, a change goes through `correct_fact` → gather again: the question it answers
    is not asked."""
    from test_authoring_gathering import _gathering, _payload, _pending_for

    sid = _gathering(["counts.matrix"])
    _pending_for(sid, "paired")
    _change(sid, Change(kind="measurement", subject="paired", value=True,
                        heard="paired-end", heard_seq=1, actor="model"))
    pending = session.pending_id(sid)
    assert pending is None or _payload(pending).get("subject") != "paired"

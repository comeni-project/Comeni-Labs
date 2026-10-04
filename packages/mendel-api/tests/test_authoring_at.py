"""Where a session rests (14.7.8.1): `at`, and the node derived for a row from before it."""

import secrets
from datetime import UTC, datetime

import pytest
from mendel_api.authoring.types import Mode, Phase
from mendel_api.db import session_scope
from mendel_api.models import PipelineAuthoringSession, PipelineDraft
from mendel_api.services import authoring, session
from mendel_authoring import state as st
from mendel_authoring.protocol import PROTOCOL
from sqlalchemy import text


@pytest.fixture
def sid():
    """One session on one draft, the tables emptied first (`test_authoring_service.py`'s way)."""
    with session_scope() as db:
        db.execute(text(
            "TRUNCATE TABLE pipeline_authoring_proposal, pipeline_authoring_turn, "
            "pipeline_authoring_session, pipeline_draft"
        ))
    draft_id = secrets.token_hex(16)
    with session_scope() as db:
        db.add(PipelineDraft(id=draft_id, who="tester", name="d",
                             graph={"nodes": [], "edges": []}, updated_at=datetime.now(UTC),
                             goal=None, provenance={}, revision=0))
    return authoring.open_session(draft_id, mode=Mode.BUILD, who="tester")


def _at(sid):
    with session_scope() as db:
        return session.rests_at(db, db.get(PipelineAuthoringSession, sid))


def _old(sid, phase: Phase):
    """A row from before `at`: the phase set, `at` null."""
    with session_scope() as db:
        row = db.get(PipelineAuthoringSession, sid)
        row.phase, row.at = phase.value, None


def test_a_new_session_rests_where_you_say_what_you_want(sid):
    assert _at(sid) == "say"


@pytest.mark.parametrize("phase, node", [
    (Phase.UNDERSTANDING, "say"), (Phase.GATHERING, "list_needs"),
    (Phase.GOAL_REVIEW, "card"), (Phase.RESOLVING, "resolve"), (Phase.BUILDING, "offer"),
    (Phase.COMPLETE, "done"), (Phase.FAILED, "failed"), (Phase.STOPPED, "stopped"),
])
def test_a_row_from_before_at_rests_on_its_phases_node(sid, phase, node):
    """Spec §8: every old phase has a derived node, and each is a built one."""
    _old(sid, phase)
    assert _at(sid) == node
    assert node in {n.id for n in PROTOCOL.nodes if n.built}


def test_every_phase_has_a_derived_node():
    assert set(session._BY_PHASE) == set(Phase)


def test_a_pending_turn_in_understanding_rests_where_the_model_works(sid):
    authoring.say(sid, "RNA-seq counts")
    _old(sid, Phase.UNDERSTANDING)
    assert _at(sid) == "family"


def test_a_pending_question_rests_on_the_reply(sid):
    _old(sid, Phase.GATHERING)
    authoring.propose(sid, kind=authoring.GAP, payload={"subject": "x", "kind": "input",
                                                        "why": "", "options": {}, "block": {}})
    assert _at(sid) == "reply"


@pytest.mark.parametrize("tier, node", [(1, "step_settled"), (2, "step_settled"),
                                        (3, "step_rule"), (4, "step_choice")])
def test_a_pending_step_rests_on_its_tiers_card(sid, tier, node):
    _old(sid, Phase.BUILDING)
    authoring.propose(sid, kind=authoring.STEP, payload={"node": "n", "options": {},
                                                         "block": {"tier": tier}})
    assert _at(sid) == node


def test_a_stored_node_wins_over_the_phase(sid):
    with session_scope() as db:
        db.get(PipelineAuthoringSession, sid).at = "family"
    assert _at(sid) == "family"


def test_a_test_moving_by_event_leaves_the_node_to_be_derived(sid):
    """Ruling 5: `move` is setup for tests, and clears `at`."""
    authoring.move(sid, st.Event.WANT_RETURNED, row_version=1)
    with session_scope() as db:
        assert db.get(PipelineAuthoringSession, sid).at is None
    assert _at(sid) == "list_needs"

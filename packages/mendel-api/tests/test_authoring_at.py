"""Where a session rests (14.7.8.1): `at`, and the node derived for a row from before it."""

import secrets
from datetime import UTC, datetime

import authoring_setup
import pytest
from mendel_api.authoring.types import Phase
from mendel_api.db import session_scope
from mendel_api.models import PipelineAuthoringSession, PipelineDraft
from mendel_api.services import session
from mendel_api.services import session as facade
from mendel_api.stages import _rows, gathering
from mendel_authoring import commands
from mendel_authoring import state as st
from mendel_authoring.protocol import PROTOCOL
from mendel_postgres import truncate


@pytest.fixture
def sid():
    """One session on one draft, the tables emptied first (`test_authoring_service.py`'s way)."""
    with session_scope() as db:
        db.execute(truncate(
            "TRUNCATE TABLE pipeline_authoring_proposal, pipeline_authoring_turn, "
            "pipeline_authoring_session, pipeline_draft, gate_run"
        ))
    draft_id = secrets.token_hex(16)
    with session_scope() as db:
        db.add(PipelineDraft(id=draft_id, who="tester", name="d",
                             graph={"nodes": [], "edges": []}, updated_at=datetime.now(UTC),
                             goal=None, provenance={}, revision=0))
    return facade.perform(commands.OpenSession(draft_id, "tester")).result


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
    (Phase.GOAL_REVIEW, "card"), (Phase.RESOLVING, "resolve"), (Phase.BUILDING, "step_card"),
    (Phase.COMPLETE, "wrap"), (Phase.FAILED, "failed"), (Phase.STOPPED, "stopped"),
])
def test_a_row_from_before_at_rests_on_its_phases_node(sid, phase, node):
    """Spec §8: every old phase has a derived node, and each is a built one."""
    _old(sid, phase)
    assert _at(sid) == node
    assert node in {n.id for n in PROTOCOL.nodes if n.built}


def test_every_phase_has_a_derived_node():
    assert set(session._BY_PHASE) == set(Phase)


def test_a_pending_turn_in_understanding_rests_where_the_model_works(sid):
    facade.perform(commands.Say(sid, "RNA-seq counts"))
    _old(sid, Phase.UNDERSTANDING)
    assert _at(sid) == "family"


def test_a_pending_question_rests_on_the_reply(sid):
    _old(sid, Phase.GATHERING)
    _rows.propose(sid, kind=gathering.GAP, payload={"subject": "x", "kind": "input",
                                                        "why": "", "options": {}, "block": {}})
    assert _at(sid) == "reply"


def test_a_stored_node_wins_over_the_phase(sid):
    with session_scope() as db:
        db.get(PipelineAuthoringSession, sid).at = "family"
    assert _at(sid) == "family"


def test_a_test_moving_by_event_leaves_the_node_to_be_derived(sid):
    """Ruling 5: `move` is setup for tests, and clears `at`."""
    authoring_setup.move(sid, st.Event.WANT_RETURNED, row_version=1)
    with session_scope() as db:
        assert db.get(PipelineAuthoringSession, sid).at is None
    assert _at(sid) == "list_needs"

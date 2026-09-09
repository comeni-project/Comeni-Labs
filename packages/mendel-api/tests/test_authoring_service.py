"""Authoring sessions against a real database.

**These need Postgres and they are the ones that matter.** The pure state machine is checked in
`test_authoring_state.py`; what cannot be checked there is whether a rule survives being written
down and read back — which is the failure this project keeps finding (`admit()` dropped fifteen
fields, and the record did not survive being read back, both found by running rather than by a
test written to pass).

Every scenario Task 3 names has a test here: reload, retry, duplicate delivery, two-tab stale
acceptance, and a model call that finishes after the draft changed.
"""

import secrets
from datetime import UTC, datetime

import pytest
from mendel_api.authoring import state as st
from mendel_api.authoring.types import Mode, Phase, ProposalState, TurnState
from mendel_api.db import session_scope
from mendel_api.models import PipelineAuthoringTurn, PipelineDraft
from mendel_api.services import authoring
from sqlalchemy import select, text


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


@pytest.fixture
def clean_authoring():
    """An empty authoring workflow, and the drafts the sessions hang off.

    **All four in one `TRUNCATE`**, for `clean_forge`'s reason: every foreign key here is
    `RESTRICT`, so truncating `pipeline_draft` on its own is refused while a session points at
    it — which is the constraint working, and exactly what these tests are for.
    """
    tables = (
        "pipeline_authoring_proposal, pipeline_authoring_turn, "
        "pipeline_authoring_session, pipeline_draft"
    )
    with session_scope() as session:
        session.execute(text(f"TRUNCATE TABLE {tables}"))
    yield


@pytest.fixture
def draft(clean_authoring) -> str:
    """One draft to converse about, written through the model rather than a service.

    These tests are about the authoring rows; routing draft creation through the draft service
    would make every one of them depend on that service's validation too.
    """
    draft_id = secrets.token_hex(16)
    with session_scope() as session:
        session.add(
            PipelineDraft(
                id=draft_id,
                who="tester",
                name="rnaseq",
                graph={"nodes": [], "edges": []},
                updated_at=datetime.now(UTC),
                goal=None,
                provenance={},
                revision=0,
            )
        )
    return draft_id


def _bump(draft_id: str) -> int:
    """Move the draft on, the way accepting a proposal would."""
    with session_scope() as session:
        row = session.get(PipelineDraft, draft_id)
        row.revision += 1
        return row.revision


# ── the checkpoint ────────────────────────────────────────────────────────────────────────


def test_a_session_survives_being_read_back_in_a_new_connection(draft):
    """**Task 3's checkpoint.** Everything written comes back unchanged from a fresh session.

    `session_scope` opens and closes a connection per call, so every read below is a genuinely
    new one — which is what "restart the API" tests in a unit test. The property is not
    hypothetical: W1's record did not survive being read back, because it was written by field
    name and validated by alias, and no test that stayed inside one session could have seen it.
    """
    session_id = authoring.open_session(draft, mode=Mode.BUILD, who="tester")
    authoring.say(session_id, "I have paired fastq and I want counts per gene")
    proposal_id = authoring.propose(
        session_id, kind="step_proposal", payload={"node": "align", "contract": "nf-core/star"}
    )

    read = authoring.read(session_id)

    assert read["id"] == session_id
    assert read["draft_id"] == draft
    assert read["mode"] == Mode.BUILD.value
    assert read["phase"] == Phase.UNDERSTANDING.value
    assert read["revision"] == 0
    assert [t["role"] for t in read["turns"]] == ["person", "assistant"]
    assert read["turns"][0]["text"] == "I have paired fastq and I want counts per gene"
    assert read["turns"][1]["state"] == TurnState.PENDING.value
    assert read["pending_proposal"]["id"] == proposal_id
    assert read["pending_proposal"]["payload"]["node"] == "align"


def test_the_confirmed_goal_survives_the_round_trip(draft):
    """`goal` is JSON and nullable, and the two states it can be in are different facts. A goal
    that came back as `{}` would be indistinguishable from one nobody confirmed."""
    session_id = authoring.open_session(draft, mode=Mode.BUILD, who="tester")
    assert authoring.read(session_id)["goal"] is None

    goal = {"have": [], "want": ["counts.matrix"], "constraints": {}, "profile": {}}
    authoring.move(session_id, st.Event.GOAL_RETURNED, row_version=1, goal=goal)

    reread = authoring.read(session_id)
    assert reread["goal"] == goal
    assert reread["phase"] == Phase.GOAL_REVIEW.value


# ── reload ────────────────────────────────────────────────────────────────────────────────


def test_the_transcript_reloads_in_the_order_it_was_written(draft):
    """`seq`, not `at`. Two turns written inside one clock tick sort arbitrarily by timestamp,
    and a transcript that reorders itself on reload is the defect an ordering by time hides
    until the machine is fast enough to expose it — which is every machine."""
    session_id = authoring.open_session(draft, mode=Mode.BUILD, who="tester")
    for word in ("first", "second", "third"):
        authoring.say(session_id, word)

    said = [t["text"] for t in authoring.read(session_id)["turns"] if t["role"] == "person"]
    assert said == ["first", "second", "third"]

    seqs = [t["seq"] for t in authoring.read(session_id)["turns"]]
    assert seqs == sorted(seqs) and len(seqs) == len(set(seqs))


def test_one_draft_gets_one_session(draft):
    """§2 gives a session one phase and one cursor, so two sessions on one draft would be two
    answers to *where are we*. Refused with a sentence; the unique index is the half that holds
    when two requests arrive together."""
    authoring.open_session(draft, mode=Mode.BUILD, who="tester")
    with pytest.raises(ValueError) as raised:
        authoring.open_session(draft, mode=Mode.SPAWN, who="someone else")
    assert "already has an authoring session" in str(raised.value)


# ── retry ─────────────────────────────────────────────────────────────────────────────────


def test_a_failed_session_retries_the_phase_that_failed(draft):
    """The whole reason `failed_from` is a column. A build that failed must not be retried as a
    prompt call — that re-asks a person a question they have already answered."""
    session_id = authoring.open_session(draft, mode=Mode.BUILD, who="tester")
    authoring.move(session_id, st.Event.GOAL_RETURNED, row_version=1)
    authoring.move(session_id, st.Event.GOAL_ACCEPTED, row_version=2)
    assert authoring.read(session_id)["phase"] == Phase.RESOLVING.value

    authoring.move(session_id, st.Event.BUILD_FAILED, row_version=3)
    failed = authoring.read(session_id)
    assert failed["phase"] == Phase.FAILED.value
    assert failed["failed_from"] == Phase.RESOLVING.value

    authoring.move(session_id, st.Event.RETRY, row_version=4)
    assert authoring.read(session_id)["phase"] == Phase.RESOLVING.value


def test_recovering_from_failure_clears_the_recorded_phase(draft):
    """A stale `failed_from` sends the *next* retry to the wrong place — `forge_state.move`
    clears `failed_stage` for exactly this reason, and rule 9 inverted is a real defect rather
    than an untidiness."""
    session_id = authoring.open_session(draft, mode=Mode.BUILD, who="tester")
    authoring.move(session_id, st.Event.PROVIDER_FAILED, row_version=1)
    assert authoring.read(session_id)["failed_from"] == Phase.UNDERSTANDING.value

    authoring.move(session_id, st.Event.RETRY, row_version=2)
    assert authoring.read(session_id)["failed_from"] is None


def test_a_session_that_moved_underneath_you_refuses_the_write(draft):
    """`row_version` catches the *session* moving, which `expected_revision` cannot see: a model
    answer landing after the person revised their goal changes no draft revision at all."""
    session_id = authoring.open_session(draft, mode=Mode.BUILD, who="tester")
    authoring.move(session_id, st.Event.GOAL_RETURNED, row_version=1)

    with pytest.raises(ValueError) as raised:
        authoring.move(session_id, st.Event.GOAL_ACCEPTED, row_version=1)
    assert "MI0201" in str(raised.value)


# ── duplicate delivery ────────────────────────────────────────────────────────────────────


def test_answering_a_turn_twice_records_one_answer(draft):
    """A retried worker job, or an at-least-once queue. The correct answer to a duplicate is the
    same answer, not a second effect — re-answering would overwrite one account of what happened
    with another."""
    session_id = authoring.open_session(draft, mode=Mode.BUILD, who="tester")
    seq = authoring.say(session_id, "counts per gene")

    assert authoring.answer(session_id, seq, blocks=[{"kind": "narrative"}], base_revision=0)
    assert not authoring.answer(session_id, seq, blocks=[{"kind": "notice"}], base_revision=0)

    answered = [t for t in authoring.read(session_id)["turns"] if t["role"] == "assistant"]
    assert answered[0]["blocks"] == [{"kind": "narrative"}], "the second delivery overwrote"
    assert answered[0]["state"] == TurnState.ANSWERED.value


def test_deciding_a_proposal_twice_is_refused(draft):
    """`MI0203`. The first call decides and every later one is refused rather than re-applied,
    which is what makes accepting idempotent in the way that matters."""
    session_id = authoring.open_session(draft, mode=Mode.BUILD, who="tester")
    proposal_id = authoring.propose(session_id, kind="step_proposal", payload={})

    first = authoring.decide(
        proposal_id, ProposalState.ACCEPTED, expected_revision=0, by="person"
    )
    assert first.applies and first.state is ProposalState.ACCEPTED

    second = authoring.decide(
        proposal_id, ProposalState.REJECTED, expected_revision=1, by="person"
    )
    assert not second.applies
    assert "MI0203" in second.refusal
    assert second.state is ProposalState.ACCEPTED, "the outcome changed on a duplicate"


def test_one_pending_proposal_at_a_time(draft):
    """§2's MVP rule. Refused with a sentence; the partial unique index holds the race."""
    session_id = authoring.open_session(draft, mode=Mode.BUILD, who="tester")
    authoring.propose(session_id, kind="step_proposal", payload={})
    with pytest.raises(ValueError) as raised:
        authoring.propose(session_id, kind="setting_request", payload={})
    assert "waiting for an answer" in str(raised.value)


# ── two tabs ──────────────────────────────────────────────────────────────────────────────


def test_a_second_tab_accepting_against_an_older_view_changes_nothing(draft):
    """The ordinary case §2 names. Somebody accepts a step in one tab and then answers in the
    other, against a picture one revision old."""
    session_id = authoring.open_session(draft, mode=Mode.BUILD, who="tester")
    first = authoring.propose(session_id, kind="step_proposal", payload={"node": "align"})

    accepted = authoring.decide(first, ProposalState.ACCEPTED, expected_revision=0, by="person")
    assert accepted.applies and accepted.bumps_revision
    assert authoring.read(session_id)["revision"] == 1

    second = authoring.propose(session_id, kind="setting_request", payload={"node": "align"})
    stale_view = authoring.decide(
        second, ProposalState.ACCEPTED, expected_revision=0, by="person"
    )
    assert not stale_view.applies
    assert "MI0201" in stale_view.refusal
    assert authoring.read(session_id)["revision"] == 1, "a refused acceptance moved the draft"
    assert authoring.read(session_id)["pending_proposal"]["id"] == second


def test_a_proposal_from_before_the_draft_moved_goes_stale_and_never_applies(draft):
    """Task 3's property, end to end: *it never applies to a newer draft.*

    `stale`, not `rejected` — nobody rejected it. A person reading their transcript later must be
    able to tell a choice they declined from one the engine withdrew.
    """
    session_id = authoring.open_session(draft, mode=Mode.BUILD, who="tester")
    proposal_id = authoring.propose(session_id, kind="step_proposal", payload={"node": "align"})

    now = _bump(draft)  # the draft moved by some other route

    outcome = authoring.decide(
        proposal_id, ProposalState.ACCEPTED, expected_revision=now, by="person"
    )
    assert not outcome.applies
    assert outcome.state is ProposalState.STALE
    assert "MI0202" in outcome.refusal

    after = authoring.read(session_id)
    assert after["revision"] == now, "a stale proposal moved the draft"
    assert after["pending_proposal"] is None, "a stale proposal is still offered"


# ── a late model answer ───────────────────────────────────────────────────────────────────


def test_a_model_answer_that_lands_after_the_draft_changed_is_not_applied(draft):
    """The scenario Task 3 names last, and the one `row_version` alone would miss.

    The call did not fail — it answered a question that is no longer being asked. The turn is
    marked `failed` so the transcript says so, and its blocks are dropped rather than shown
    against a pipeline they do not describe.
    """
    session_id = authoring.open_session(draft, mode=Mode.BUILD, who="tester")
    seq = authoring.say(session_id, "use hisat2")

    _bump(draft)  # the person accepted something else while the model was thinking

    applied = authoring.answer(
        session_id, seq, blocks=[{"kind": "step_proposal"}], base_revision=0
    )
    assert applied is False

    with session_scope() as db:
        row = db.scalars(
            select(PipelineAuthoringTurn).where(
                PipelineAuthoringTurn.session_id == session_id,
                PipelineAuthoringTurn.seq == seq,
            )
        ).one()
        assert row.state == TurnState.FAILED.value
        assert row.blocks == [], "a late answer was shown against a pipeline it does not describe"

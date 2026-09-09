"""The authoring state machine, asked of the function rather than of a session.

**Pure, so this file needs no database and no clock.** `state.py` reads a phase and an event and
answers with a phase; everything that persists is `services/authoring.py`'s. That split is the
same one `mendel_forge.workflow` keeps, and it is what lets the diagram in the plan's §2 be
checked directly instead of being re-implemented in a service and checked by proxy.

The rule the file exists to keep: **the diagram is the specification.** Every transition asserted
here is an arrow drawn there, and an arrow that is not drawn is refused.
"""

import pytest
from mendel_api.authoring import state as st
from mendel_api.authoring.types import Phase, ProposalState

# ── the diagram, arrow by arrow ───────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("phase", "event", "expected"),
    [
        (Phase.UNDERSTANDING, st.Event.GOAL_RETURNED, Phase.GOAL_REVIEW),
        (Phase.UNDERSTANDING, st.Event.PROVIDER_FAILED, Phase.FAILED),
        (Phase.GOAL_REVIEW, st.Event.GOAL_ACCEPTED, Phase.RESOLVING),
        (Phase.GOAL_REVIEW, st.Event.GOAL_REVISED, Phase.UNDERSTANDING),
        (Phase.RESOLVING, st.Event.BLUEPRINT_STORED, Phase.BUILDING),
        (Phase.RESOLVING, st.Event.BUILD_FAILED, Phase.FAILED),
        (Phase.BUILDING, st.Event.PROPOSAL_SETTLED, Phase.BUILDING),
        (Phase.BUILDING, st.Event.NOTHING_LEFT, Phase.COMPLETE),
        (Phase.BUILDING, st.Event.GOAL_ACCEPTED, Phase.RESOLVING),
        (Phase.COMPLETE, st.Event.GOAL_ACCEPTED, Phase.RESOLVING),
    ],
)
def test_every_arrow_in_the_diagram_is_a_transition(phase, event, expected):
    """§2's diagram, transcribed. A missing arrow here is a session that cannot get somewhere
    the design says it goes, and the symptom is a person stuck on a screen."""
    assert st.advance(phase, event) is expected


def test_a_completed_session_can_be_reopened_by_a_goal_revision():
    """`complete --> resolving` is the arrow that makes the pipeline *living* rather than
    finished. Without it the only way to change a completed pipeline is to start again."""
    assert st.advance(Phase.COMPLETE, st.Event.GOAL_ACCEPTED) is Phase.RESOLVING


def test_an_arrow_the_diagram_does_not_draw_is_refused():
    """A closed table, not a default. Silently ignoring an illegal event would let the phase and
    the transcript disagree, and the transcript is what a person reads."""
    with pytest.raises(ValueError) as raised:
        st.advance(Phase.UNDERSTANDING, st.Event.NOTHING_LEFT)
    assert "MI0200" in str(raised.value)


def test_the_refusal_says_what_can_happen_instead():
    """`workflow.refuse` sets the precedent: a refusal that names only the illegal move leaves
    the caller to guess, and the recovery is one request only if the answer is in the sentence.
    """
    with pytest.raises(ValueError) as raised:
        st.advance(Phase.COMPLETE, st.Event.PROPOSAL_SETTLED)
    assert "goal_accepted" in str(raised.value)


def test_the_table_covers_every_phase():
    """`tests/README.md`: a loop is not an assertion. Every phase must appear as a source or be
    deliberately terminal, so a phase added to the enum and forgotten here is visible."""
    sources = {phase for phase, _ in st.TRANSITIONS}
    assert sources, "the transition table is empty"
    unreachable = set(Phase) - sources - {Phase.FAILED}
    assert unreachable == set(), f"these phases can never be left: {sorted(unreachable)}"


# ── retry resumes the stage that failed ───────────────────────────────────────────────────


def test_retry_resumes_the_phase_that_failed():
    """§2 draws **two** arrows out of `failed`, and `phase` alone cannot choose between them.

    This is `workflow.retry_target`'s argument arriving a second time: a failed build retried as
    a prompt call would re-ask a person a question they have already answered.
    """
    assert st.advance(Phase.FAILED, st.Event.RETRY, Phase.UNDERSTANDING) is Phase.UNDERSTANDING
    assert st.advance(Phase.FAILED, st.Event.RETRY, Phase.RESOLVING) is Phase.RESOLVING


def test_an_unrecorded_failure_retries_from_the_beginning():
    """The safe reading, and the same one the forge takes: an unrecorded stage costs one extra
    model call and cannot skip a step. Guessing `resolving` would resume a build on a goal that
    may never have been confirmed."""
    assert st.advance(Phase.FAILED, st.Event.RETRY, None) is Phase.UNDERSTANDING


def test_a_failure_records_where_it_came_from():
    """The column exists to be written. A `failed` session that does not know what failed is a
    session `retry` has to guess about, which is the defect `failed_from` was added to close."""
    assert st.failed_from(Phase.RESOLVING) is Phase.RESOLVING
    assert st.failed_from(Phase.UNDERSTANDING) is Phase.UNDERSTANDING


# ── compare and swap ──────────────────────────────────────────────────────────────────────


def test_a_proposal_on_the_current_draft_is_accepted():
    outcome = st.settle(
        current=ProposalState.PENDING,
        proposal_revision=4,
        draft_revision=4,
        expected_revision=4,
        decision=ProposalState.ACCEPTED,
    )
    assert outcome.state is ProposalState.ACCEPTED
    assert outcome.refusal is None
    assert outcome.applies is True


def test_a_client_acting_on_an_older_view_is_refused_and_changes_nothing():
    """Two tabs, which §2 calls the ordinary case. The second acceptance is against a picture
    one revision old, and `MI0201` is what it gets."""
    outcome = st.settle(
        current=ProposalState.PENDING,
        proposal_revision=5,
        draft_revision=5,
        expected_revision=4,
        decision=ProposalState.ACCEPTED,
    )
    assert outcome.applies is False
    assert "MI0201" in outcome.refusal
    assert outcome.state is ProposalState.PENDING, "a conflict must not settle the proposal"


def test_a_proposal_made_against_an_older_draft_becomes_stale_and_never_applies():
    """The property Task 3 names: *it never applies to a newer draft*.

    `stale` rather than `rejected`, because nobody rejected it. A person reading their own
    transcript later has to be able to tell a choice they declined from one the engine withdrew.
    """
    outcome = st.settle(
        current=ProposalState.PENDING,
        proposal_revision=4,
        draft_revision=5,
        expected_revision=5,
        decision=ProposalState.ACCEPTED,
    )
    assert outcome.applies is False
    assert outcome.state is ProposalState.STALE
    assert "MI0202" in outcome.refusal


def test_settling_a_settled_proposal_is_refused_rather_than_repeated():
    """A duplicate delivery — a retried request, or a double click. The correct answer to a
    duplicate is the same answer, not a second effect."""
    for already in (ProposalState.ACCEPTED, ProposalState.REJECTED, ProposalState.STALE):
        outcome = st.settle(
            current=already,
            proposal_revision=4,
            draft_revision=4,
            expected_revision=4,
            decision=ProposalState.ACCEPTED,
        )
        assert outcome.applies is False, already
        assert "MI0203" in outcome.refusal, already
        assert outcome.state is already, "a refusal must leave the outcome as it was"


def test_a_rejection_settles_without_touching_the_draft():
    """Declining a proposal is a decision and is recorded, and it advances no revision — the
    draft did not change, so a revision bump would make the next acceptance look stale."""
    outcome = st.settle(
        current=ProposalState.PENDING,
        proposal_revision=4,
        draft_revision=4,
        expected_revision=4,
        decision=ProposalState.REJECTED,
    )
    assert outcome.state is ProposalState.REJECTED
    assert outcome.applies is True
    assert outcome.bumps_revision is False


def test_an_acceptance_bumps_the_revision_and_a_rejection_does_not():
    """What makes the next proposal stale is the revision moving, so which outcomes move it is
    the whole of the concurrency design and is stated once, here."""
    accepted = st.settle(
        current=ProposalState.PENDING,
        proposal_revision=1,
        draft_revision=1,
        expected_revision=1,
        decision=ProposalState.ACCEPTED,
    )
    assert accepted.bumps_revision is True


def test_a_decision_must_be_a_settlement_and_not_pending():
    """Settling something to `pending` is a no-op dressed as a transition, and it would leave
    the one-pending index enforcing uniqueness over a row nobody moved."""
    with pytest.raises(ValueError):
        st.settle(
            current=ProposalState.PENDING,
            proposal_revision=1,
            draft_revision=1,
            expected_revision=1,
            decision=ProposalState.PENDING,
        )

"""What may happen to an adaptation, checked without a database.

**This is the half of the workflow that CI runs.** `mendel-api`'s tests skip when Postgres is
unreachable, and CI has none — so a transition rule that only existed inside the service would
be a rule nothing checked on a pull request. The rules live in `mendel_forge.workflow` for that
reason, and this is the suite that holds them.
"""

import pytest
from mendel_forge.workflow import (
    ACTIVE,
    ALLOWED,
    RUNNING,
    SEALED,
    TERMINAL,
    AdaptationState,
    EventKind,
    InvocationPurpose,
    InvocationState,
    MessageRole,
    MessageState,
    RevisionState,
    allowed,
    approval_refusals,
    refuse,
    retry_target,
    sealed,
)


def test_every_state_is_in_the_table():
    """`ALLOWED`'s docstring promises this, so it is a test rather than a sentence.

    A state missing from the table is not a state nothing can leave — it is a `KeyError` at the
    moment somebody tries, which is the worst place for a typo to surface. And a state present
    only as a *value* would be a state nothing can ever reach.
    """
    assert set(ALLOWED) == set(AdaptationState)
    reachable = {target for onward in ALLOWED.values() for target in onward}
    unreachable = set(AdaptationState) - reachable - {AdaptationState.SCAFFOLDING}
    assert unreachable == set(), f"nothing can reach: {sorted(unreachable)}"


def test_the_terminal_states_are_derived_and_are_the_two_expected():
    """`TERMINAL` is computed from `ALLOWED`, and the value is asserted here rather than in the
    module. A second literal list would be a second answer to the same question."""
    assert frozenset({AdaptationState.PUBLISHED, AdaptationState.ARCHIVED}) == TERMINAL
    assert set(AdaptationState) - TERMINAL == ACTIVE
    assert RUNNING < ACTIVE


def test_the_table_matches_the_rules_spelled_out():
    """**The readability half of computing `ALLOWED`.**

    An enumerated table can be read at a glance; a computed one has to be run. This is the
    glance, written out, so a reader has one and a change to `_exits` has to be agreed with in
    two places rather than absorbed silently by every caller.

    It is not a duplicate of the rules — it is the rules *applied*, which is exactly what a
    reader of a comprehension cannot see.
    """
    S = AdaptationState
    assert {state: set(onward) for state, onward in ALLOWED.items()} == {
        S.SCAFFOLDING: {S.QUEUED, S.FAILED},
        S.QUEUED: {S.GENERATING, S.FAILED, S.ARCHIVED},
        S.GENERATING: {S.VALIDATING, S.FAILED},
        S.VALIDATING: {S.REVIEW, S.FAILED},
        S.REVIEW: {S.CHANGES_REQUESTED, S.PUBLISHING, S.FAILED, S.ARCHIVED},
        S.CHANGES_REQUESTED: {S.GENERATING, S.FAILED, S.ARCHIVED},
        S.PUBLISHING: {S.PUBLISHED, S.REVIEW, S.FAILED},
        S.PUBLISHED: set(),
        S.FAILED: {S.QUEUED, S.SCAFFOLDING, S.ARCHIVED},
        S.ARCHIVED: set(),
    }


def test_anything_a_worker_holds_can_record_its_own_failure():
    """Rule 7, and the hole that computing the table closed.

    `validating` had `review` as its only successor, so a worker killed mid-validation left a
    row whose only legal move was **forward** — Task 7's recovery sweep would have had to
    promote a half-validated candidate or write a state the table forbids.
    """
    for state in RUNNING:
        assert AdaptationState.FAILED in ALLOWED[state], f"{state} cannot record a failure"


def test_a_row_a_worker_holds_cannot_be_archived_out_from_under_it():
    """The distinction `_exits` draws: failing is what a *sweep* does to a row whose worker is
    already gone; archiving would orphan a job that is still running.

    `publishing` is the sharpest case — it is the transition that writes to the registry.
    """
    for state in RUNNING:
        assert AdaptationState.ARCHIVED not in ALLOWED[state], f"{state} can be archived"
    assert RUNNING, "an empty set would make that loop assert nothing"


def test_a_failed_adaptation_can_finally_be_closed():
    """Settled by the operator on 2026-09-04 and built on 2026-09-05.

    Archiving destroys nothing — every foreign key is `RESTRICT`, `forge_event` has no update
    path, revisions and the invocation audit survive — so it is a lifecycle statement rather
    than a disposal. The old table let `review` archive and `failed` not, which is backwards:
    the *healthier* state could be closed and the stuck one could not.

    The cost of that was concrete: the partial unique index excludes exactly the finished
    states, so a failed adaptation held its catalogue item's one-active slot forever, with no
    exit but retry or a manual `UPDATE`.
    """
    assert allowed(AdaptationState.FAILED, AdaptationState.ARCHIVED)
    assert AdaptationState.ARCHIVED in TERMINAL


def test_no_state_transitions_to_itself():
    """`failed -> failed` fell straight out of the derivation.

    A compare-and-swap that expects `failed` and writes `failed` succeeds: it bumps the row
    version, records an event and changes nothing — a retry loop reporting progress. The
    enumerated table could not express this defect, which is the price of computing one.
    """
    assert [state for state, onward in ALLOWED.items() if state in onward] == []


def test_a_legal_transition_is_not_refused():
    assert allowed(AdaptationState.REVIEW, AdaptationState.PUBLISHING)
    assert refuse(AdaptationState.REVIEW, AdaptationState.PUBLISHING) is None


def test_approving_something_still_generating_is_refused_and_says_what_is_possible():
    """The refusal a page hits when it draws *Approve* on a row that is still running.

    It names the legal successors, because a refusal that only says no makes the caller guess,
    and the guess is another round trip.
    """
    message = refuse(AdaptationState.GENERATING, AdaptationState.PUBLISHING)
    assert message is not None
    assert "MF0300" in message
    assert "validating" in message and "failed" in message


def test_a_terminal_state_goes_nowhere_and_says_so_in_words():
    message = refuse(AdaptationState.PUBLISHED, AdaptationState.REVIEW)
    assert message is not None
    assert "it is finished" in message


def test_no_transition_leaves_a_terminal_state():
    for state in TERMINAL:
        assert ALLOWED[state] == frozenset(), f"{state} is not terminal after all"


def test_publishing_can_fall_back_to_review():
    """The registry moved, or `land` refused. The candidate is not lost and not published —
    it goes back to the reviewer, which is the only honest third answer."""
    assert allowed(AdaptationState.PUBLISHING, AdaptationState.REVIEW)
    assert allowed(AdaptationState.PUBLISHING, AdaptationState.PUBLISHED)


def test_requesting_changes_returns_to_generating_rather_than_ending_anything():
    """§1.6 — *request changes* is not rejection. It queues another attempt, so the state it
    leads to is one an attempt starts from.

    **This asserted `ARCHIVED not in ALLOWED[CHANGES_REQUESTED]` until 2026-09-05, and that was
    the enumerated table's gap wearing a test's clothes.** The claim being made is that
    requesting changes *continues* rather than ends — which is about where it leads, not about
    what a curator may later decide. Someone who asks for changes and then concludes the tool
    is not worth adapting should be able to close it; refusing that was never a design position,
    it was a row nobody wrote.
    """
    assert allowed(AdaptationState.REVIEW, AdaptationState.CHANGES_REQUESTED)
    assert allowed(AdaptationState.CHANGES_REQUESTED, AdaptationState.GENERATING)
    assert AdaptationState.PUBLISHED not in ALLOWED[AdaptationState.CHANGES_REQUESTED], (
        "requesting changes must not be a route to publishing without another attempt"
    )


def test_a_scaffold_failure_retries_as_a_scaffold_and_not_as_a_model_call():
    """Rule 9, and the reason `failed_stage` is a column.

    A source that could not be read is not repaired by queueing a model. The plan's diagram
    draws one arrow out of `failed`; the prose says retry resumes the stage, and the prose is
    the one that can be right about both cases.
    """
    assert retry_target(AdaptationState.SCAFFOLDING) is AdaptationState.SCAFFOLDING
    assert retry_target(AdaptationState.GENERATING) is AdaptationState.QUEUED
    assert retry_target(None) is AdaptationState.QUEUED


def test_every_retry_target_is_a_legal_successor_of_failed():
    """The two rules are written in two places — `ALLOWED[FAILED]` and `retry_target` — and
    this is what stops them from disagreeing. Widening one without the other produces a retry
    that is refused by the transition it was computed for."""
    for stage in [*AdaptationState, None]:
        assert retry_target(stage) in ALLOWED[AdaptationState.FAILED]


def test_a_revision_is_sealed_from_the_moment_validation_begins():
    """Rule 3. `VALIDATING` is inside the set, not after it: a candidate rewritten *while* it
    is being checked breaks the verdict just as thoroughly as one rewritten afterwards."""
    assert sealed(RevisionState.VALIDATING)
    assert sealed(RevisionState.VALIDATED)
    assert not sealed(RevisionState.SCAFFOLDED)
    assert not sealed(RevisionState.GENERATING)
    assert set(RevisionState) > SEALED


def _approval(**overrides):
    ready = {
        "revision_id": "r1",
        "revision_state": RevisionState.VALIDATED,
        "unresolved_required": 0,
        "validation_green": True,
        "who": "rafael",
        "reason": "checked the ports against meta.yml",
        "registry_digest_at_validation": "abc",
        "registry_digest_now": "abc",
    }
    return approval_refusals(**{**ready, **overrides})


def test_a_ready_candidate_has_nothing_against_it():
    assert _approval() == []


@pytest.mark.parametrize(
    "override,expected",
    [
        ({"revision_id": None, "revision_state": None}, "no current revision"),
        ({"revision_state": RevisionState.GENERATING}, "not validated"),
        ({"unresolved_required": 3}, "3 required hole"),
        ({"validation_green": False}, "validation did not pass"),
        ({"who": "   "}, "named human"),
        ({"reason": ""}, "needs a reason"),
        ({"registry_digest_now": "def"}, "the registry moved"),
    ],
)
def test_each_approval_condition_refuses_on_its_own(override, expected):
    """Six conditions plus the revision-state check, each failing in isolation.

    Parameterised rather than written as one test with seven asserts: a single test tells you
    approval is broken, and seven tell you which condition it is.
    """
    refusals = _approval(**override)
    assert any(expected in r for r in refusals), refusals
    assert all("MF0301" in r for r in refusals)


def test_every_unmet_condition_is_reported_at_once():
    """**Not the first one.** A reviewer who fixes one thing, presses the button and is told
    about the next has paid six round trips for facts the server had at the first press."""
    refusals = _approval(
        validation_green=False,
        who="",
        reason="",
        registry_digest_now="moved",
        unresolved_required=2,
    )
    assert len(refusals) >= 5


def test_a_stale_registry_refusal_names_both_digests():
    """The one condition that goes stale while nobody touches the adaptation. A refusal that
    said only *re-validate* would leave a reviewer unable to tell whether anything changed."""
    refusals = _approval(registry_digest_at_validation="was", registry_digest_now="is")
    stale = next(r for r in refusals if "registry moved" in r)
    assert "was" in stale and "is" in stale


def test_the_closed_vocabularies_have_no_duplicate_values():
    """Every enum here is written into a database column and read back out. Two members
    sharing a value would make the round trip lossy in a way nothing else would notice."""
    for enum in (
        AdaptationState,
        RevisionState,
        EventKind,
        MessageRole,
        MessageState,
        InvocationPurpose,
        InvocationState,
    ):
        values = [member.value for member in enum]
        assert len(values) == len(set(values)), enum


def test_refused_is_not_folded_into_failed():
    """A provider that timed out and a model whose answer did not validate are different
    findings, and only one of them is worth retrying."""
    assert InvocationState.REFUSED is not InvocationState.FAILED
    assert {"refused", "failed"} < {member.value for member in InvocationState}

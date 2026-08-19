"""Deciding a proposal: approve, rename, or reject with a reason.

Phase 2 made declining possible and left it a dead end — a proposed hole could not be resolved
by anything. This is the resolution, and its two halves are asymmetric on purpose: approving
settles the hole, rejecting reopens it and keeps the record.
"""

import pytest
from comeni_core.review import ValueSource
from mendel_forge.scaffold import Decision, Proposal, Scaffold


@pytest.fixture
def closed_scaffold(complete_scaffold) -> Scaffold:
    """One hole with a CLOSED candidate list, so `fill` refuses anything outside it."""
    from comeni_core.review import Candidate
    from mendel_forge.scaffold import Hole

    return complete_scaffold.model_copy(
        update={
            "holes": [
                Hole(
                    subject="produces[0].type_id",
                    what="the semantic type of the output",
                    why_open="nf-core declares it as type: file",
                    candidates=[Candidate(value="qc.report"), Candidate(value="alignment.bam")],
                    closed=True,
                )
            ]
        }
    )


def _proposed(scaffold: Scaffold, field: str) -> Scaffold:
    return scaffold.propose(
        field,
        Proposal(id="qc.index_stats", description="per-reference stats", why="nothing fits",
                 by="rafael"),
    )


def test_approving_settles_the_hole_with_the_proposed_id(incomplete_scaffold):
    field = incomplete_scaffold.holes[0].subject
    after = _proposed(incomplete_scaffold, field).decide(
        field, Decision.APPROVED, by="reviewer", why="it is a real distinct output"
    )

    assert after.filled[field].value == "qc.index_stats"
    assert after.filled[field].how is ValueSource.HUMAN
    assert after.filled[field].by == "reviewer"
    assert after.hole(field) is None, "an approved proposal closes the hole"


def test_approving_bypasses_the_candidate_check_on_purpose(closed_scaffold):
    """`fill` refuses a value outside the candidates — MF0003 — and that refusal is a
    guarantee. An approved proposal is BY DEFINITION not among them; that is what proposing
    means. So `decide` writes the value itself rather than routing through `fill`.

    **The `fill` half is asserted, not assumed.** `Question.legal` returns True when a hole
    has NO candidates, so this test run against `incomplete_scaffold` — whose only hole is
    `roles`, with none — would pass without demonstrating anything: `fill` would have
    accepted the value too. It needs a hole that genuinely refuses.
    """
    field = "produces[0].type_id"
    with pytest.raises(ValueError, match="MF0003"):
        closed_scaffold.fill(field, "qc.index_stats", ValueSource.HUMAN, by="r", why="w")

    after = _proposed(closed_scaffold, field).decide(
        field, Decision.APPROVED, by="reviewer", why="w"
    )
    assert after.filled[field].value == "qc.index_stats"


def test_renaming_approves_a_different_id_and_keeps_what_was_proposed(incomplete_scaffold):
    """A rename is a judgement about somebody's suggestion; losing the suggestion loses the
    judgement's subject."""
    field = incomplete_scaffold.holes[0].subject
    after = _proposed(incomplete_scaffold, field).decide(
        field, Decision.APPROVED, by="reviewer", why="clearer", id="qc.idxstats"
    )

    assert after.filled[field].value == "qc.idxstats"
    assert after.proposed[field].id == "qc.index_stats", "the proposal keeps what was proposed"
    assert after.proposed[field].decided_id == "qc.idxstats"


def test_rejecting_reopens_the_hole_and_records_why(incomplete_scaffold):
    """Deleting the proposal would make the hole look exactly like one nobody has reached,
    and telling those apart is what a decline exists to do."""
    field = incomplete_scaffold.holes[0].subject
    before = _proposed(incomplete_scaffold, field)
    after = before.decide(
        field, Decision.REJECTED, by="reviewer", why="idxstats is a measurement, not a type"
    )

    assert after.hole(field) is not None, "a rejected proposal leaves the hole open"
    # `filled` is compared whole rather than checking the field is absent: `incomplete_scaffold`
    # puts a `roles` hole back on a COMPLETE scaffold, so `roles` is already in `filled` and
    # `field not in after.filled` would fail against the fixture rather than the code.
    assert after.filled == before.filled, "rejecting writes no value"
    assert after.proposed[field].decision is Decision.REJECTED
    assert after.proposed[field].decided_why == "idxstats is a measurement, not a type"


def test_deciding_a_field_with_no_proposal_is_refused(incomplete_scaffold):
    field = incomplete_scaffold.holes[0].subject
    with pytest.raises(ValueError, match="MF0002"):
        incomplete_scaffold.decide(field, Decision.APPROVED, by="r", why="w")


def test_approved_lists_only_what_was_approved(incomplete_scaffold):
    """`land` writes one vocabulary file per entry here, so a rejected or undecided proposal
    appearing would put an unapproved type into the registry."""
    field = incomplete_scaffold.holes[0].subject
    scaffold = _proposed(incomplete_scaffold, field)

    assert scaffold.approved() == {}, "an undecided proposal is not approved"
    assert scaffold.decide(field, Decision.REJECTED, by="r", why="w").approved() == {}
    assert scaffold.decide(field, Decision.APPROVED, by="r", why="w").approved() == {
        field: "qc.index_stats"
    }

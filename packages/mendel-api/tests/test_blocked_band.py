"""A question blocked on a proposal outranks every ordinary question.

Design §4's ladder is drift, BLOCKED, ask, confirm, label — and `Band.rank` left 1 and 2 free
for exactly this. A blocked question is not more likely to be wrong; it is the thing stopping
a module from landing.
"""

from mendel_api.questions import Band, OpenQuestion, aggregate, band_for
from mendel_forge.scaffold import Decision, Proposal


def _open_proposal() -> Proposal:
    return Proposal(id="qc.index_stats", description="d", why="w", by="rafael")


def _decided(decision: Decision) -> Proposal:
    return _open_proposal().model_copy(
        update={"decision": decision, "decided_by": "r", "decided_why": "w"}
    )


def test_an_open_proposal_makes_a_question_blocked():
    assert band_for("roles", proposal=_open_proposal()) is Band.BLOCKED


def test_a_question_with_no_proposal_keeps_its_ordinary_band():
    assert band_for("roles") is Band.ROUTING
    assert band_for("consumes[0].name") is Band.COSMETIC


def test_a_rejected_proposal_returns_the_question_to_its_ordinary_band():
    """The hole is open again and nothing is blocking a landing — the record stays, but the
    work is ordinary work now."""
    assert band_for("roles", proposal=_decided(Decision.REJECTED)) is Band.ROUTING


def test_blocked_sorts_above_everything_else():
    def q(subject: str, band: Band) -> OpenQuestion:
        return OpenQuestion(
            subject=subject, what="", why_open="", band=band, asked_by=["fastqc"],
            candidates=[], closed=True, evidence=[],
        )

    rows = aggregate([q("roles", Band.ROUTING), q("produces[0].type_id", Band.BLOCKED)])
    assert [r.subject for r in rows] == ["produces[0].type_id", "roles"]
    assert Band.BLOCKED.rank < Band.ROUTING.rank

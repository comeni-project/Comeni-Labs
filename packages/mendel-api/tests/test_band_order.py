"""The order the queue is read in.

`docs/design/forge-review.md` §4: sort is by CONSEQUENCE, not recency and not alphabet. The
design's ladder is drift, blocked, ask, confirm, label — and of those five, phase 1 has ask,
confirm and label, because drift is phase 5 and proposals are phase 3.
"""

from mendel_api.questions import Band, OpenQuestion, aggregate


def _q(subject: str, band: Band, suggested: str | None = None) -> OpenQuestion:
    return OpenQuestion(
        subject=subject, what="", why_open="", band=band,
        asked_by=["fastqc"], candidates=[], closed=True, evidence=[], suggested=suggested,
    )


def test_a_band_declares_its_consequence_rather_than_inheriting_it():
    """`Band` is a StrEnum, so `sorted()` on it compares the VALUES: cosmetic, prose,
    routing. That is alphabetical order wearing the costume of a priority, and it put the
    cheapest work at the top of a queue whose whole claim is consequence-first."""
    assert Band.ROUTING.rank < Band.PROSE.rank < Band.COSMETIC.rank


def test_the_queue_puts_routing_first_and_cosmetic_last():
    rows = aggregate([
        _q("consumes[0].name", Band.COSMETIC),
        _q("priority_because", Band.PROSE),
        _q("roles", Band.ROUTING),
    ])
    assert [r.subject for r in rows] == ["roles", "priority_because", "consumes[0].name"]


def test_an_unanswered_question_outranks_one_a_model_answered():
    """Design §4: Ask before Confirm. A question nobody answered needs a person; one a
    model answered needs a glance."""
    rows = aggregate([
        _q("produces[0].type_id", Band.ROUTING, suggested="qc.report"),
        _q("consumes[0].type_id", Band.ROUTING),
    ])
    assert [r.subject for r in rows] == ["consumes[0].type_id", "produces[0].type_id"]

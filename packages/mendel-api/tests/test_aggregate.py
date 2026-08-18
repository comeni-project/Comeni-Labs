"""Identical work collapses into one row.

86 confirmable answers are not 86 rows; they are `consumes[0].type_id -> alignment.bam x11`.
This is the third of the three things that keep the queue bounded as the registry grows,
and the only one that is code rather than layout.
"""

from mendel_api.questions import Band, OpenQuestion, aggregate


def _q(subject="consumes[0].type_id", draft="a", suggested=None) -> OpenQuestion:
    return OpenQuestion(
        subject=subject, what="w", why_open="o", band=Band.ROUTING,
        asked_by=[draft], candidates=[], closed=True, evidence=[], suggested=suggested,
    )


def test_the_same_question_across_drafts_becomes_one_row():
    rows = aggregate([_q(draft="samtools/index"), _q(draft="samtools/sort"),
                      _q(draft="picard/markduplicates")])
    assert len(rows) == 1
    assert rows[0].asked_by == ["picard/markduplicates", "samtools/index", "samtools/sort"]


def test_different_subjects_stay_apart():
    rows = aggregate([_q(subject="consumes[0].type_id"), _q(subject="roles")])
    assert len(rows) == 2


def test_the_same_subject_with_different_answers_stays_apart():
    """Grouping is by (subject, suggested). Collapsing two different answers into one row
    would hide exactly the disagreement a reviewer is scanning for — the samtools/faidx
    case in the design's confirmable screen."""
    rows = aggregate([_q(suggested="alignment.bam"), _q(suggested="alignment.cram")])
    assert len(rows) == 2


def test_asked_by_is_sorted_so_the_row_is_stable():
    """Two runs must produce the same row. Workspace order is directory order, and
    directory order moves under a refactor nobody asked for."""
    a = aggregate([_q(draft="z"), _q(draft="a")])[0]
    b = aggregate([_q(draft="a"), _q(draft="z")])[0]
    assert a.asked_by == b.asked_by == ["a", "z"]


def test_aggregating_does_not_mutate_the_input():
    """A projection that edits its argument is a projection you cannot call twice."""
    one = _q(draft="a")
    aggregate([one, _q(draft="b")])
    assert one.asked_by == ["a"]

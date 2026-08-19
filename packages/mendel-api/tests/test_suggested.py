"""`suggested` had every consumer and no producer.

It crosses the API, is keyed on by `aggregate()`, sorted on by the queue's ordering, highlighted
by `Question.tsx`, and switches `QueueRow`'s label from *Ask* to *Confirm* — and every
`suggested=` in the repository was in a test, so the Confirm branch was unreachable and the
*Ask before Confirm* ordering its own comment describes was a no-op. This is the producer.
"""

from comeni_core.review import Candidate  # noqa: F401
from mendel_forge.scaffold import Hole

from mendel_api.questions import question_from_hole


def test_the_top_candidate_is_what_is_suggested() -> None:
    hole = Hole(
        subject="produces[0].type_id",
        what="the semantic type of the output the module emits as fa",
        why_open="the semantic type exists only in the English description",
        candidates=[Candidate(value="genome.fasta"), Candidate(value="alignment.bam")],
        suggested="genome.fasta",
    )
    assert question_from_hole(hole, draft="faidx").suggested == "genome.fasta"


def test_an_unfounded_hole_suggests_nothing_even_though_it_has_candidates() -> None:
    """**The defect this test exists to stop, watched happening.**

    `gzi`, `sizes` and `versions_samtools` are real ports of `samtools/faidx` whose names say
    nothing about a type, so every candidate scores 0 and the list falls back to alphabetical.
    Projecting `candidates[0]` regardless labelled those holes **Confirm** and offered
    `alignment.bai` — a screen that used to admit it was asking, inviting a person to accept the
    alphabet instead.
    """
    hole = Hole(
        subject="produces[3].type_id",
        what="the semantic type of the output the module emits as gzi",
        why_open="the semantic type exists only in the English description",
        candidates=[Candidate(value="alignment.bai"), Candidate(value="genome.fasta")],
    )
    assert question_from_hole(hole, draft="faidx").suggested is None


def test_a_hole_with_no_candidates_suggests_nothing() -> None:
    # Free text — `priority_because` is the live case. A suggestion there would be an invention,
    # which is the one thing the forge must never do (invariant 2).
    hole = Hole(
        subject="priority_because",
        what="why this ranks where it does",
        why_open="a judgement",
    )
    assert question_from_hole(hole, draft="faidx").suggested is None

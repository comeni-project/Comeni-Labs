"""Scoring a proposal against a contract a human already approved.

Every claim here is about the arithmetic, and the arithmetic is where an evaluation harness goes
wrong quietly: a metric that rewards declining, or one that punishes it, will be believed for as
long as nobody checks what it counts.
"""

from mendel_forge.ai.evaluate import Report, Score, score
from mendel_forge.ai.schemas import Analysis, Answer, Proposal, Unresolved
from mendel_forge.hole_manifest import HoleKind, ScaffoldHole


def _hole(hole_id, **overrides):
    base = {
        "id": hole_id,
        "pointer": "/consumes/0/type_id",
        "kind": HoleKind.TYPE,
        "question": "the semantic type",
        "why_open": "a suffix is not a type",
        "legal_values": ("fastq.reads", "alignment.bam"),
    }
    return ScaffoldHole(**{**base, **overrides})


def _proposal(answers=(), unresolved=()):
    return Proposal(analysis=Analysis(answers=answers, unresolved=unresolved))


def test_a_right_answer_counts_right_and_a_wrong_one_counts_wrong():
    result = score(
        _proposal(
            (
                Answer(hole_id="a", value="fastq.reads"),
                Answer(hole_id="b", value="fastq.reads"),
            )
        ),
        case="c",
        expected={"a": "fastq.reads", "b": "alignment.bam"},
        holes=[_hole("a"), _hole("b")],
    )
    assert (result.correct, result.wrong) == (1, 1)


def test_declining_is_neither_right_nor_wrong():
    """§5.9's last row — *unresolved weak-source case: expected, not failure* — is only
    expressible this way. Counting a decline as wrong makes the honest answer the worst one,
    and a model told that will stop giving it."""
    result = score(
        _proposal(unresolved=(Unresolved(hole_id="a", needed_evidence="the man page"),)),
        case="c",
        expected={"a": "fastq.reads"},
        holes=[_hole("a")],
    )
    assert (result.correct, result.wrong, result.declined) == (0, 0, 1)


def test_a_forgotten_hole_is_missing_and_that_is_a_failure():
    """A hole the model forgot is not a hole the model refused. Collapsing them would let a
    model score well by ignoring every question it found hard."""
    result = score(
        _proposal(), case="c", expected={"a": "fastq.reads"}, holes=[_hole("a")]
    )
    assert result.missing == 1
    assert result.declined == 0


def test_an_optional_hole_left_alone_is_not_missing():
    """`required` is a judgement the scaffold already made, and re-making it here would be a
    second opinion about what blocks."""
    result = score(
        _proposal(), case="c", expected={}, holes=[_hole("a", required=False)]
    )
    assert result.missing == 0


def test_an_answer_the_key_cannot_judge_is_unknown_rather_than_wrong():
    """The upstream module may have gained a port since the contract landed. Scoring that as
    wrong would make every corpus case decay as upstream moves, and the decay would read as the
    prompt getting worse."""
    result = score(
        _proposal((Answer(hole_id="new", value="qc.report"),)),
        case="c",
        expected={"a": "fastq.reads"},
        holes=[_hole("new")],
    )
    assert (result.unknown, result.wrong) == (1, 0)


def test_precision_is_none_rather_than_perfect_when_nothing_was_judged():
    """A model that declined everything has not achieved perfect precision. It has not been
    measured, and 1.0 is the number most likely to be quoted."""
    assert Score(case="c", declined=9).precision() is None
    assert "precision —" in Score(case="c", declined=9).summary()


def test_coverage_and_precision_are_both_printed():
    """**Either alone is trivially gamed by the opposite failure.** Declining everything gives
    perfect precision; guessing everything gives perfect coverage. A summary that printed one
    would be quoted, and the quote would be wrong in a direction nobody could see."""
    line = Score(case="c", correct=3, wrong=1, declined=2).summary()
    assert "precision 75%" in line
    assert "coverage 67%" in line
    assert "declined 2" in line


def test_an_invented_citation_is_collected_as_a_gate_failure():
    """§5.9 gates it at zero. On the live path `admit()` raises first — this counts what would
    have got through when the harness runs without the gate."""
    result = score(
        _proposal((Answer(hole_id="a", value="fastq.reads", evidence_ids=("E404",)),)),
        case="c",
        expected={"a": "fastq.reads"},
        holes=[_hole("a")],
        evidence_ids=frozenset({"E001"}),
    )
    assert result.invented_citations == ("E404",)
    assert Report(model="m", scores=(result,)).failures()


def test_an_answer_outside_a_closed_candidate_set_is_collected_too():
    result = score(
        _proposal((Answer(hole_id="a", value="fastq.invented"),)),
        case="c",
        expected={},
        holes=[_hole("a")],
    )
    assert result.outside_candidates == ("a",)


def test_overwriting_something_the_source_settled_is_a_gate_failure():
    """§5.9's *source fact mutation: 0*. A proposal that answers a hole the scaffold had already
    settled from the source is claiming to know better than the thing it was reading."""
    result = score(
        _proposal((Answer(hole_id="nf_process", value="WRONG_NAME"),)),
        case="c",
        expected={},
        holes=[_hole("nf_process", kind=HoleKind.NEXTFLOW, legal_values=())],
        settled={"nf_process": "FASTQC"},
    )
    assert result.mutated_facts == ("nf_process",)
    assert "overwrote nf_process" in Report(model="m", scores=(result,)).render()


def test_a_clean_run_says_so_rather_than_printing_nothing():
    """An empty failure list rendered as silence reads as *the report did not run*."""
    clean = Score(case="c", correct=4)
    assert "every zero-gate row is at zero" in Report(model="m", scores=(clean,)).render()


def test_precision_is_not_a_gate():
    """It is §5.9's *report per port* row with a floor of *must not regress the current measured
    baseline*, and there is no baseline yet. Gating on a number nobody has measured would be
    inventing the thing this harness exists to find."""
    poor = Score(case="c", correct=0, wrong=9)
    assert Report(model="m", scores=(poor,)).failures() == ()

"""A run-time setting's lookup as Groovy, from the closed tests and operations only (#217, #466)."""

import pytest
from comeni_core.plan.at_run import (
    AtRun,
    AtRunCondition,
    AtRunFact,
    AtRunFallback,
    AtRunOp,
    AtRunRow,
    AtRunSource,
    AtRunStep,
    AtRunTest,
)
from mendel_compiler.groovy_lookup import closure

STAR_CHAIN = [AtRunStep(op=AtRunOp.LOG2), AtRunStep(op=AtRunOp.DIVIDE, by=2),
              AtRunStep(op=AtRunOp.SUBTRACT, by=1), AtRunStep(op=AtRunOp.AT_MOST, by=14),
              AtRunStep(op=AtRunOp.ROUND)]


def _lookup(rows, fallback=None, facts=("strandedness",), kind=AtRunFallback.VALUE) -> AtRun:
    return AtRun(facts=[AtRunFact(measurement=f, meta_key=f, source=AtRunSource.MEASURED,
                                  measured_by="comeni/measure/x@1.0.0") for f in facts],
                 rule="param:quantification:strandedness", rows=rows, fallback=fallback,
                 fallback_reason="the default", fallback_is=kind)


def _on(fact, test, *operand) -> AtRunCondition:
    return AtRunCondition(fact=fact, test=test, operand=list(operand))


def test_rows_become_a_chain_ending_in_the_fallback():
    text = closure(_lookup([
        AtRunRow(when=[_on("strandedness", AtRunTest.EQ, "reverse")], then=2),
        AtRunRow(when=[_on("strandedness", AtRunTest.EQ, "forward")], then=1),
        AtRunRow(when=[_on("strandedness", AtRunTest.IN, "unstranded")], then=0),
    ], fallback=0))
    assert text == (
        "((meta.strandedness != null && meta.strandedness == 'reverse') ? 2 : "
        "((meta.strandedness != null && meta.strandedness == 'forward') ? 1 : "
        "((meta.strandedness != null && meta.strandedness in ['unstranded']) ? 0 : 0)))")


def test_a_row_over_two_facts_needs_both():
    text = closure(_lookup([AtRunRow(when=[_on("read_length", AtRunTest.GE, 70),
                                          _on("strandedness", AtRunTest.EQ, "reverse")],
                                     then=10)], fallback=0,
                           facts=("read_length", "strandedness")))
    assert text == (
        "(((meta.read_length instanceof Number) && (meta.read_length as double) >= 70.0) && "
        "(meta.strandedness != null && meta.strandedness == 'reverse') ? 10 : 0)")


def test_a_missing_value_passes_only_absent():
    """A blank cell or an undetermined measurement: `!=` must not match it, as `matches` has
    it (#466)."""
    text = closure(_lookup([AtRunRow(when=[_on("strandedness", AtRunTest.NE, "reverse")],
                                     then=1),
                            AtRunRow(when=[_on("strandedness", AtRunTest.ABSENT)], then=9)],
                           fallback=0))
    assert "(meta.strandedness != null && meta.strandedness != 'reverse') ? 1" in text
    assert "(meta.strandedness == null) ? 9" in text


def test_a_comparison_reads_the_fact_as_a_number():
    text = closure(_lookup([AtRunRow(when=[_on("read_length", AtRunTest.GE, 70.0)],
                                     then="star")],
                           fallback="hisat2", facts=("read_length",)))
    assert ("((meta.read_length instanceof Number) && (meta.read_length as double) >= 70.0) "
            "? 'star'") in text


def test_the_star_chain():
    text = closure(_lookup([AtRunRow(takes="genome_length", integer=True,
                                     transform=STAR_CHAIN)], facts=("genome_length",)))
    assert text.startswith("((meta.genome_length != null) ? ")
    assert "Math.rint(Math.min(" in text and "as long)" in text and "Math.log(2.0d)" in text
    assert text.endswith(" : null)")


def test_stop_names_the_sample():
    text = closure(_lookup([AtRunRow(when=[_on("strandedness", AtRunTest.EQ, "reverse")],
                                     then=2)], kind=AtRunFallback.STOP))
    assert "throw new IllegalStateException('sample ' + meta.id + ': " in text
    assert "no row of param:quantification:strandedness applies to its strandedness" in text


def test_a_literal_outside_the_substitutable_class_is_refused():
    with pytest.raises(ValueError, match="MD0201"):
        closure(_lookup([AtRunRow(then="x; rm -rf /")]))
    with pytest.raises(ValueError, match="MD0201"):
        closure(_lookup([AtRunRow(when=[_on("strandedness", AtRunTest.EQ, "a'b")], then=1)]))


def test_numbers_compare_as_doubles_whatever_json_made_them():
    """`70.0 in [70]` is false in Groovy and true in Python (Task 7 review)."""
    text = closure(_lookup([AtRunRow(when=[_on("read_length", AtRunTest.IN, 70, 75.5)],
                                     then="x")], fallback="y", facts=("read_length",)))
    assert "[70.0, 75.5].any { it == (meta.read_length as double) }" in text


def test_a_chain_ending_in_round_is_a_whole_number():
    text = closure(_lookup([AtRunRow(takes="x", integer=False,
                                     transform=[AtRunStep(op=AtRunOp.ROUND)])], facts=("x",)))
    assert text.endswith("as long) : null)")


def test_a_non_finite_literal_is_refused():
    with pytest.raises(ValueError, match="MD0201"):
        closure(_lookup([AtRunRow(then=float("inf"))]))

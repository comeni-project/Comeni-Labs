"""A run-time setting's lookup as Groovy, from the closed tests and operations only (#217)."""

import pytest
from comeni_core.plan.at_run import AtRun, AtRunOp, AtRunRow, AtRunStep, AtRunTest
from mendel_compiler.groovy_lookup import closure

STAR_CHAIN = [AtRunStep(op=AtRunOp.LOG2), AtRunStep(op=AtRunOp.DIVIDE, by=2),
              AtRunStep(op=AtRunOp.SUBTRACT, by=1), AtRunStep(op=AtRunOp.AT_MOST, by=14),
              AtRunStep(op=AtRunOp.ROUND)]


def _lookup(rows, fallback=None, fact="strandedness") -> AtRun:
    return AtRun(fact=fact, meta_key=fact, measured_by="comeni/measure/x@1.0.0",
                 rule="param:quantification:strandedness", rows=rows, fallback=fallback,
                 fallback_reason="the default")


def test_rows_become_a_chain_ending_in_the_fallback():
    text = closure(_lookup([
        AtRunRow(test=AtRunTest.EQ, operand=["reverse"], then=2),
        AtRunRow(test=AtRunTest.EQ, operand=["forward"], then=1),
        AtRunRow(test=AtRunTest.IN, operand=["unstranded"], then=0),
    ], fallback=0))
    assert text == (
        "(meta.strandedness == null ? 0 : ((meta.strandedness == 'reverse') ? 2 : "
        "((meta.strandedness == 'forward') ? 1 : ((meta.strandedness in ['unstranded']) ? 0 "
        ": 0))))")


def test_a_comparison_reads_the_fact_as_a_number():
    text = closure(_lookup([AtRunRow(test=AtRunTest.GE, operand=[70.0], then="star")],
                           fallback="hisat2", fact="read_length"))
    assert "((meta.read_length as double) >= 70.0) ? 'star'" in text


def test_the_star_chain():
    text = closure(_lookup([AtRunRow(test=AtRunTest.ANY, takes_fact=True, integer=True,
                                     transform=STAR_CHAIN)], fact="genome_length"))
    assert text.startswith("(meta.genome_length == null ? null : (true ? ")
    assert "Math.rint(Math.min(" in text and "as long)" in text and "Math.log(2.0d)" in text


def test_a_literal_outside_the_substitutable_class_is_refused():
    with pytest.raises(ValueError, match="MD0201"):
        closure(_lookup([AtRunRow(test=AtRunTest.ANY, then="x; rm -rf /")]))
    with pytest.raises(ValueError, match="MD0201"):
        closure(_lookup([AtRunRow(test=AtRunTest.EQ, operand=["a'b"], then=1)]))

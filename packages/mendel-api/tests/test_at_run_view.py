"""A run-time setting as the step card shows it before the run (#217)."""

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
from mendel_api.services.build import at_run_view


def _fact(name, source=AtRunSource.MEASURED):
    return AtRunFact(measurement=name, meta_key=name, source=source,
                     measured_by=None if source is AtRunSource.CELL
                     else "comeni/measure/genome_length_fai@1.0.0")


def test_rows_read_as_lines_and_the_chain_is_spelled_out():
    view = at_run_view(AtRun(
        facts=[_fact("genome_length")], rule="param:index_building:sa_index_nbases",
        rows=[AtRunRow(takes="genome_length", integer=True, transform=[
            AtRunStep(op=AtRunOp.LOG2), AtRunStep(op=AtRunOp.DIVIDE, by=2),
            AtRunStep(op=AtRunOp.SUBTRACT, by=1), AtRunStep(op=AtRunOp.AT_MOST, by=14),
            AtRunStep(op=AtRunOp.ROUND)])],
        fallback=None, fallback_reason="asked"))
    assert view.rows == [
        "any sample → genome_length → log2 → ÷ 2 → − 1 → at most 14 → round"]
    assert view.fallback is None
    (fact,) = view.facts
    assert (fact.fact, fact.said) == ("genome_length", "measured in the run")


def test_a_table_reads_row_by_row():
    view = at_run_view(AtRun(
        facts=[_fact("read_length", AtRunSource.CELL_OR_MEASURED),
               _fact("strandedness", AtRunSource.CELL)],
        rule="param:quantification:min_mqs",
        rows=[AtRunRow(when=[AtRunCondition(fact="read_length", test=AtRunTest.GE,
                                            operand=[70.0]),
                             AtRunCondition(fact="strandedness", test=AtRunTest.EQ,
                                            operand=["reverse"])], then=10),
              AtRunRow(when=[AtRunCondition(fact="strandedness", test=AtRunTest.ABSENT)],
                       then=1)],
        fallback=None, fallback_reason="a person", fallback_is=AtRunFallback.STOP))
    assert view.rows == ["read_length >= 70 and strandedness is reverse → 10",
                         "strandedness is not known → 1"]
    assert [f.said for f in view.facts] == [
        "from the samplesheet, measured in the run where left blank", "from the samplesheet"]
    assert view.fallback_is == "stop"


def test_a_fact_is_left_unasked_only_when_this_goal_can_measure_it():
    """Final review: no genome among the inputs, nothing measures its length, so it is asked."""
    from mendel_api.services import gaps, registry

    stack = registry.stack()
    decisions = gaps._premise_measurements(stack)["genome_length"]
    assert gaps._decided_in_the_run(stack, "genome_length", decisions, {"genome.fasta"})
    assert not gaps._decided_in_the_run(stack, "genome_length", decisions, {"fastq.reads"})

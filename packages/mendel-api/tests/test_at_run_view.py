"""A run-time setting as the step card shows it before the run (#217)."""

from comeni_core.plan.at_run import AtRun, AtRunOp, AtRunRow, AtRunStep, AtRunTest
from mendel_api.services.build import at_run_view


def test_rows_read_as_lines_and_the_chain_is_spelled_out():
    view = at_run_view(AtRun(
        fact="genome_length", meta_key="genome_length",
        measured_by="comeni/measure/genome_length_fai@1.0.0",
        rule="param:index_building:sa_index_nbases",
        rows=[AtRunRow(test=AtRunTest.ANY, takes_fact=True, integer=True, transform=[
            AtRunStep(op=AtRunOp.LOG2), AtRunStep(op=AtRunOp.DIVIDE, by=2),
            AtRunStep(op=AtRunOp.SUBTRACT, by=1), AtRunStep(op=AtRunOp.AT_MOST, by=14),
            AtRunStep(op=AtRunOp.ROUND)])],
        fallback=None, fallback_reason="asked"))
    assert view.rows == [
        "any genome_length → genome_length → log2 → ÷ 2 → − 1 → at most 14 → round"]
    assert view.fallback is None


def test_a_table_reads_row_by_row():
    view = at_run_view(AtRun(
        fact="strandedness", meta_key="strandedness", measured_by="comeni/measure/x@1.0.0",
        rule="param:quantification:strandedness",
        rows=[AtRunRow(test=AtRunTest.EQ, operand=["reverse"], then=2),
              AtRunRow(test=AtRunTest.GE, operand=[70.0], then=1)],
        fallback=0, fallback_reason="the default"))
    assert view.rows == ["strandedness is reverse → 2", "strandedness >= 70 → 1"]
    assert view.fallback == "0"

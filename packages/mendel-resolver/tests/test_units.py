"""An input may span several rows per sample, such as a sample's lanes; its merging step is
placed before anything reads it (#466, stage 5)."""

import pytest
from mendel_resolver import layers
from mendel_resolver.goal import Goal
from mendel_resolver.resolve import resolve
from support.paths import ROOT

CAT = "nf-core/cat/fastq@9.5"


def _stack(*extra):
    return layers.load([ROOT / "registry", *extra])


def _resolved(stack, units=(), have=("fastq.reads", "genome.fasta", "annotation.gtf"),
              want="counts.matrix"):
    goal = Goal.model_validate({
        "have": [{"type_id": t} for t in have], "want": [want],
        "constraints": {"units": list(units)},
        "profile": stack.measurements.profile({"read_length": 150}).model_dump(mode="json")})
    return resolve(goal, stack.routing, stack.rules, stack.measurements,
                   vocabulary=stack.vocabulary)


def test_lanes_are_merged_before_anything_reads_the_reads():
    ir = _resolved(_stack(), units=["fastq.reads"])
    merge = next(n for n in ir.nodes if n.contract_id == CAT)
    assert merge.id == "merge_fastq_reads"
    assert "a sample may span several rows of fastq.reads" in merge.presence.reason
    into = {(e.from_node, e.to_node, e.to_port) for e in ir.edges}
    assert ("merge_fastq_reads", "trimgalore", "reads") in into
    order = [n.id for n in ir.nodes]
    assert order.index("merge_fastq_reads") < order.index("trimgalore")


def test_without_units_the_pipeline_is_todays():
    stack = _stack()
    plain = _resolved(stack)
    assert CAT not in {n.contract_id for n in plain.nodes}


def test_units_on_a_study_input_are_refused():
    with pytest.raises(ValueError, match="MD0340"):
        _resolved(_stack(), units=["genome.fasta"])


def test_units_on_an_input_the_goal_does_not_have_are_refused():
    with pytest.raises(ValueError, match="MD0340"):
        _resolved(_stack(), units=["alignment.bam"])


def test_a_type_with_no_merger_is_refused():
    with pytest.raises(ValueError, match="MD0341"):
        _resolved(_stack(), units=["alignment.bam"], have=("alignment.bam", "annotation.gtf"))


def test_lanes_beside_another_per_sample_input_are_refused():
    """Final review I3: the other input would be read once per lane."""
    with pytest.raises(ValueError, match="MD0340"):
        _resolved(_stack(), units=["fastq.reads"],
                  have=("fastq.reads", "alignment.bam", "annotation.gtf"))

"""The gap engine: what an analysis still needs, computed from the registry, not by a model."""

from mendel_api.authoring.types import Fact, FactKind, FactSource
from mendel_api.services import gaps as g
from mendel_api.services import registry


def _kinds(result):
    return [(gap.kind.value, gap.subject) for gap in result]


def test_gene_counts_needs_reads_a_genome_an_annotation_and_the_facts_rules_read():
    result = g.gaps(["counts.matrix"], [], registry.stack())
    got = _kinds(result)
    inputs = [s for k, s in got if k == "input"]
    measurements = [s for k, s in got if k == "measurement"]
    assert set(inputs) == {"fastq.reads", "genome.fasta", "annotation.gtf"}
    assert {"read_length", "paired", "strandedness"} <= set(measurements)
    # inputs first, then measurements
    assert got.index(("input", inputs[-1])) < got.index(("measurement", measurements[0]))


def test_a_fact_removes_its_gap_and_an_open_one_is_not_asked_again():
    facts = [
        Fact(kind=FactKind.INPUT, subject="genome.fasta", source=FactSource.PERSON_SAID),
        Fact(kind=FactKind.MEASUREMENT, subject="read_length", source=FactSource.OPEN),
    ]
    subjects = {gap.subject for gap in g.gaps(["counts.matrix"], facts, registry.stack())}
    assert "genome.fasta" not in subjects and "read_length" not in subjects
    assert "annotation.gtf" in subjects


def test_a_want_nothing_can_make_is_unreachable_not_an_empty_list():
    """Review focus 1: an empty list would send an unbuildable goal to the card."""
    result = g.gaps(["no.such.type"], [], registry.stack())
    assert result == g.Unreachable("no.such.type")


def _by_subject(result):
    return {gap.subject: gap for gap in result}


def test_an_input_names_every_candidate_step_that_reads_it():
    """Part I.1 §4: who reads an input, from the walk itself."""
    found = _by_subject(g.gaps(["counts.matrix"], [], registry.stack()))
    readers = found["annotation.gtf"].used_by
    assert readers, "nothing reads the annotation — the walk recorded nothing"
    assert len(readers) == len(set(readers))
    assert any("featurecounts" in c for c in readers)


def test_a_premise_measurement_names_the_rule_that_reads_it():
    found = _by_subject(g.gaps(["counts.matrix"], [], registry.stack()))
    decides = found["read_length"].decides
    assert [d.because for d in decides] == ["read length determines which aligner is appropriate"]
    assert decides[0].cite.startswith("Dobin et al. 2013")


def test_a_carried_measurement_names_the_steps_that_read_its_type():
    found = _by_subject(g.gaps(["counts.matrix"], [], registry.stack()))
    assert found["paired"].used_by == found["fastq.reads"].used_by
    assert found["paired"].decides == ()


def test_the_same_want_gives_the_same_context_in_the_same_order():
    first = g.gaps(["counts.matrix"], [], registry.stack())
    assert first == g.gaps(["counts.matrix"], [], registry.stack())


def test_a_measurement_two_rules_read_lists_both_in_table_order():
    """Review Focus 5."""
    stack = registry.stack()
    decision = next(d for d in stack.rules.decisions if d.because and "read length" in d.because)
    second = decision.model_copy(update={"because": "a second reason"})
    rules = stack.rules.model_copy(update={"decisions": [*stack.rules.decisions, second]})
    found = _by_subject(g.gaps(["counts.matrix"], [], stack.model_copy(update={"rules": rules})))
    assert [d.because for d in found["read_length"].decides] == [
        "read length determines which aligner is appropriate", "a second reason"]

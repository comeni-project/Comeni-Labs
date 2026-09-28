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

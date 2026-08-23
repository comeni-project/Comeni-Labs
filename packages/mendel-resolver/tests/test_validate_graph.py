"""The checks that are about the graph rather than about one wire.

`stack` comes from the conftest.
"""

from comeni_core.plan.draft import DraftEdge, DraftGraph, DraftNode
from comeni_core.review.verdict import Level
from mendel_resolver.validate import validate

STAR = "nf-core/star/align@1.11.0"
SORT = "nf-core/samtools/sort@1.21.0"
COUNTS = "nf-core/subread/featurecounts@2.0.6"


def test_an_input_fed_by_an_entry_channel_is_not_unmet(stack):
    """**The defect 3C shipped and caught.**

    `star/align` consumes a GTF that arrives from `params.gtf` and has no incoming edge. A
    check reading only edges drew a hollow *unmet* dot on a satisfied input. `annotation.gtf`
    declares an `entry_channel` in the vocabulary, and that is what makes it met.
    """
    graph = DraftGraph(nodes=[DraftNode(id="align", contract_id=STAR)])
    unmet = [f for f in validate(graph, stack).findings if f.code == "MD0506"]
    assert "gtf" not in {f.port for f in unmet}, [f.message for f in unmet]
    assert "reads" not in {f.port for f in unmet}, "fastq.reads is an entry channel too"


def test_an_input_with_no_entry_channel_is_unmet(stack):
    """`star/align.index` takes `genome.index.star`, which no type declares an entry channel
    for — it is built by `star/genomegenerate` and must be wired."""
    graph = DraftGraph(nodes=[DraftNode(id="align", contract_id=STAR)])
    unmet = [f for f in validate(graph, stack).findings if f.code == "MD0506"]
    assert "index" in {f.port for f in unmet}
    assert all(f.level is Level.UNMET for f in unmet)


def test_unmet_is_not_illegal(stack):
    """A half-drawn graph is a legal thing to be holding. `keep` refuses it; `validate` does
    not."""
    graph = DraftGraph(nodes=[DraftNode(id="counts", contract_id=COUNTS)])
    verdict = validate(graph, stack)
    assert verdict.illegal == []
    assert verdict.emittable is True


def test_a_cycle_is_reported_with_its_nodes_in_order(stack):
    """`SAMTOOLS_SORT` consumes and produces `alignment.bam`, so it is a candidate for its own
    dependency. Routing excludes the node itself and cannot draw this; a person can."""
    graph = DraftGraph(
        nodes=[DraftNode(id="a", contract_id=SORT), DraftNode(id="b", contract_id=SORT)],
        edges=[
            DraftEdge(from_node="a", from_port="bam", to_node="b", to_port="bam"),
            DraftEdge(from_node="b", from_port="bam", to_node="a", to_port="bam"),
        ],
    )
    cycles = [f for f in validate(graph, stack).findings if f.code == "MD0508"]
    assert cycles and cycles[0].level is Level.ILLEGAL
    assert "a" in cycles[0].message and "b" in cycles[0].message


def test_a_self_loop_is_a_cycle(stack):
    graph = DraftGraph(
        nodes=[DraftNode(id="a", contract_id=SORT)],
        edges=[DraftEdge(from_node="a", from_port="bam", to_node="a", to_port="bam")],
    )
    assert "MD0508" in {f.code for f in validate(graph, stack).findings}


def test_a_cycle_is_reported_once_not_once_per_traversal(stack):
    graph = DraftGraph(
        nodes=[DraftNode(id="a", contract_id=SORT), DraftNode(id="b", contract_id=SORT)],
        edges=[
            DraftEdge(from_node="a", from_port="bam", to_node="b", to_port="bam"),
            DraftEdge(from_node="b", from_port="bam", to_node="a", to_port="bam"),
        ],
    )
    codes = [f.code for f in validate(graph, stack).findings]
    assert codes.count("MD0508") == 1


def test_two_wires_into_a_port_that_takes_one(stack):
    graph = DraftGraph(
        nodes=[
            DraftNode(id="x", contract_id=STAR),
            DraftNode(id="y", contract_id=STAR),
            DraftNode(id="sort", contract_id=SORT),
        ],
        edges=[
            DraftEdge(from_node="x", from_port="bam", to_node="sort", to_port="bam"),
            DraftEdge(from_node="y", from_port="bam", to_node="sort", to_port="bam"),
        ],
    )
    arity = [f for f in validate(graph, stack).findings if f.code == "MD0505"]
    assert arity and arity[0].level is Level.ILLEGAL


def test_the_verdict_is_deterministic(stack):
    """Invariant 10's habit applied to a check: same graph in, same findings out, in order."""
    graph = DraftGraph(
        nodes=[DraftNode(id="align", contract_id=STAR), DraftNode(id="counts", contract_id=COUNTS)],
        edges=[DraftEdge(from_node="align", from_port="bam", to_node="counts", to_port="bam")],
    )
    first = validate(graph, stack).model_dump()
    again = validate(graph, stack).model_dump()
    assert first == again

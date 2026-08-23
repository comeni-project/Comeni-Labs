"""The index is an optimisation of `validate`'s answer, never a second opinion.

The last test is the one that matters: it runs both over the whole registry and asserts they
never disagree. If someone changes the verb and forgets the index, that fails here rather than
lighting up a wire in the browser that the server will later refuse.

`stack` comes from the conftest.
"""

from comeni_core.plan.draft import DraftEdge, DraftGraph, DraftNode
from mendel_resolver.compatibility import index, signature
from mendel_resolver.validate import validate

STAR = "nf-core/star/align@1.11.0"
SORT = "nf-core/samtools/sort@1.21.0"
COUNTS = "nf-core/subread/featurecounts@2.0.6"


def test_a_signature_sorts_its_states():
    assert signature("alignment.bam", frozenset()) == "alignment.bam"
    assert (
        signature("alignment.bam", frozenset({"indexed", "coordinate_sorted"}))
        == "alignment.bam[coordinate_sorted,indexed]"
    )


def test_an_unsorted_bam_does_not_satisfy_featurecounts(stack):
    idx = index(stack)
    star = idx.emits[f"{STAR}#bam"]
    counts = idx.requires[f"{COUNTS}#bam"]
    assert not set(counts) & set(idx.satisfies[star])


def test_a_sorted_bam_does(stack):
    idx = index(stack)
    sorted_bam = idx.emits[f"{SORT}#bam"]
    counts = idx.requires[f"{COUNTS}#bam"]
    assert set(counts) & set(idx.satisfies[sorted_bam])


def test_every_input_port_has_at_least_one_requirement(stack):
    """`_one_form` refuses a port declaring neither `type_id` nor `accepts`, so an empty list
    here would mean `alternatives()` had changed under us."""
    idx = index(stack)
    for key, requirements in idx.requires.items():
        assert requirements, key
        assert len(requirements) == len(set(requirements)), key


def test_the_conventional_alternative_is_first(stack):
    """The client renders green for a match on index 0 and amber for a later one; the ORDER
    carries that and nothing else does."""
    idx = index(stack)
    # star/align.reads declares state_required_conventional: [trimmed], so the conventional
    # form is the trimmed one and the bare form is the fallback.
    assert idx.requires[f"{STAR}#reads"] == ["fastq.reads[trimmed]", "fastq.reads"]


def test_the_index_agrees_with_the_verb_on_every_pair(stack):
    """**The guarantee. One rule, one answer.**

    Every output port against every input port in the registry: the index's verdict and
    `validate`'s must match. The loop is quadratic on purpose — the point is exhaustiveness.
    """
    idx = index(stack)
    contracts = stack.registry.all()
    disagreements = []
    for source in contracts:
        for out in source.produces:
            emitted = idx.emits[f"{source.id}#{out.name}"]
            for target in contracts:
                for inp in target.consumes:
                    accepted = idx.requires[f"{target.id}#{inp.name}"]
                    index_says = bool(set(accepted) & set(idx.satisfies.get(emitted, [])))

                    graph = DraftGraph(
                        nodes=[
                            DraftNode(id="a", contract_id=source.id),
                            DraftNode(id="b", contract_id=target.id),
                        ],
                        edges=[
                            DraftEdge(
                                from_node="a", from_port=out.name, to_node="b", to_port=inp.name
                            )
                        ],
                    )
                    verb_says = not [
                        f
                        for f in validate(graph, stack).illegal
                        if f.code in {"MD0503", "MD0504"}
                    ]
                    if index_says != verb_says:
                        disagreements.append(
                            f"{source.id}#{out.name} -> {target.id}#{inp.name}: "
                            f"index={index_says} verb={verb_says}"
                        )
    assert not disagreements, "\n".join(disagreements)

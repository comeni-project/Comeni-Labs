"""Derive a goal and evidenced pipeline IR from a hand-drawn graph."""

from comeni_core.plan.draft import DraftEdge, DraftGraph, DraftNode
from comeni_core.plan.tiers import Tier, ValueSource
from mendel_resolver.materialise import goal_of, ir_of

STAR = "nf-core/star/align@2.7.11b"
SORT = "nf-core/samtools/sort@1.24"
COUNTS = "nf-core/subread/featurecounts@2.1.1"
GENOME = "nf-core/star/genomegenerate@2.7.11b"


def _spine() -> DraftGraph:
    """The RNA-seq spine, drawn by hand rather than resolved."""
    return DraftGraph(
        nodes=[
            DraftNode(id="index", contract_id=GENOME),
            DraftNode(id="align", contract_id=STAR),
            DraftNode(id="sort", contract_id=SORT),
            DraftNode(id="counts", contract_id=COUNTS),
        ],
        edges=[
            DraftEdge(from_node="index", from_port="index", to_node="align", to_port="index"),
            DraftEdge(from_node="align", from_port="bam", to_node="sort", to_port="bam"),
            DraftEdge(from_node="sort", from_port="bam", to_node="counts", to_port="bam"),
        ],
    )


def test_the_goal_wants_what_the_terminal_nodes_produce(stack):
    """`counts` feeds nothing, so `counts.matrix` is what this graph is for."""
    goal = goal_of(_spine(), stack)
    assert "counts.matrix" in goal.want


def test_the_goal_has_what_the_entry_channels_supply(stack):
    """`fastq.reads`, `annotation.gtf` and `genome.fasta` declare entry channels; they arrive
    from `params` and are therefore what the person already has."""
    goal = goal_of(_spine(), stack)
    have = {i.type_id for i in goal.have}
    assert {"fastq.reads", "annotation.gtf", "genome.fasta"} <= have


def test_an_intermediate_output_is_not_wanted(stack):
    """`align.bam` feeds the sorter. Wanting it would make every step a terminal one and the
    derived goal meaningless."""
    goal = goal_of(_spine(), stack)
    assert "alignment.bam" not in goal.want


def test_an_edge_gets_its_type_from_the_source_port(stack):
    """A `DraftEdge` states four names; an `IREdge` needs the type and states too. They are
    read off the producing port, which is the only place they can honestly come from."""
    ir = ir_of(_spine(), stack)
    wire = next(e for e in ir.edges if e.from_node == "sort")
    assert wire.type_id == "alignment.bam"
    assert wire.states == frozenset({"coordinate_sorted"})


def test_every_node_is_tier_four_and_says_a_person_chose_it(stack):
    """**The honesty mechanism, applied to the builder.** Nothing about a drawn graph was
    resolved, so nothing may claim a lower tier. Tier 4 is always flagged (invariant 6)."""
    ir = ir_of(_spine(), stack)
    assert ir.nodes, "an empty IR claims no tier at all — that is not the same as tier 4"
    for node in ir.nodes:
        assert node.selection.tier is Tier.AMBIGUOUS
        assert node.selection.source is ValueSource.HUMAN


def test_a_drawn_choice_is_recorded_as_a_human_override(stack):
    """`ProducerDecision.human_override` already exists for exactly this, since Plan 1.10.
    Without it `mendel upgrade` would replace the drawn choice with whatever it resolves."""
    ir = ir_of(_spine(), stack)
    producers = [d for d in ir.decisions if d.kind == "producer"]
    assert producers, "a drawn graph is all producer choices; recording none loses them"
    assert all(d.human_override is not None for d in producers)


def test_a_model_drawn_graph_says_so(stack):
    """Task 5's whole point. `by` names the model and the override lands in `model_override`,
    so a reviewer can see which steps an agent chose."""
    ir = ir_of(_spine(), stack, by="claude-opus-5")
    producers = [d for d in ir.decisions if d.kind == "producer"]
    assert all(d.human_override is None for d in producers)
    assert all(d.model_override is not None for d in producers)
    assert all(d.model_override_by == "claude-opus-5" for d in producers)
    assert all(n.selection.source is ValueSource.MODEL for n in ir.nodes)


def test_it_is_deterministic(stack):
    """Invariant 10 applies here too: same drawing in, same IR out."""
    assert ir_of(_spine(), stack).model_dump() == ir_of(_spine(), stack).model_dump()


def test_a_drawn_graph_becomes_a_real_pipeline(stack):
    """**The assertion spec §6 actually makes.** Everything above tests a part; this tests that
    the parts compose into the artifact — `Pipeline.of` is the only validating constructor and
    it refuses a great deal.
    """
    from comeni_core.artifact.pipeline import Pipeline

    graph = _spine()
    pipeline = Pipeline.of(
        ir_of(graph, stack),
        stack.registry,
        stack.vocabulary,
        stack.measurements,
        stack.paths,
        goal=goal_of(graph, stack),
    )
    assert len(pipeline.steps) == 4
    assert pipeline.goal.want == ["counts.matrix"]
    assert {i.type_id for i in pipeline.goal.have} == {
        "annotation.gtf",
        "fastq.reads",
        "genome.fasta",
    }


FAIDX = "nf-core/samtools/faidx@1.24"


def _faidx_alone() -> DraftGraph:
    return DraftGraph(nodes=[DraftNode(id="faidx", contract_id=FAIDX)])


def test_a_drawn_optional_input_nothing_feeds_is_off(stack):
    """A step built in the conversation is materialised from its drawing (issue 496). Without
    a record for each optional input, the emitter took them all as on, and faidx's own `fai`
    became a `params.fai` the run demanded: the very index this step makes."""
    ir = ir_of(_faidx_alone(), stack)
    faidx = next(n for n in ir.nodes if n.id == "faidx")
    assert faidx.inputs
    assert {(r.port, r.state.value) for r in faidx.inputs} == {("fai", "off")}


def test_a_persons_choice_for_a_drawn_optional_input_is_kept(stack):
    """The confirmed goal carries the person's switch; the drawing alone cannot say it."""
    from comeni_core.goal.asked import InputChoice
    from comeni_core.plan.ir import InputState

    goal = goal_of(_faidx_alone(), stack)
    goal = goal.model_copy(update={"constraints": goal.constraints.model_copy(update={
        "inputs": [InputChoice(contract=FAIDX, port="fai", state=InputState.REQUIRED)]})})
    ir = ir_of(_faidx_alone(), stack, goal=goal)
    faidx = next(n for n in ir.nodes if n.id == "faidx")
    assert [(r.port, r.state) for r in faidx.inputs] == [("fai", InputState.REQUIRED)]

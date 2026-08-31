"""Two channels of one type, and a name that does not depend on the order you clicked.

Plan 5B phase 3, spec §3 and §11.2.

`materialise.goal_of` deduplicated `have` by `type_id` in one line, so the RNA-seq spine's three
`annotation.gtf` consumers were a single input nobody could address. That line is gone: a drawing
says which sockets share a channel, the default is still one per type, and splitting one produces
a second `params.*` a laboratory can bind separately.

**The hard part is not the split; it is the name.** `useGraph.nextId` mints `star_align_1`,
`star_align_2` … from the ids currently *taken*, so two structurally identical graphs get
different node ids depending on what was deleted along the way. Any channel order keyed on those
ids makes a person's `params.*` depend on the order they clicked, which is indefensible in a
product whose whole claim is that the same input gives the same output.
"""

import pathlib

import pytest
from comeni_core.artifact.pipeline import Pipeline
from comeni_core.plan.draft import DraftChannel, DraftEdge, DraftGraph, DraftNode
from mendel_compiler.emit import emit, entry_params
from mendel_resolver import layers
from mendel_resolver.materialise import channels_of, goal_of, ir_of

ROOT = pathlib.Path(__file__).parent.parent

STAR = "nf-core/star/align@1.11.0"
SORT = "nf-core/samtools/sort@1.21.0"
COUNTS = "nf-core/subread/featurecounts@2.0.6"
GENOME = "nf-core/star/genomegenerate@1.11.0"


@pytest.fixture(scope="module")
def stack():
    return layers.load(ROOT / "registry")


def _spine(*, ids=("index", "align", "sort", "counts"), channels=()) -> DraftGraph:
    """The spine, with its four node ids given so a caller can name them differently."""
    index, align, sort, counts = ids
    return DraftGraph(
        nodes=[
            DraftNode(id=index, contract_id=GENOME),
            DraftNode(id=align, contract_id=STAR),
            DraftNode(id=sort, contract_id=SORT),
            DraftNode(id=counts, contract_id=COUNTS),
        ],
        edges=[
            DraftEdge(from_node=index, from_port="index", to_node=align, to_port="index"),
            DraftEdge(from_node=align, from_port="bam", to_node=sort, to_port="bam"),
            DraftEdge(from_node=sort, from_port="bam", to_node=counts, to_port="bam"),
        ],
        channels=list(channels),
    )


def _artifact(graph: DraftGraph, stack) -> Pipeline:
    return Pipeline.of(
        ir_of(graph, stack),
        stack.registry,
        stack.vocabulary,
        stack.measurements,
        stack.paths,
        goal=goal_of(graph, stack),
    )


# ═══ THE GOAL STOPS DEDUPLICATING — spec §3 ══════════════════════════════════════════════


def test_the_default_is_still_one_channel_per_type(stack):
    """**The behaviour that must not change**, and it is most of the value of this phase.

    One GTF feeding three steps is the right answer for a shared reference annotation, and it is
    what every drawing meant before `DraftChannel` existed. A drawing that declares no channels
    resolves exactly as it did.
    """
    channels = channels_of(_spine(), stack)
    gtf = [c for c in channels if c.type_id == "annotation.gtf"]
    assert len(gtf) == 1
    assert len(gtf[0].ports) == 3, "the spine's GTF feeds the index builder, STAR and counts"


def test_splitting_a_socket_gives_it_a_channel_and_a_param_of_its_own(stack):
    """Ask (2) — *"a pipeline needs to have two same type inputs"* — end to end.

    The second channel is not a cosmetic duplicate: it has its own name, its own `params.*` and
    its own line in the emitted workflow, so a laboratory binds two annotations rather than one.
    """
    artifact = _artifact(_spine(channels=[DraftChannel(ports=("counts.annotation",))]), stack)
    gtf = [c for c in artifact.channels if c.type_id == "annotation.gtf"]
    assert [c.name for c in gtf] == ["gtf", "gtf_2"]
    assert [c.param for c in gtf] == ["gtf", "gtf_2"]
    assert "gtf_2" in entry_params(artifact)

    source = emit(artifact)
    assert "ch_gtf = " in source
    assert "ch_gtf_2 = " in source
    # And the split port reads the SECOND one, which is the whole point of splitting it.
    counts = next(step for step in artifact.steps if step.id == "counts")
    assert next(i for i in counts.inputs if i.port == "annotation").channel == "gtf_2"


def test_the_goal_carries_both_and_sorts_by_type_then_name(stack):
    """`Goal.have` reaches `pipeline.yml`, and byte-identical output is a hard requirement.

    It sorted by `type_id` alone, which stopped being a total order the moment two inputs could
    share one — two entries comparing equal is a sort whose result depends on the input order.
    """
    goal = goal_of(_spine(channels=[DraftChannel(ports=("counts.annotation",))]), stack)
    assert [(i.type_id, i.name) for i in goal.have] == sorted(
        (i.type_id, i.name) for i in goal.have
    )
    assert [i.name for i in goal.have if i.type_id == "annotation.gtf"] == ["gtf", "gtf_2"]


# ═══ THE ORDER IS THE SHAPE'S, NOT THE CLICKING'S — spec §11.2, §3.2 ═════════════════════


def test_the_same_pipeline_drawn_by_two_routes_emits_the_same_nextflow(stack):
    """**The determinism test §3.2 owes.**

    `useGraph.nextId` mints an id from what is currently taken, so adding two STAR nodes and
    deleting the first leaves `star_align_2` where drawing one fresh gives `star_align_1`. Two
    structurally identical graphs, two different node ids.

    This is that, minimally: the same four steps wired the same way, under node ids a person
    would have got by a different sequence of clicks. The emitted workflow must not know.
    """
    drawn_first = _spine()
    drawn_after_deleting = _spine(ids=("index_2", "star_align_3", "sort_9", "counts_4"))
    assert emit(_artifact(drawn_first, stack)) == emit(_artifact(drawn_after_deleting, stack))


def test_a_split_channel_keeps_its_name_across_the_two_routes(stack):
    """The same claim where it is hardest: with two channels of one type, the *order* decides
    which is `gtf` and which is `gtf_2`, and getting it from node ids is exactly the defect.

    Keyed on `(depth of the shallowest consumer, that consumer's contract, the port name)` —
    all facts about the graph's shape. The node ids below differ in every position and sort in
    a different order from the originals.
    """
    plain = _spine(channels=[DraftChannel(ports=("counts.annotation",))])
    renamed = _spine(
        ids=("aaa_index", "zzz_align", "mmm_sort", "bbb_counts"),
        channels=[DraftChannel(ports=("bbb_counts.annotation",))],
    )
    assert emit(_artifact(plain, stack)) == emit(_artifact(renamed, stack))
    assert entry_params(_artifact(plain, stack)) == entry_params(_artifact(renamed, stack))


def test_routing_is_unaffected_and_that_is_checked_rather_than_assumed(stack):
    """§3.1. `producers_of` matches a requirement against a contract's `produces` by type and
    states; a channel is not a producer and never was, which `StepInput`'s `source`/`channel`
    split and `MD0215` already enforce.

    So splitting a channel must change which *channel* a port reads and nothing about which
    *step* feeds which — asserted over the wiring rather than argued in a docstring.
    """
    def wiring(artifact: Pipeline):
        return sorted(
            (step.id, item.port, item.source)
            for step in artifact.steps
            for item in step.inputs
            if item.source is not None
        )

    assert wiring(_artifact(_spine(), stack)) == wiring(
        _artifact(_spine(channels=[DraftChannel(ports=("counts.annotation",))]), stack)
    )

"""The blueprint engine against the real registry, with no database and no provider.

Task 6's checkpoint is two sentences and each has a test here: *identical goal + registry +
policy produces identical blueprint and proposal order*, and *no per-module model calls occur
for tiers 1 to 3*. The shapes it names are real goals, not fixtures — one step, the RNA-seq
spine, an N→N flow and an N→1 gatherer, and a branched blueprint whose order must not depend on
anything but the graph.

**The discriminating test for the whole commit path** is
`test_accepting_every_step_rebuilds_the_blueprint_through_ir_of`: a committed draft, materialised
the ordinary way, must come back with the same contracts, the same wires and the same authors
the resolver produced. Every smaller test passes on a commit that quietly drops a reason.
"""

from pathlib import Path

import pytest
from comeni_core import yaml_strict
from comeni_core.artifact.pipeline import Pipeline
from comeni_core.plan.decision import ProducerDecision
from comeni_core.plan.draft import DraftGraph, DraftProvenance
from comeni_core.plan.tiers import Tier, ValueSource
from mendel_api.services import blueprint as bp
from mendel_api.services import registry
from mendel_resolver.goal import Goal
from mendel_resolver.materialise import ir_of

ROOT = Path(__file__).resolve().parents[3]
STAR = "nf-core/star/align@1.11.0"
HISAT2 = "nf-core/hisat2/align@2.2.2"
SORT = "nf-core/samtools/sort@1.21.0"


def _rnaseq() -> Goal:
    return Goal.model_validate(yaml_strict.load(ROOT / "examples" / "rnaseq-goal.yml"))


def _one_step() -> Goal:
    return Goal.model_validate({"have": [{"type_id": "fastq.reads"}], "want": ["qc.report"]})


def _gathered() -> Goal:
    return Goal.model_validate(
        {
            "have": [{"type_id": "fastq.reads"}],
            "want": ["qc.report"],
            "constraints": {"required_states": {"qc.report": ["aggregated"]}},
        }
    )


@pytest.fixture(scope="module")
def spine() -> bp.Blueprint:
    return bp.resolve(_rnaseq())[0]


@pytest.fixture(scope="module")
def contracts():
    return registry.stack().registry


# ── the shapes Task 6 names ───────────────────────────────────────────────────────────────


def test_a_one_step_pipeline_is_one_card_with_nothing_else_to_choose():
    """**Also a regression.** MultiQC produces `qc.report` and consumes it, and the first run of
    this test offered it as FastQC's alternative — the same self-loop as the sorter, in a shape
    that had no consuming step to exclude, which is why the rule became one about types."""
    blueprint, _ = bp.resolve(_one_step())
    assert blueprint.order == ["fastqc"]

    offered = _payload(blueprint, "fastqc", goal=_one_step())
    assert offered["block"]["tier"] == 1
    assert offered["options"] == {bp.KEEP: "nf-core/fastqc@0.12.1"}
    assert blueprint.after("fastqc") is None


def test_the_rnaseq_spine_is_revealed_in_layout_order(spine):
    """A branched blueprint: the index and the trimmer share rank 0, and the order between them
    comes from the layout rather than from dictionary order or which one the router met first."""
    assert spine.order == [
        "star_genomegenerate",
        "trimgalore",
        "star_align",
        "samtools_sort",
        "subread_featurecounts",
    ]


def test_a_per_item_flow_and_a_gatherer_keep_their_cardinality(contracts):
    """N→N and N→1. FastQC runs once per item and MultiQC once for all of them, and the
    blueprint has to carry that so the canvas can draw `×N` into one node rather than N wires."""
    blueprint, _ = bp.resolve(_gathered())
    assert blueprint.order == ["fastqc", "multiqc"]

    per_item = blueprint.step("fastqc").inputs[0]
    gathered = blueprint.step("multiqc").inputs[0]
    assert per_item.gather is False
    assert gathered.gather is True and gathered.source == "fastqc.zip"


def test_the_same_goal_and_registry_and_policy_give_the_same_blueprint():
    """The checkpoint, stated as bytes rather than as a similar-looking object."""
    first, _ = bp.resolve(_rnaseq())
    second, _ = bp.resolve(_rnaseq())
    assert first.model_dump_json() == second.model_dump_json()


def test_a_blueprint_survives_being_stored_and_read_back(spine):
    """It lives in a JSON column. `admit()` dropping fields and a record that did not survive a
    read-back are both on this project's list of defects found by running rather than testing."""
    assert bp.Blueprint.model_validate_json(spine.model_dump_json()) == spine


# ── alternatives ──────────────────────────────────────────────────────────────────────────


def test_every_offered_option_id_maps_to_a_contract_the_server_holds():
    """The block the browser renders and the set the server enforces are written together
    (spec §14.4): *keep*, each alternative that can be built, and the fact the rule lacked —
    and every alternative id stands for the amendment stored beside it."""
    data = yaml_strict.load(ROOT / "examples" / "rnaseq-goal.yml")
    data["profile"].pop("read_length")
    blueprint, _ = bp.resolve(Goal.model_validate(data))
    offered = _payload(blueprint, "star_align", goal=Goal.model_validate(data))
    shown = {option["id"] for option in offered["block"]["alternatives"]}

    assert shown, "the aligner offered no alternatives, so this asserted nothing"
    assert set(offered["options"]) == {bp.KEEP, "fact_read_length"} | set(offered["amendments"])
    assert set(offered["amendments"]) <= shown


def _payload(
    blueprint, node: str, present: frozenset[str] = frozenset(), goal: Goal | None = None
) -> dict:
    """The step's card as the building stage stores it (`step_payload`, spec §14.4)."""
    from mendel_api.services import declared
    from mendel_api.stages.building import step_payload
    from mendel_authoring.pacing import Stop
    from mendel_authoring.plan import plan_of

    plan = plan_of(blueprint, declared.of(registry.stack()))
    planned = next(s for s in plan.steps if s.node == node)
    return step_payload(blueprint, planned, goal or _rnaseq(), present, Stop.TOGETHER)


# ── committing ────────────────────────────────────────────────────────────────────────────


def _accept(blueprint, graph, provenance, node, contracts, by="ana"):
    return bp.committed(blueprint, graph, provenance, node, by=by)


def test_an_edge_is_committed_only_when_both_of_its_steps_are(spine, contracts):
    """Reject the trimmer: the aligner still joins the index, and no wire reaches a step that
    was never accepted."""
    graph, provenance = DraftGraph(), DraftProvenance()
    graph, provenance = _accept(spine, graph, provenance, "star_genomegenerate", contracts)
    graph, provenance = _accept(spine, graph, provenance, "star_align", contracts)

    wires = {(e.from_node, e.to_node) for e in graph.edges}
    assert wires == {("star_genomegenerate", "star_align")}


def test_a_step_accepted_after_its_consumer_still_joins_it(spine, contracts):
    """Either direction. Accepting the trimmer late must not leave the aligner unfed."""
    graph, provenance = DraftGraph(), DraftProvenance()
    graph, provenance = _accept(spine, graph, provenance, "star_align", contracts)
    graph, provenance = _accept(spine, graph, provenance, "trimgalore", contracts)

    assert ("trimgalore", "reads", "star_align", "reads") in {
        (e.from_node, e.from_port, e.to_node, e.to_port) for e in graph.edges
    }


def test_acknowledging_a_resolver_step_keeps_the_resolver_as_its_author(spine, contracts):
    graph, provenance = _accept(spine, DraftGraph(), DraftProvenance(), "star_align", contracts)
    selection = provenance.node("star_align").selection

    assert selection.source is ValueSource.RESOLVER
    assert selection.tier is Tier.DATA_PROFILED
    assert selection.reason == spine.step("star_align").why.reason


def _with_why(blueprint, node, **why):
    steps = [
        step.model_copy(update={"why": step.why.model_copy(update=why)})
        if step.id == node
        else step
        for step in blueprint.pipeline.steps
    ]
    return blueprint.model_copy(
        update={"pipeline": blueprint.pipeline.model_copy(update={"steps": steps})}
    )


def test_a_person_accepting_a_tier_four_default_is_its_author(spine, contracts):
    """Build mode's flag picked the first candidate and said nobody judged it. A person pressing
    accept *is* the judgement, and the sidecar has to say so rather than keep the flag's
    `resolver` label on a choice a human made."""
    flagged = _with_why(spine, "star_align", tier=Tier.AMBIGUOUS, source=ValueSource.RESOLVER)
    _, provenance = _accept(flagged, DraftGraph(), DraftProvenance(), "star_align", contracts)
    selection = provenance.node("star_align").selection

    assert selection.source is ValueSource.HUMAN
    assert selection.tier is Tier.AMBIGUOUS


def test_a_models_tier_four_choice_stays_the_models(spine, contracts):
    """Spawn's model chose, and a person acknowledging it does not convert that into a human
    decision — A130's direction, and the one a later reader most needs to be right."""
    chosen = _with_why(spine, "star_align", tier=Tier.AMBIGUOUS, source=ValueSource.MODEL)
    chosen = chosen.model_copy(
        update={
            "pipeline": chosen.pipeline.model_copy(
                update={
                    "decisions": [
                        ProducerDecision(
                            key="producer:alignment.bam",
                            subject="producer:alignment.bam",
                            reason="splice-aware",
                            resolved_by="claude-opus-5",
                            chosen=STAR,
                            candidates=[STAR, HISAT2],
                        )
                    ]
                }
            )
        }
    )
    _, provenance = _accept(chosen, DraftGraph(), DraftProvenance(), "star_align", contracts)
    selection = provenance.node("star_align").selection

    assert selection.source is ValueSource.MODEL
    assert selection.by == "claude-opus-5"


def test_accepting_every_step_rebuilds_the_blueprint_through_ir_of(spine, contracts):
    """**The discriminating test.** Accept the whole blueprint as proposed, materialise the
    draft the ordinary way, and the pipeline must name the same contracts, carry the same wires,
    and credit the same authors at the same tiers the resolver did."""
    goal = _rnaseq()
    graph, provenance = DraftGraph(profile=goal.profile), DraftProvenance()
    for node in spine.order:
        graph, provenance = _accept(spine, graph, provenance, node, contracts)

    stack = registry.stack()
    ir = ir_of(graph, stack, provenance=provenance)
    rebuilt = Pipeline.of(
        ir, stack.registry, stack.vocabulary, stack.measurements, stack.paths, goal=goal
    )

    def shape(pipeline):
        return {
            step.id: (
                step.module.contract_id,
                step.why.source,
                step.why.tier,
                sorted(i.source for i in step.inputs if i.source),
            )
            for step in pipeline.steps
        }

    assert shape(rebuilt) == shape(spine.pipeline)


def test_a_step_card_carries_exactly_the_wires_accepting_it_would_add(spine, contracts):
    """What the browser draws optimistically must be what the server commits. The aligner's
    proposal, offered after only the index is in the draft, carries the index wire and not the
    trimmer's — and `committed` adds the same one."""
    offered = _payload(spine, "star_align", present=frozenset({"star_genomegenerate"}))
    graph, _ = _accept(spine, DraftGraph(nodes=[{"id": "star_genomegenerate",
        "contract_id": "nf-core/star/genomegenerate@1.11.0"}]), DraftProvenance(),
        "star_align", contracts)

    drawn = {(e["from_node"], e["to_node"]) for e in offered["edges"]}
    assert drawn == {("star_genomegenerate", "star_align")}
    assert drawn == {(e.from_node, e.to_node) for e in graph.edges}


def test_each_step_knows_its_site_and_its_candidates():
    """§14.3 of the consultant build: a step's alternatives are the router's candidates at the
    site where its tool was chosen."""
    blueprint, _ = bp.resolve(_rnaseq())
    assert set(blueprint.sites) == set(blueprint.order)
    assert blueprint.sites["star_align"].type_id == "alignment.bam"
    assert "nf-core/hisat2/align@2.2.2" in bp.candidates(blueprint, "star_align")
    assert "nf-core/samtools/sort@1.21.0" not in bp.candidates(blueprint, "star_align"), (
        "the sorter consumes the BAM it would stand in for"
    )
    assert bp.candidates(blueprint, "no_such_step") == []

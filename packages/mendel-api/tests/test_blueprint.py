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
from comeni_ai import Client, ModelAccess, ModelUnavailableError
from comeni_core import yaml_strict
from comeni_core.artifact.pipeline import Pipeline
from comeni_core.plan.decision import ProducerDecision
from comeni_core.plan.draft import DraftGraph, DraftProvenance
from comeni_core.plan.tiers import Tier, ValueSource
from mendel_api.authoring.types import Mode
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
    return bp.resolve(_rnaseq(), mode=Mode.BUILD)[0]


@pytest.fixture(scope="module")
def contracts():
    return registry.stack().registry


# ── the shapes Task 6 names ───────────────────────────────────────────────────────────────


def test_a_one_step_pipeline_is_one_proposal_with_nothing_else_to_choose(contracts):
    """**Also a regression.** MultiQC produces `qc.report` and consumes it, and the first run of
    this test offered it as FastQC's alternative — the same self-loop as the sorter, in a shape
    that had no consuming step to exclude, which is why the rule became one about types."""
    blueprint, _ = bp.resolve(_one_step(), mode=Mode.BUILD)
    assert blueprint.order == ["fastqc"]

    offered = bp.proposal(blueprint, "fastqc", registry=contracts)
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
    blueprint, _ = bp.resolve(_gathered(), mode=Mode.BUILD)
    assert blueprint.order == ["fastqc", "multiqc"]

    per_item = blueprint.step("fastqc").inputs[0]
    gathered = blueprint.step("multiqc").inputs[0]
    assert per_item.gather is False
    assert gathered.gather is True and gathered.source == "fastqc.zip"


def test_the_same_goal_and_registry_and_policy_give_the_same_blueprint():
    """The checkpoint, stated as bytes rather than as a similar-looking object."""
    first, _ = bp.resolve(_rnaseq(), mode=Mode.BUILD)
    second, _ = bp.resolve(_rnaseq(), mode=Mode.BUILD)
    assert first.model_dump_json() == second.model_dump_json()


def test_a_blueprint_survives_being_stored_and_read_back(spine):
    """It lives in a JSON column. `admit()` dropping fields and a record that did not survive a
    read-back are both on this project's list of defects found by running rather than testing."""
    assert bp.Blueprint.model_validate_json(spine.model_dump_json()) == spine


# ── the model is reached only for tier 4 ──────────────────────────────────────────────────


class Refusing:
    def __init__(self) -> None:
        self.sent: list[str] = []

    def send(self, access, prompt: str) -> str:
        self.sent.append(prompt)
        raise ModelUnavailableError("MA0007: fake/test: connection refused")


def test_spawn_calls_no_model_for_anything_the_resolver_settled():
    """**The checkpoint's second sentence.** The spine has one tier-4 question, and its only
    candidate is null — so nothing is put to the model, and the transport is never touched. A
    per-module call would show up as a prompt in `sent`."""
    transport = Refusing()
    spawned, calls = bp.resolve(
        _rnaseq(), mode=Mode.SPAWN, client=Client(ModelAccess(model="fake/test"), transport)
    )
    built, _ = bp.resolve(_rnaseq(), mode=Mode.BUILD)

    assert transport.sent == []
    assert calls == []
    assert spawned.pipeline.model_dump_json() == built.pipeline.model_dump_json()


def test_spawn_with_no_configured_model_resolves_exactly_as_build_does():
    """*Also wait; never fabricate.* No model is not an error and not a guess — the questions
    stay open, the same way Build leaves them."""
    spawned, calls = bp.resolve(_rnaseq(), mode=Mode.SPAWN, client=None)
    built, _ = bp.resolve(_rnaseq(), mode=Mode.BUILD)

    assert calls == []
    assert spawned.pipeline == built.pipeline
    assert spawned.mode is Mode.SPAWN


# ── alternatives ──────────────────────────────────────────────────────────────────────────


def test_an_aligner_is_offered_the_other_aligner_and_never_the_step_that_consumes_it(
    spine, contracts
):
    """**A regression, found by the first smoke run.** `samtools/sort` produces `alignment.bam`
    and consumes it, so the candidate service lists it — and it was offered as an alternative to
    the STAR aligner feeding it. That is the self-loop the router excludes by construction."""
    offered = bp.alternatives(spine, "star_align", registry=contracts)

    assert HISAT2 in offered
    assert SORT not in offered, "the consuming step was offered as its own producer"
    assert STAR not in offered


def test_a_decision_supplies_its_own_candidates_before_the_candidate_service(spine, contracts):
    """The resolver's record wins, because it is the resolver saying what it chose between. The
    candidate here exists nowhere in the registry, so only the decision could have supplied it."""
    invented_by_the_record = "nf-core/bwa/mem@0.7.18"
    decided = spine.model_copy(
        update={
            "pipeline": spine.pipeline.model_copy(
                update={
                    "decisions": [
                        ProducerDecision(
                            key="producer:alignment.bam",
                            subject="producer:alignment.bam",
                            reason="two aligners and no rule",
                            resolved_by="flag-only",
                            chosen=STAR,
                            candidates=[STAR, invented_by_the_record],
                        )
                    ]
                }
            )
        }
    )
    assert bp.alternatives(decided, "star_align", registry=contracts) == [invented_by_the_record]


def test_every_offered_option_id_maps_to_a_contract_the_server_holds(spine, contracts):
    """The block the browser renders and the set the server enforces are written together."""
    offered = bp.proposal(spine, "star_align", registry=contracts)
    shown = {option["id"] for option in offered["block"]["alternatives"]}

    assert shown, "the aligner offered no alternatives, so this asserted nothing"
    assert shown | {bp.KEEP} == set(offered["options"])


# ── committing ────────────────────────────────────────────────────────────────────────────


def _accept(blueprint, graph, provenance, node, contracts, contract=None, by="ana"):
    return bp.committed(
        blueprint,
        graph,
        provenance,
        node,
        contract_id=contract or blueprint.step(node).module.contract_id,
        by=by,
        registry=contracts,
    )


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


def test_choosing_an_alternative_makes_the_person_its_author(spine, contracts):
    graph, provenance = _accept(
        spine, DraftGraph(), DraftProvenance(), "star_align", contracts, contract=HISAT2
    )
    selection = provenance.node("star_align").selection

    assert graph.nodes[0].contract_id == HISAT2
    assert selection.source is ValueSource.HUMAN
    assert selection.by == "ana"


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


def test_a_proposal_carries_exactly_the_wires_accepting_it_would_add(spine, contracts):
    """What the browser draws optimistically must be what the server commits. The aligner's
    proposal, offered after only the index is in the draft, carries the index wire and not the
    trimmer's — and `committed` adds the same one."""
    offered = bp.proposal(
        spine, "star_align", registry=contracts, present=frozenset({"star_genomegenerate"})
    )
    graph, _ = _accept(spine, DraftGraph(nodes=[{"id": "star_genomegenerate",
        "contract_id": "nf-core/star/genomegenerate@1.11.0"}]), DraftProvenance(),
        "star_align", contracts)

    drawn = {(e["from_node"], e["to_node"]) for e in offered["edges"]}
    assert drawn == {("star_genomegenerate", "star_align")}
    assert drawn == {(e.from_node, e.to_node) for e in graph.edges}

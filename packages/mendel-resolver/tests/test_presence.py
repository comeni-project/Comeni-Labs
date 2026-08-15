"""A step can be absent, and a convention cannot block routing.

Spec §4.1 and §8.2. `presence: absent` is the effect the shipped format could not spell —
`producer_of: fastq.reads` with `then: null` was the way to say "do not trim", which reads as
a null pointer rather than as a claim about a pipeline.

**The finding that nearly shipped is the second half.** Giving the format a presence effect
without splitting the state requirement produces an *unroutable* pipeline rather than a
shorter one: `star/align` declared `state_required: [trimmed]`, and STAR soft-clips adapters.
nf-core/rnaseq's `--skip_trimming` exists precisely because trimming is optional, so the
contract had encoded a tier-2 convention as a tier-1 constraint — the same disease as "the
only contract that produces this" (A113), one layer down.
"""

import pathlib

import pytest
from mendel_resolver import layers
from mendel_resolver.goal import Goal, GoalInput
from mendel_resolver.router import UnroutableError, route

ROOT = pathlib.Path(__file__).parents[3]


@pytest.fixture
def registry():
    return layers.load(ROOT / "registry").registry


def _goal() -> Goal:
    return Goal(
        have=[
            GoalInput(type_id="fastq.reads"),
            GoalInput(type_id="annotation.gtf"),
            GoalInput(type_id="genome.fasta"),
        ],
        want=["counts.matrix"],
    )


def test_the_spine_still_inserts_trimming_when_no_rule_removes_it(registry):
    """The half that makes the other half safe. A conventional requirement still *drives
    insertion* — dropping it unconditionally would delete trimming from every pipeline,
    which is a far bigger change than the one this task is making."""
    steps = [s.contract_id for s in route(_goal(), registry).steps]
    assert "nf-core/trimgalore@0.6.10" in steps
    assert "nf-core/star/align@1.11.0" in steps


def test_removing_a_conventionally_required_state_still_routes(registry):
    """§8.2. STAR soft-clips, so `trimmed` is a convention and only a structural requirement
    may block routing. Before the split this raised `nothing produces fastq.reads with states
    ['trimmed']` — a rule saying "skip trimming" made the pipeline unbuildable."""
    plan = route(_goal(), registry, absent_roles=frozenset({"trimming"}))
    steps = [s.contract_id for s in plan.steps]
    assert "nf-core/star/align@1.11.0" in steps
    assert "nf-core/trimgalore@0.6.10" not in steps


def test_removing_a_structurally_required_state_is_refused(registry):
    """featureCounts genuinely requires a coordinate-sorted BAM. Absence is unroutable and
    must say so, rather than emitting something that dies at run time — which is the whole
    difference between the two fields."""
    with pytest.raises(UnroutableError, match="coordinate_sorted"):
        route(_goal(), registry, absent_roles=frozenset({"bam_sorting"}))


def test_an_absent_role_removes_every_contract_that_fills_it(registry):
    """Keyed on the role rather than on the contract, so a lab that adds a second trimmer
    does not have to name it in the rule that turns trimming off. That is the whole reason
    a decision targets a role."""
    plan = route(_goal(), registry, absent_roles=frozenset({"trimming"}))
    for step in plan.steps:
        assert "trimming" not in registry.get(step.contract_id).roles


def test_a_presence_absent_rule_removes_the_step_from_a_built_pipeline(tmp_path):
    """End to end, through `resolve()`, because `presence_for` being correct proves nothing
    about whether anything *calls* it.

    That is the shape A14 is about and the shape this plan has already hit three times —
    including in Task 0, where four green tests exercised a role check no loader ran.
    """
    import shutil

    from mendel_resolver import layers as layer_loader
    from mendel_resolver.resolve import resolve

    layer = tmp_path / "layer"
    shutil.copytree(ROOT / "registry", layer)
    (layer / "rules" / "skip-trimming.yml").write_text("""
version: 1
decisions:
  - decides: {effect: presence, of: trimming}
    because: "whether reads need adapter removal before alignment"
    rows:
      - when: {}
        then: absent
        because: >-
          this fixture turns trimming off unconditionally; the point under test is that the
          pipeline still routes, not that skipping trimming is ever the right call
        cite: "nf-core/rnaseq --skip_trimming"
""")
    loaded = layer_loader.load(layer)
    ir = resolve(
        _goal(),
        loaded.registry,
        loaded.rules,
        loaded.measurements,
        vocabulary=loaded.vocabulary,
    )
    steps = [node.contract_id for node in ir.nodes]
    assert "nf-core/trimgalore@0.6.10" not in steps
    assert "nf-core/star/align@1.11.0" in steps, "the pipeline is shorter, not unroutable"

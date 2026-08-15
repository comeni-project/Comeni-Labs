"""A decision exits at the tier its evidence earned, not at the tier its code path implies.

Spec §1 and §4.4. The tier ladder is a product commitment — `CLAUDE.md` prints the table and
the CLI colours by it — so a tier that means "which branch ran" rather than "what settled
this" makes the whole ladder decorative.

Two defects, from opposite ends:

- **A113.** A module chosen because it was the only candidate reported **tier 1**, whose
  definition is *"no choice exists — inputs force it"*. One contract in the stack is a fact
  about registry contents, not about the inputs: install a second sorter tomorrow and the
  same pipeline becomes a real choice. That is a convention, and it is tier 2.
- **The catch-all.** A row testing no premise positively also reported tier 3, whose
  definition is *"a declared rule matched measured data"* — with no measured data anywhere in
  it. Tier 3 is advisory, meaning *"the machinery worked, check the premise"*, and a
  catch-all offers no premise to check.
"""

import pathlib

import pytest
from comeni_core.tiers import ReviewLevel, Tier, ValueSource
from mendel_resolver import layers
from mendel_resolver.goal import Goal, GoalInput
from mendel_resolver.resolve import resolve
from mendel_resolver.rules import RuleValidationError

ROOT = pathlib.Path(__file__).parents[3]


@pytest.fixture(scope="module")
def loaded():
    return layers.load(ROOT / "registry")


def _goal(loaded) -> Goal:
    """Carries `read_length`, so the shipped aligner rule fires and there is a tier-3
    selection to check a review level against."""
    return Goal(
        have=[
            GoalInput(type_id="fastq.reads"),
            GoalInput(type_id="annotation.gtf"),
            GoalInput(type_id="genome.fasta"),
        ],
        want=["counts.matrix"],
        profile=loaded.measurements.profile({"read_length": 150}, source=ValueSource.MEASURED),
    )


def _build(loaded):
    return resolve(
        _goal(loaded), loaded.registry, loaded.rules, loaded.measurements,
        vocabulary=loaded.vocabulary,
    )


def _node(ir, node_id):
    return next(node for node in ir.nodes if node.id == node_id)


def test_a_tier_2_row_must_carry_a_citation(tmp_path):
    """A76 and A128 stated as a rule rather than fixed twice.

    Tier 2 is *"a documented default exists"*, so its output is value plus the document. A
    row with a `because` and no `cite` states the value and asserts the document — which is
    the shape both of those findings had, one in a contract default and one in a rule.
    """
    import shutil

    layer = tmp_path / "layer"
    shutil.copytree(ROOT / "registry", layer)
    (layer / "rules" / "catch-all.yml").write_text("""
version: 1
decisions:
  - decides: {effect: presence, of: trimming}
    rows: [{when: {}, then: absent, because: "nothing to trim"}]
""")
    with pytest.raises(RuleValidationError, match="exits at tier 2"):
        layers.load(layer)


def test_only_one_candidate_is_not_a_forcing_constraint(loaded):
    """A113. Tier 1 produces `value + the forcing constraint`, and "this stack holds one
    contract" is a fact about registry contents rather than about the inputs."""
    sorter = _node(_build(loaded), "samtools_sort")
    assert sorter.selection.tier is Tier.CONVENTION
    assert "only contract" not in sorter.selection.reason
    assert "uncontested" in sorter.selection.reason


def test_the_presence_of_a_forced_step_is_still_tier_1(loaded):
    """The other half, and the reason A113 is a *split* rather than a demotion.

    featureCounts requires a coordinate-sorted BAM, so a sorter must exist — that genuinely
    is an input forcing a step, and it is tier 1. Which *contract* sorts is the part that was
    never forced. Collapsing the two is what let a fact about the registry wear tier 1's
    badge.
    """
    sorter = _node(_build(loaded), "samtools_sort")
    assert sorter.presence.tier is Tier.STRUCTURAL
    assert "alignment.bam" in sorter.presence.reason


def test_a_step_the_goal_asked_for_says_so(loaded):
    """The other way a step's presence is forced. Naming which one matters to a reader
    deciding whether they can remove it."""
    counts = _node(_build(loaded), "subread_featurecounts")
    assert counts.presence.tier is Tier.STRUCTURAL
    assert "the goal" in counts.presence.reason


def test_a_tier_states_its_own_review_level(loaded):
    """§6.2. `tier: 3` is a number whose meaning lives in a table in another document, and a
    reader should not need `CLAUDE.md` open to learn what it obliges them to do."""
    aligner = _node(_build(loaded), "star_align")
    assert aligner.selection.tier is Tier.DATA_PROFILED
    assert aligner.selection.review_level is ReviewLevel.ADVISORY


def test_the_artifact_states_the_review_level_beside_the_tier(loaded, tmp_path):
    """§6.2, and the field this task actually adds.

    `ResolvedValue.review_level` has existed since Plan 1, so a test reading *that* proves
    nothing about `Why` — which is the model a `pipeline.yml` is made of and the one a
    stranger opens. Reverting the new computed field left every other test in this file
    green, in code written the same hour.
    """
    from comeni_core.pipeline import Pipeline
    from comeni_core.tiers import ReviewLevel as RL

    goal = _goal(loaded)
    pipeline = Pipeline.of(
        _build(loaded),
        loaded.registry,
        loaded.vocabulary,
        loaded.measurements,
        loaded.paths,
        goal=goal,
    )
    aligner = next(step for step in pipeline.steps if step.id == "star_align")
    assert aligner.why.tier is Tier.DATA_PROFILED
    assert aligner.why.review_level is RL.ADVISORY
    sorter = next(step for step in pipeline.steps if step.id == "samtools_sort")
    assert sorter.presence.tier is Tier.STRUCTURAL
    assert sorter.presence.review_level is RL.NONE


def test_the_review_level_is_derived_and_cannot_disagree_with_the_tier():
    """Two fields that can disagree is a field that will. Computed, never stored — `Why`
    already learned that once, which is why `for_value` exists (A104)."""
    from comeni_core.ir import ResolvedValue

    assert ResolvedValue(value=1, tier=Tier.CONVENTION, reason="x").review_level is (
        ReviewLevel.NONE
    )
    assert ResolvedValue(value=1, tier=Tier.AMBIGUOUS, reason="x").review_level is (
        ReviewLevel.REQUIRED
    )


def test_the_review_queue_did_not_grow(loaded):
    """Step 6's check, as a test rather than as a command somebody remembers to run.

    Tier 1 is silent and tier 2 is green, so demoting a selection from one to the other must
    not move this number. If it did, the split is wrong.
    """
    assert _build(loaded).needs_review() == ["star_align.seq_platform"]

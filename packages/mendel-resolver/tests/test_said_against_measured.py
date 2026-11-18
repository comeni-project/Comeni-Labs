"""A fact a person said that the data measures otherwise (#510, option C).

On the walk of 2026-11-15 `read_length: 150, said` chose STAR while the reads measured about 99,
and the explanation stated 150 as a fact about the reads. A person's word still stands; a choice
that read it is tier 4, flagged for review, and its reason gives both values."""

import pytest
from comeni_core.declared.measurement import MeasuredEntry
from comeni_core.goal.premise import PremiseRecord
from comeni_core.plan.tiers import PremiseOrigin, Tier, ValueSource
from mendel_resolver import layers
from mendel_resolver.goal import Goal, GoalInput
from mendel_resolver.resolve import resolve
from support.paths import ROOT


@pytest.fixture(scope="module")
def stack():
    return layers.load(ROOT / "registry")


def _aligner(stack, read_length: MeasuredEntry):
    profile = stack.measurements.profile_of(
        [read_length, MeasuredEntry("strandedness", "reverse", ValueSource.SAID)])
    goal = Goal(have=[GoalInput(type_id="fastq.reads"), GoalInput(type_id="annotation.gtf"),
                      GoalInput(type_id="genome.fasta")],
                want=["counts.matrix"],
                constraints={"required_states": {"counts.matrix": ["gene_level"]}},
                profile=profile)
    ir = resolve(goal, stack.registry, stack.rules, stack.measurements,
                 vocabulary=stack.vocabulary)
    return next(n for n in ir.nodes if n.contract_id.startswith("nf-core/star/align"))


def test_a_choice_on_a_contradicted_fact_is_flagged_with_both_values(stack):
    star = _aligner(stack, MeasuredEntry("read_length", 150, ValueSource.SAID, measured=99))
    assert star.selection.tier is Tier.AMBIGUOUS
    assert "read_length is 150, asserted, not measured; the data measures 99" in (
        star.selection.reason)


def test_the_same_fact_said_alone_stays_at_tier_3(stack):
    star = _aligner(stack, MeasuredEntry("read_length", 150, ValueSource.SAID))
    assert star.selection.tier is Tier.DATA_PROFILED
    assert "measures" not in star.selection.reason


def test_only_a_said_value_can_disagree_with_a_measurement(stack):
    with pytest.raises(ValueError, match="only a value a person said"):
        stack.measurements.profile_of(
            [MeasuredEntry("read_length", 150, ValueSource.MEASURED, measured=99)])


def test_the_record_never_states_the_said_value_as_the_datas():
    record = PremiseRecord(id="read_length", value=150, origin=PremiseOrigin.ASSERTED,
                           measured=99)
    assert record.contradicted
    assert record.prose() == "read_length is 150, asserted, not measured; the data measures 99"

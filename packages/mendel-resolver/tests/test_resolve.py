import pytest
from comeni_core.ir import ReviewLevel, Tier
from comeni_core.registry import Registry
from comeni_core.vocabulary import Vocabulary
from mendel_resolver.goal import DataProfile, Goal, GoalInput
from mendel_resolver.resolve import resolve
from mendel_resolver.rules import RuleTable

COUNTS = """
id: nf-core/subread/featurecounts@2.0.6
nf_process: FEATURECOUNTS
nf_include: modules/nf-core/subread/featurecounts/main
consumes: [{name: bam, type_id: alignment.bam, state_required: [coordinate_sorted]}]
produces: [{name: counts, type_id: counts.matrix, state: [gene_level]}]
params:
  - {name: strandedness, tier_hint: 3}
  - {name: seq_platform, tier_hint: 4, default: illumina}
priority: 0
provenance: {source: hand, drafted_by: hand, approved_by: r, approved_at: "2026-08-02"}
"""
SORT = """
id: nf-core/samtools/sort@1.21.0
nf_process: SAMTOOLS_SORT
nf_include: modules/nf-core/samtools/sort/main
consumes: [{name: bam, type_id: alignment.bam, state_required: []}]
produces: [{name: bam, type_id: alignment.bam, state: [coordinate_sorted]}]
priority: 0
provenance: {source: hand, drafted_by: hand, approved_by: r, approved_at: "2026-08-02"}
"""
RULES = """
rules:
  - id: strandedness-reverse
    subject: strandedness
    when: {strandedness: {"==": reverse}}
    then: {value: 2}
    citation: "featureCounts -s 2 for reverse-stranded libraries"
"""


@pytest.fixture
def setup(tmp_path):
    vocab_dir = tmp_path / "vocab"
    vocab_dir.mkdir()
    (vocab_dir / "alignment.bam.yml").write_text("states: [coordinate_sorted]\n")
    (vocab_dir / "counts.matrix.yml").write_text("states: [gene_level]\n")
    contracts = tmp_path / "contracts"
    contracts.mkdir()
    (contracts / "fc.yml").write_text(COUNTS)
    (contracts / "sort.yml").write_text(SORT)
    rules = tmp_path / "rules.yml"
    rules.write_text(RULES)
    return Registry.load(contracts, Vocabulary.load(vocab_dir)), RuleTable.load(rules)


def test_tier_3_rule_sets_value_and_marks_advisory(setup):
    registry, rules = setup
    goal = Goal(
        have=[GoalInput(type_id="alignment.bam")],
        want=["counts.matrix"],
        profile=DataProfile(strandedness="reverse"),
    )
    ir = resolve(goal, registry, rules)
    node = next(n for n in ir.nodes if n.id == "featurecounts")
    assert node.params["strandedness"].value == 2
    assert node.params["strandedness"].tier is Tier.DATA_PROFILED
    assert node.params["strandedness"].review_level is ReviewLevel.ADVISORY
    assert "featureCounts -s 2" in node.params["strandedness"].reason


def test_rule_miss_demotes_to_tier_4_and_flags(setup):
    registry, rules = setup
    goal = Goal(
        have=[GoalInput(type_id="alignment.bam")],
        want=["counts.matrix"],
        profile=DataProfile(),
    )
    ir = resolve(goal, registry, rules)
    node = next(n for n in ir.nodes if n.id == "featurecounts")
    assert node.params["strandedness"].tier is Tier.AMBIGUOUS
    assert node.params["strandedness"].review_level is ReviewLevel.REQUIRED
    assert "featurecounts.strandedness" in ir.needs_review()


def test_param_with_default_and_no_rule_is_tier_2_convention(setup):
    registry, rules = setup
    goal = Goal(
        have=[GoalInput(type_id="alignment.bam")],
        want=["counts.matrix"],
        profile=DataProfile(strandedness="reverse"),
    )
    ir = resolve(goal, registry, rules)
    node = next(n for n in ir.nodes if n.id == "featurecounts")
    assert node.params["seq_platform"].value == "illumina"
    assert node.params["seq_platform"].tier is Tier.CONVENTION


def test_every_tier_4_resolution_emits_a_decision_record(setup):
    registry, rules = setup
    goal = Goal(
        have=[GoalInput(type_id="alignment.bam")],
        want=["counts.matrix"],
        profile=DataProfile(),
    )
    ir = resolve(goal, registry, rules)
    keys = [d.key for d in ir.decisions]
    assert "featurecounts.strandedness" in keys
    assert ir.decisions[0].resolved_by == "flag-only"


def test_gap_insertion_appears_as_nodes_and_edges(setup):
    registry, rules = setup
    goal = Goal(
        have=[GoalInput(type_id="alignment.bam")],
        want=["counts.matrix"],
        profile=DataProfile(strandedness="reverse"),
    )
    ir = resolve(goal, registry, rules)
    assert [n.id for n in ir.nodes] == ["samtools_sort", "featurecounts"]
    assert len(ir.edges) == 1
    assert ir.edges[0].from_node == "samtools_sort"
    assert ir.edges[0].to_node == "featurecounts"
    assert ir.edges[0].states == frozenset({"coordinate_sorted"})


def test_resolution_is_deterministic(setup):
    registry, rules = setup
    goal = Goal(
        have=[GoalInput(type_id="alignment.bam")],
        want=["counts.matrix"],
        profile=DataProfile(strandedness="reverse"),
    )
    assert (
        resolve(goal, registry, rules).model_dump_json()
        == resolve(goal, registry, rules).model_dump_json()
    )

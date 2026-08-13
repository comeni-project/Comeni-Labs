import pytest
from comeni_core.ir import ReviewLevel, Tier
from comeni_core.measurement import MeasurementRegistry
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
  # `via:` is mandatory since Plan 1.10 Task 3 — a setting with no route reaches no tool.
  # The template is a stand-in: these fixtures test resolution, not emission.
  - {name: strandedness, tier_hint: 3, via: ext, key: args, template: "--x {value}"}
  - {name: seq_platform, tier_hint: 4, default: illumina,
     via: ext, key: args, template: "--x {value}"}
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
version: 1
decisions:
  - decides: {param: strandedness}
    cite: "featureCounts -s 2 for reverse-stranded libraries"
    rows:
      - {when: {strandedness: reverse}, then: 2}
"""
MEASUREMENTS = {
    "strandedness.yml": "kind: enum\nvalues: [forward, reverse, unstranded]\n",
    "read_length.yml": "kind: integer\nminimum: 1\n",
}


def _rules_and_measurements(tmp_path, registry, vocabulary, body):
    """Both, because `resolve()` now needs the measurement registry too.

    It used to build one here and throw it away. `resolve()` validates the goal's profile
    against declared measurements — the check used to live in `mendel build` alone, so
    `mendel upgrade` skipped it entirely (audit A2) — and a test that constructed a second
    registry would be testing against a different set of declarations than it routes with.
    """
    measurements = tmp_path / "measurements"
    measurements.mkdir(exist_ok=True)
    for name, declaration in MEASUREMENTS.items():
        (measurements / name).write_text(declaration)
    declared = MeasurementRegistry.load(tmp_path)
    # A layer's rules live in `<layer>/rules/`. `RuleTable.load` took a bare file path
    # too, which is one more way to spell "a layer" than a layer has.
    rules = tmp_path / "rules"
    rules.mkdir(exist_ok=True)
    (rules / "r.yml").write_text(body)
    return (
        RuleTable.load(
            tmp_path, registry=registry, vocabulary=vocabulary, measurements=declared
        ),
        declared,
    )


@pytest.fixture
def setup(tmp_path):
    vocab_dir = tmp_path / "vocabularies"
    vocab_dir.mkdir()
    (vocab_dir / "alignment.bam.yml").write_text("states: [coordinate_sorted]\n")
    (vocab_dir / "counts.matrix.yml").write_text("states: [gene_level]\n")
    contracts = tmp_path / "contracts"
    contracts.mkdir()
    (contracts / "fc.yml").write_text(COUNTS)
    (contracts / "sort.yml").write_text(SORT)
    vocabulary = Vocabulary.load(tmp_path)
    registry = Registry.load(tmp_path, vocabulary)
    return registry, *_rules_and_measurements(tmp_path, registry, vocabulary, RULES), vocabulary


def test_tier_3_rule_sets_value_and_marks_advisory(setup):
    registry, rules, measurements, vocabulary = setup
    goal = Goal(
        have=[GoalInput(type_id="alignment.bam")],
        want=["counts.matrix"],
        profile=DataProfile(strandedness="reverse"),
    )
    ir = resolve(goal, registry, rules, measurements, vocabulary=vocabulary)
    node = next(n for n in ir.nodes if n.id == "featurecounts")
    assert node.param("strandedness").value == 2
    assert node.param("strandedness").tier is Tier.DATA_PROFILED
    assert node.param("strandedness").review_level is ReviewLevel.ADVISORY
    assert "featureCounts -s 2" in node.param("strandedness").reason


def test_rule_miss_demotes_to_tier_4_and_flags(setup):
    registry, rules, measurements, vocabulary = setup
    goal = Goal(
        have=[GoalInput(type_id="alignment.bam")],
        want=["counts.matrix"],
        profile=DataProfile(),
    )
    ir = resolve(goal, registry, rules, measurements, vocabulary=vocabulary)
    node = next(n for n in ir.nodes if n.id == "featurecounts")
    assert node.param("strandedness").tier is Tier.AMBIGUOUS
    assert node.param("strandedness").review_level is ReviewLevel.REQUIRED
    assert "featurecounts.strandedness" in ir.needs_review()


def test_param_with_default_and_no_rule_is_tier_2_convention(setup):
    registry, rules, measurements, vocabulary = setup
    goal = Goal(
        have=[GoalInput(type_id="alignment.bam")],
        want=["counts.matrix"],
        profile=DataProfile(strandedness="reverse"),
    )
    ir = resolve(goal, registry, rules, measurements, vocabulary=vocabulary)
    node = next(n for n in ir.nodes if n.id == "featurecounts")
    assert node.param("seq_platform").value == "illumina"
    assert node.param("seq_platform").tier is Tier.CONVENTION


def test_every_tier_4_resolution_emits_a_decision_record(setup):
    registry, rules, measurements, vocabulary = setup
    goal = Goal(
        have=[GoalInput(type_id="alignment.bam")],
        want=["counts.matrix"],
        profile=DataProfile(),
    )
    ir = resolve(goal, registry, rules, measurements, vocabulary=vocabulary)
    keys = [d.key for d in ir.decisions]
    assert "featurecounts.strandedness" in keys
    assert ir.decisions[0].resolved_by == "flag-only"


def test_gap_insertion_appears_as_nodes_and_edges(setup):
    registry, rules, measurements, vocabulary = setup
    goal = Goal(
        have=[GoalInput(type_id="alignment.bam")],
        want=["counts.matrix"],
        profile=DataProfile(strandedness="reverse"),
    )
    ir = resolve(goal, registry, rules, measurements, vocabulary=vocabulary)
    assert [n.id for n in ir.nodes] == ["samtools_sort", "featurecounts"]
    assert len(ir.edges) == 1
    assert ir.edges[0].from_node == "samtools_sort"
    assert ir.edges[0].to_node == "featurecounts"
    assert ir.edges[0].states == frozenset({"coordinate_sorted"})


def test_resolution_is_deterministic(setup):
    registry, rules, measurements, vocabulary = setup
    goal = Goal(
        have=[GoalInput(type_id="alignment.bam")],
        want=["counts.matrix"],
        profile=DataProfile(strandedness="reverse"),
    )
    assert (
        resolve(goal, registry, rules, measurements, vocabulary=vocabulary).model_dump_json()
        == resolve(goal, registry, rules, measurements, vocabulary=vocabulary).model_dump_json()
    )


ALIGN_A = """
id: nf-core/star/align@1.11.0
nf_process: STAR_ALIGN
nf_include: modules/nf-core/star/align/main
consumes: [{name: reads, type_id: fastq.reads, state_required: []}]
produces: [{name: bam, type_id: alignment.bam, state: []}]
priority: 0
provenance: {source: hand, drafted_by: hand, approved_by: r, approved_at: "2026-08-03"}
"""


@pytest.fixture
def tied(tmp_path):
    vocab_dir = tmp_path / "vocabularies"
    vocab_dir.mkdir()
    (vocab_dir / "fastq.reads.yml").write_text("states: []\n")
    (vocab_dir / "alignment.bam.yml").write_text("states: []\n")
    contracts = tmp_path / "contracts"
    contracts.mkdir()
    (contracts / "a.yml").write_text(ALIGN_A)
    (contracts / "b.yml").write_text(
        ALIGN_A.replace("star/align@1.11.0", "hisat2/align@2.2.1").replace(
            "STAR_ALIGN", "HISAT2_ALIGN"
        )
    )
    vocabulary = Vocabulary.load(tmp_path)
    registry = Registry.load(tmp_path, vocabulary)
    return (
        registry,
        *_rules_and_measurements(tmp_path, registry, vocabulary, "version: 1\ndecisions: []\n"),
        vocabulary,
    )


def test_a_routing_tie_is_surfaced_for_review(tied):
    """Invariant 8 demotes a tie to tier 4; invariant 6 says tier 4 is always flagged.

    The DecisionRecord existed but needs_review() only scanned node params, so the
    CLI printed "0 requiring review" and the user was never told their aligner had
    been chosen alphabetically. A record nobody is shown is not a flag.
    """
    registry, rules, measurements, vocabulary = tied
    goal = Goal(have=[GoalInput(type_id="fastq.reads")], want=["alignment.bam"])
    ir = resolve(goal, registry, rules, measurements, vocabulary=vocabulary)

    assert len(ir.decisions) == 1
    flagged = ir.needs_review()
    # Twice over, on purpose: the DecisionRecord names the ambiguity, and now the node's
    # own `selection` names the module. A reviewer asking "which modules need looking at"
    # should not have to join those two lists.
    assert any("producer:alignment.bam" in item for item in flagged)
    assert any(item.endswith("(module)") for item in flagged)


def test_review_list_covers_params_and_decisions_together(setup):
    registry, rules, measurements, vocabulary = setup
    goal = Goal(
        have=[GoalInput(type_id="alignment.bam")],
        want=["counts.matrix"],
        profile=DataProfile(),
    )
    ir = resolve(goal, registry, rules, measurements, vocabulary=vocabulary)
    assert "featurecounts.strandedness" in ir.needs_review()


INDEX = """
id: nf-core/samtools/index@1.21.0
nf_process: SAMTOOLS_INDEX
nf_include: modules/nf-core/samtools/index/main
consumes: [{name: bam, type_id: alignment.bam, state_required: [coordinate_sorted]}]
produces: [{name: bai, type_id: alignment.bam, state: [coordinate_sorted, indexed]}]
priority: 0
provenance: {source: hand, drafted_by: hand, approved_by: r, approved_at: "2026-08-03"}
"""


@pytest.fixture
def with_index(tmp_path):
    vocab_dir = tmp_path / "vocabularies"
    vocab_dir.mkdir()
    (vocab_dir / "alignment.bam.yml").write_text("states: [coordinate_sorted, indexed]\n")
    (vocab_dir / "counts.matrix.yml").write_text("states: [gene_level]\n")
    contracts = tmp_path / "contracts"
    contracts.mkdir()
    (contracts / "fc.yml").write_text(COUNTS)
    (contracts / "sort.yml").write_text(SORT)
    (contracts / "index.yml").write_text(INDEX)
    vocabulary = Vocabulary.load(tmp_path)
    registry = Registry.load(tmp_path, vocabulary)
    return (
        registry,
        *_rules_and_measurements(tmp_path, registry, vocabulary, "version: 1\ndecisions: []\n"),
        vocabulary,
    )


def test_a_consumer_is_fed_a_source_that_satisfies_its_required_states(with_index):
    """`produced` was keyed on type_id alone, so the last producer of a type won.

    With both SAMTOOLS_SORT and SAMTOOLS_INDEX producing `alignment.bam`, featureCounts
    was handed SAMTOOLS_INDEX's `.bai` output — an index file where a BAM belongs. It
    emitted valid Nextflow, raised no flag, and passed `-stub-run`, because nf-core stubs
    never read their inputs. Something was guessed, it was wrong, and it was silent.
    """
    registry, rules, measurements, vocabulary = with_index
    goal = Goal(
        have=[GoalInput(type_id="alignment.bam")],
        want=["counts.matrix", "alignment.bam"],
        constraints={"required_states": {"alignment.bam": ["coordinate_sorted", "indexed"]}},
        profile=DataProfile(strandedness="reverse"),
    )
    ir = resolve(goal, registry, rules, measurements, vocabulary=vocabulary)
    into_fc = [e for e in ir.edges if e.to_node == "featurecounts"]
    assert [e.from_node for e in into_fc] == ["samtools_sort"], (
        f"featurecounts fed from {[e.from_node for e in into_fc]}"
    )


def test_a_resolver_cannot_certify_its_own_answer_as_human():
    """A56. `source: HUMAN` is not a claim like `confidence` and `reason` — it *clears the
    tier-4 review*, moving the value out of `needs_review()` and into `overrides()`. A54's
    fix then wrote `human_override = resolution.chosen` straight from that claim, so the
    evidence `MD0220` checks is manufactured by the same resolver that made the claim.

    Invariant 6 is what that defeats — "tier 4 is always flagged, even at high model
    confidence … the difference from a chat window". Latent today because `FlagOnlyResolver`
    never says HUMAN; live the day Plan 2 wires a model to this port, which is the next plan.
    """
    import pathlib

    from comeni_core.decision import Resolution
    from comeni_core.tiers import ValueSource
    from mendel_resolver import layers
    from mendel_resolver.goal import Goal, GoalInput

    class LyingResolver:
        def resolve(self, ambiguity):
            return Resolution(
                chosen="nefarious",
                reason="trust me",
                confidence=0.99,
                resolved_by="totally-a-model",
                source=ValueSource.HUMAN,
            )

    root = pathlib.Path(__file__).parents[3]
    loaded = layers.load(root / "registry")
    goal = Goal(
        have=[GoalInput(type_id=t) for t in ("fastq.reads", "annotation.gtf", "genome.fasta")],
        want=["counts.matrix"],
        profile=loaded.measurements.profile({}),
    )
    ir = resolve(
        goal,
        loaded.registry,
        loaded.rules,
        loaded.measurements,
        vocabulary=loaded.vocabulary,
        resolver=LyingResolver(),
    )

    assert ir.needs_review(), "the resolver cleared its own tier-4 flag"
    assert ir.overrides() == [], "a resolver's guess was recorded as a human's override"
    forged = [
        d for d in ir.decisions if getattr(d, "human_override", None) is not None
    ]
    assert forged == [], f"the evidence MD0220 checks was manufactured: {forged}"


def test_a_replayed_override_backed_by_its_record_is_still_honoured():
    """The other half of A56, and the half a fix like this usually breaks.

    Demoting an unbacked `HUMAN` is only correct if a *backed* one still clears the review.
    `mendel upgrade` is built on that: a curated pipeline replays every untouched decision,
    and an override that stops being honoured would re-flag questions a person already
    answered — issue #10's shape, a mechanism that runs and changes nothing.
    """
    import pathlib

    from comeni_core.decision import ParamDecision
    from comeni_core.tiers import ValueSource
    from mendel_resolver import layers
    from mendel_resolver.goal import Goal, GoalInput
    from mendel_resolver.replay import ReplayResolver

    root = pathlib.Path(__file__).parents[3]
    loaded = layers.load(root / "registry")
    goal = Goal(
        have=[GoalInput(type_id=t) for t in ("fastq.reads", "annotation.gtf", "genome.fasta")],
        want=["counts.matrix"],
        profile=loaded.measurements.profile({}),
    )
    # `key` is `{node_id}.{subject}` — `Ambiguity.key()`. `chosen=None` with a
    # `human_override` is the real recorded shape: nothing was resolved, a person answered.
    record = ParamDecision(
        key="star_align.seq_platform",
        subject="seq_platform",
        candidates=[None],
        chosen=None,
        reason="our sequencer",
        resolved_by="human",
        human_override="illumina",
    )
    ir = resolve(
        goal,
        loaded.registry,
        loaded.rules,
        loaded.measurements,
        vocabulary=loaded.vocabulary,
        resolver=ReplayResolver([record]),
        prior=[record],
    )

    value = next(
        b.value for n in ir.nodes for b in n.params if b.name == "seq_platform"
    )
    assert value.source is ValueSource.HUMAN, "a backed override lost its human source"
    assert value.value == "illumina"
    assert ir.needs_review() == [], "an answered question was re-flagged"
    assert ir.overrides(), "the answer vanished from overrides()"

import pytest
from comeni_core.registry import Registry
from comeni_core.vocabulary import Vocabulary
from mendel_resolver.goal import Goal, GoalInput
from mendel_resolver.router import UnroutableError, route

ALIGN = """
id: nf-core/star/align@1.11.0
nf_process: STAR_ALIGN
nf_include: modules/nf-core/star/align/main
consumes: [{name: reads, type_id: fastq.reads, state_required: [trimmed]}]
produces: [{name: bam, type_id: alignment.bam, state: []}]
priority: 0
provenance: {source: hand, drafted_by: hand, approved_by: r, approved_at: "2026-08-02"}
"""
TRIM = """
id: nf-core/trimgalore@0.6.10
nf_process: TRIMGALORE
nf_include: modules/nf-core/trimgalore/main
consumes: [{name: reads, type_id: fastq.reads, state_required: []}]
produces: [{name: reads, type_id: fastq.reads, state: [trimmed]}]
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


@pytest.fixture
def registry(tmp_path):
    vocab_dir = tmp_path / "vocab"
    vocab_dir.mkdir()
    (vocab_dir / "fastq.reads.yml").write_text("states: [trimmed]\n")
    (vocab_dir / "alignment.bam.yml").write_text("states: [coordinate_sorted]\n")
    contracts = tmp_path / "contracts"
    contracts.mkdir()
    for name, body in [("align", ALIGN), ("trim", TRIM), ("sort", SORT)]:
        (contracts / f"{name}.yml").write_text(body)
    return Registry.load(contracts, Vocabulary.load(vocab_dir))


def test_inserts_the_gap_filling_step(registry):
    """Raw reads -> sorted BAM must insert both trimming and sorting."""
    goal = Goal(
        have=[GoalInput(type_id="fastq.reads")],
        want=["alignment.bam"],
        constraints={"required_states": {"alignment.bam": ["coordinate_sorted"]}},
    )
    plan = route(goal, registry)
    assert [step.contract_id for step in plan.steps] == [
        "nf-core/trimgalore@0.6.10",
        "nf-core/star/align@1.11.0",
        "nf-core/samtools/sort@1.21.0",
    ]


def test_no_insertion_when_input_already_satisfies(registry):
    goal = Goal(
        have=[GoalInput(type_id="fastq.reads", states=frozenset({"trimmed"}))],
        want=["alignment.bam"],
    )
    plan = route(goal, registry)
    assert [s.contract_id for s in plan.steps] == ["nf-core/star/align@1.11.0"]


def test_unroutable_goal_raises(registry):
    goal = Goal(have=[GoalInput(type_id="fastq.reads")], want=["counts.matrix"])
    with pytest.raises(UnroutableError, match="counts.matrix"):
        route(goal, registry)


def test_routing_is_deterministic(registry):
    goal = Goal(have=[GoalInput(type_id="fastq.reads")], want=["alignment.bam"])
    assert [s.contract_id for s in route(goal, registry).steps] == [
        s.contract_id for s in route(goal, registry).steps
    ]


def test_a_contract_cannot_satisfy_its_own_input(registry):
    """SAMTOOLS_SORT consumes alignment.bam and produces alignment.bam.

    Without cycle exclusion it is selected to satisfy its own input, forever, and the
    only thing that stops it is the depth bound — which then reports the goal as
    unroutable when it is perfectly routable.
    """
    goal = Goal(
        have=[GoalInput(type_id="fastq.reads")],
        want=["alignment.bam"],
        constraints={"required_states": {"alignment.bam": ["coordinate_sorted"]}},
    )
    ids = [s.contract_id for s in route(goal, registry).steps]
    assert ids.count("nf-core/samtools/sort@1.21.0") == 1
    assert "nf-core/star/align@1.11.0" in ids


def test_asking_for_no_state_does_not_add_steps_nobody_wanted(registry):
    """With nothing required, every producer of the type matches on superset.

    The aligner produces alignment.bam[] and the sorter alignment.bam[coordinate_sorted];
    both satisfy "any BAM". Preferring the smaller surplus keeps "get me a BAM" from
    quietly meaning "get me a sorted BAM".
    """
    goal = Goal(
        have=[GoalInput(type_id="fastq.reads", states=frozenset({"trimmed"}))],
        want=["alignment.bam"],
    )
    plan = route(goal, registry)
    assert [s.contract_id for s in plan.steps] == ["nf-core/star/align@1.11.0"]
    assert plan.ambiguities == []


def test_tie_between_producers_becomes_an_ambiguity(tmp_path):
    vocab_dir = tmp_path / "vocab"
    vocab_dir.mkdir()
    (vocab_dir / "fastq.reads.yml").write_text("states: []\n")
    (vocab_dir / "alignment.bam.yml").write_text("states: []\n")
    contracts = tmp_path / "contracts"
    contracts.mkdir()
    (contracts / "a.yml").write_text(
        ALIGN.replace("state_required: [trimmed]", "state_required: []")
    )
    (contracts / "b.yml").write_text(
        ALIGN.replace("state_required: [trimmed]", "state_required: []")
        .replace("nf-core/star/align@1.11.0", "nf-core/hisat2/align@2.2.1")
        .replace("STAR_ALIGN", "HISAT2_ALIGN")
    )
    registry = Registry.load(contracts, Vocabulary.load(vocab_dir))
    plan = route(Goal(have=[GoalInput(type_id="fastq.reads")], want=["alignment.bam"]), registry)
    assert len(plan.ambiguities) == 1
    assert plan.ambiguities[0].subject == "producer:alignment.bam"
    assert sorted(plan.ambiguities[0].candidates) == [
        "nf-core/hisat2/align@2.2.1",
        "nf-core/star/align@1.11.0",
    ]

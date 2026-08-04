import pathlib

import pytest
from mendel_resolver import layers
from mendel_resolver.goal import Goal, GoalInput
from mendel_resolver.router import route

ROOT = pathlib.Path(__file__).parent.parent
VENDOR = ROOT / "vendor"


@pytest.fixture
def registry():
    return layers.load(ROOT / "examples").registry


def test_all_spine_contracts_load(registry):
    assert len(registry.all()) >= 6


def test_every_contract_points_at_vendored_module_code(registry):
    missing = [c.id for c in registry.all() if not (VENDOR / f"{c.nf_include}.nf").exists()]
    assert missing == [], f"contracts without vendored module code: {missing}"


def test_counts_matrix_is_reachable_from_raw_reads(registry):
    goal = Goal(
        have=[
            GoalInput(type_id="fastq.reads"),
            GoalInput(type_id="annotation.gtf"),
            GoalInput(type_id="genome.fasta"),
        ],
        want=["counts.matrix"],
    )
    steps = [s.contract_id for s in route(goal, registry).steps]
    assert "nf-core/trimgalore@0.6.10" in steps
    assert "nf-core/star/align@1.11.0" in steps
    assert "nf-core/samtools/sort@1.21.0" in steps
    assert "nf-core/subread/featurecounts@2.0.6" in steps


def test_qc_report_is_reachable_from_raw_reads(registry):
    goal = Goal(have=[GoalInput(type_id="fastq.reads")], want=["qc.report"])
    assert route(goal, registry).steps != []


def test_every_spine_contract_declares_its_container(registry):
    """The lockfile resolves these to digests later. It cannot resolve what is absent."""
    missing = [c.id for c in registry.all() if not c.container]
    assert missing == [], f"contracts without a container reference: {missing}"


def test_no_contract_uses_a_floating_container_tag(registry):
    """`latest` and friends are not reproducible, and nf-core forbids them upstream too."""
    floating = [
        c.id
        for c in registry.all()
        if c.container and c.container.rsplit(":", 1)[-1] in {"latest", "dev", "master"}
    ]
    assert floating == []


def test_contract_input_signatures_match_the_vendored_modules(registry):
    """nf_inputs must have one entry per channel the process declares.

    Written after guessing wrong twice: multiqc takes one tuple of six paths rather
    than six channels, and samtools/index takes one rather than two. A signature
    invented by a person reading a plan produces Nextflow that fails at launch with
    "declares N inputs but was called with M arguments", which is a slow way to learn
    something a test can say instantly.
    """
    import re

    mismatched = []
    for contract in registry.all():
        block = re.search(
            r"^    input:\n(.*?)^    output:",
            (VENDOR / f"{contract.nf_include}.nf").read_text(),
            re.S | re.M,
        )
        declared = [
            line
            for line in block.group(1).splitlines()
            if line.strip() and not line.strip().startswith("//")
        ]
        if len(declared) != len(contract.input_signature()):
            mismatched.append(
                f"{contract.id}: contract declares {len(contract.input_signature())} "
                f"inputs, module declares {len(declared)}"
            )
    assert mismatched == [], "\n".join(mismatched)


def test_contract_containers_match_the_vendored_modules(registry):
    """A container reference invented by a planner is the failure this project exists to stop.

    The contract must agree with the module actually on disk. If nf-core bumps a
    container upstream, this is what says the contract has gone stale rather than
    letting a build claim a reproducibility it does not have.
    """
    import re

    mismatched = []
    for contract in registry.all():
        main_nf = VENDOR / f"{contract.nf_include}.nf"
        directive = re.search(r"container\s+\"(.*?)\"", main_nf.read_text(), re.S)
        declared = re.findall(r"'([^']+)'", directive.group(1))[-1]
        if declared != contract.container:
            mismatched.append(f"{contract.id}: contract={contract.container} module={declared}")
    assert mismatched == [], "\n".join(mismatched)


def test_an_index_is_not_a_bam(registry):
    """samtools/index emits a sidecar, and nf-core's process emits no BAM at all.

    Declaring it `alignment.bam[indexed]` is what let the router hand featureCounts a
    `.bai` — audit 2026-08-03, C4. The resolver no longer believes it, but the contract
    must not assert it either.
    """
    index = registry.get("nf-core/samtools/index@1.21.0")
    assert [p.type_id for p in index.produces] == ["alignment.bai"]


def test_a_multi_want_goal_wires_each_consumer_correctly(registry):
    """Every pre-audit test used a single `want`, which is why last-writer-wins survived."""
    from mendel_resolver.resolve import resolve

    loaded = layers.load(ROOT / "examples")
    goal = Goal(
        have=[
            GoalInput(type_id="fastq.reads"),
            GoalInput(type_id="annotation.gtf"),
            GoalInput(type_id="genome.fasta"),
        ],
        want=["counts.matrix", "alignment.bai"],
        constraints={"required_states": {"counts.matrix": ["gene_level"]}},
    )
    ir = resolve(goal, loaded.registry, loaded.rules)
    fed_by = {
        e.to_node: e.from_node for e in ir.edges if e.to_node == "subread_featurecounts"
    }
    assert fed_by["subread_featurecounts"] == "samtools_sort"
    assert "samtools_index" in [n.id for n in ir.nodes]


def test_every_shipped_rule_can_fire(registry):
    """`KNOWN_DEAD_RULES` used to live here, recording two rules that had never once run.

    It is gone because loading is now the check: `RuleTable.load` validates every decision
    against the registry, the vocabulary and the measurement declarations, and refuses a
    table it cannot satisfy. So the assertion is simply that the shipped table loads —
    a dead rule can no longer be shipped to be recorded.
    """
    table = layers.load(ROOT / "examples").rules
    assert [d.decides.key() for d in table.decisions] == [
        "param:strandedness",
        "producer_of:alignment.bam",
    ]

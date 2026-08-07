import pathlib

import pytest
from mendel_resolver import layers
from mendel_resolver.goal import Goal, GoalInput
from mendel_resolver.router import route

ROOT = pathlib.Path(__file__).parent.parent
VENDOR = ROOT / "vendor"


@pytest.fixture
def registry():
    return layers.load(ROOT / "registry").registry


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


def test_contracts_agree_with_the_vendored_modules(registry):
    """Arity and containers, now asked of the conformance checker rather than re-parsed.

    Both properties were tested here first, each with its own regex over `main.nf`, and
    both are earned: `nf_inputs` must have one entry per channel the process declares —
    written after guessing wrong twice, since multiqc takes one tuple of six paths rather
    than six channels and samtools/index takes one rather than two — and a container
    reference invented by a planner is the failure this project exists to stop.

    They moved into `M0102`/`M0103` and `M0107` because two parsers for one file format is
    the drift this project keeps being bitten by, and the copy that lived here had already
    drifted: it terminated the input block on `output:` alone, where a module ending in
    `script:` or `stub:` would have parsed as having no inputs, and it took `[-1]` of the
    quoted container alternatives, which raises IndexError on a module that names its image
    directly rather than through nf-core's singularity/docker ternary.

    The checker also runs inside `mendel build` on whatever registry the user loaded, which
    a test over `examples/` never could.
    """
    from mendel_compiler.conformance import check

    disagreements = [
        d.render() for d in check(registry, VENDOR) if d.code in {"M0102", "M0103", "M0107"}
    ]
    assert disagreements == [], "\n".join(disagreements)


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

    loaded = layers.load(ROOT / "registry")
    goal = Goal(
        have=[
            GoalInput(type_id="fastq.reads"),
            GoalInput(type_id="annotation.gtf"),
            GoalInput(type_id="genome.fasta"),
        ],
        want=["counts.matrix", "alignment.bai"],
        constraints={"required_states": {"counts.matrix": ["gene_level"]}},
    )
    ir = resolve(
        goal,
        loaded.registry,
        loaded.rules,
        loaded.measurements,
        vocabulary=loaded.vocabulary,
    )
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
    table = layers.load(ROOT / "registry").rules
    # One decision, and it is a real one. `param:strandedness` used to sit beside it and
    # was a translation the module already performs — see Plan 1.5.
    assert [d.decides.key() for d in table.decisions] == ["producer_of:alignment.bam"]

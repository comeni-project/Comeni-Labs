"""An aggregator sees every sample at once, not one at a time.

Plan 5B phase 4.3, and it is the mirror of 4.2. That phase stopped a one-item reference channel
capping a whole run; this one stops a step that exists to *combine* samples from running once
per sample.

**MULTIQC is the case.** It consumes `qc.report` from every sample, and without `.collect()` the
emitted workflow says `MULTIQC(ch_qc_report)` — one invocation per sample, producing N reports
where the entire point of the tool is to produce one.

**Nothing is broken today**, and that is worth stating rather than leaving implied: MULTIQC is
not on the RNA-seq spine, so no goal in this repository routes to it. The contract is in the
registry and would have been wrong the moment one did — which is exactly the kind of defect that
is cheap now and expensive later.

`InputPort.cardinality` (now `many`) existed, defaulted to `"1"`, and had **one reader**:
`validate.py`, counting *wires*. That is a different question — how many edges may target a
port, not how many items it consumes. A port can take one wire carrying a channel of five
hundred reports.
"""


import pytest
from comeni_core.artifact.pipeline import Pipeline
from comeni_core.plan.draft import DraftEdge, DraftGraph, DraftNode
from comeni_core.plan.tiers import Grain
from mendel_compiler.emit import emit
from mendel_resolver import layers
from mendel_resolver.materialise import goal_of, ir_of
from support.paths import ROOT

FASTQC = "nf-core/fastqc@0.12.1"
MULTIQC = "nf-core/multiqc@1.35"


@pytest.fixture(scope="module")
def stack():
    return layers.load(ROOT / "registry")


def _aggregating() -> DraftGraph:
    """FASTQC per sample, MULTIQC over all of them. **Drawn rather than resolved**, because no
    goal in this repository routes to MULTIQC — which is the whole reason this was latent."""
    return DraftGraph(
        nodes=[
            DraftNode(id="qc", contract_id=FASTQC),
            DraftNode(id="summary", contract_id=MULTIQC),
        ],
        edges=[
            DraftEdge(from_node="qc", from_port="zip", to_node="summary", to_port="reports")
        ],
    )


def _emitted(stack) -> str:
    graph = _aggregating()
    ir = ir_of(graph, stack)
    pipeline = Pipeline.of(
        ir, stack.registry, stack.vocabulary, stack.measurements, stack.paths,
        goal=goal_of(graph, stack),
    )
    return emit(pipeline)


def test_the_contract_declares_the_fan_in(stack):
    """The registry is where this is said, and it is said once.

    If this fails, every assertion below is about the emitter when the finding is about the
    contract — which is the wrong place to be looking.
    """
    contract = stack.registry.get(MULTIQC)
    port = next(p for p in contract.consumes if p.name == "reports")
    assert port.grain is Grain.STUDY and port.many


def test_an_aggregator_is_called_over_the_whole_channel(stack):
    """**The defect.** `MULTIQC(FASTQC.out.html)` runs once per sample and produces N reports.

    Watched failing by dropping `.collect()` from `_port_expression`, which emits exactly that.
    """
    workflow = _emitted(stack)
    call = next(one for one in workflow.splitlines() if "MULTIQC(" in one)
    assert ".collect()" in call, (
        f"MULTIQC is called per sample: {call.strip()}\n"
        f"  It consumes qc.report from every sample and produces one report; without "
        f"`.collect()` it runs N times and produces N."
    )


def test_the_gathered_reports_fill_the_modules_one_tuple(stack):
    """**#507.** nf-core/multiqc 1.35 takes one `tuple val(meta), path(files)` and four optional
    paths. A bare `.collect()` flattened every sample's meta in among the files, and the run died
    with "Input tuple does not match tuple declaration". The reports are gathered without their
    metas, under one meta for the call, and padded with the contract's four empty paths.
    """
    workflow = _emitted(stack)
    call = next(one for one in workflow.splitlines() if "MULTIQC(" in one)
    assert ".map { it -> it[1] }.collect()" in call, call.strip()
    assert ".map { files -> [ [id: 'summary'], files ] }" in call, call.strip()
    assert call.rstrip().endswith(".map { it -> it + [[], [], [], []] })"), call.strip()


def test_a_one_item_port_is_not_collected(stack):
    """The other half, and the one that would make this vacuous if it failed.

    FASTQC takes one sample's reads per invocation. Collecting there would gather every
    sample into one call — the opposite defect, and the reason this is a per-port property
    rather than a per-step one.
    """
    workflow = _emitted(stack)
    call = next(one for one in workflow.splitlines() if "FASTQC(" in one)
    assert ".collect()" not in call, f"FASTQC gathers every sample into one call: {call.strip()}"


def test_the_default_is_one_item_and_grain_is_closed():
    """`cardinality` was a bare `str` once, and `"one"`, `"2"` and a typo all meant *many* by
    falling through. Its successor (#466) is a closed `grain` and a boolean `many`: a number would
    have to mean *invoked once per N items*, which nothing in Nextflow's channel algebra does
    without a `buffer` whose size is a pipeline's decision rather than a contract's.
    """
    from comeni_core.declared.contract import InputPort

    port = InputPort(name="x", type_id="a.b")
    assert port.grain is None and port.many is False
    with pytest.raises(ValueError):
        InputPort(name="x", type_id="a.b", grain="lane")


def test_the_spine_is_unchanged_by_this(stack):
    """Nothing on the RNA-seq spine gathers, so phase 4.3 must move no byte of it.

    A fan-in that quietly appeared on a per-sample port would be 4.2's defect inverted — every
    sample folded into one invocation — and it would pass a determinism test, because the golden
    would move once and then be regenerated.
    """
    golden = (ROOT / "tests" / "golden" / "spine" / "main.nf").read_text()
    assert ".collect()" not in golden.replace("params.input.collect", "")


# ── every kind of data reaches the aggregator (#435) ──────────────────────────────────────────


def _reads_and_assemblies(stack):
    from mendel_resolver.goal import Goal, GoalInput
    from mendel_resolver.resolve import resolve

    goal = Goal(have=[GoalInput(type_id="fastq.reads"), GoalInput(type_id="assembly.fasta")],
                want=["qc.report"],
                constraints={"required_states": {"qc.report": ["aggregated"]}})
    return goal, resolve(goal, stack.registry, stack.rules, stack.measurements,
                         vocabulary=stack.vocabulary)


def _feeding(ir) -> list[tuple[str, str]]:
    return sorted((e.from_node, e.from_port) for e in ir.edges
                  if e.to_node == "multiqc" and e.to_port == "reports")


def test_the_aggregator_gathers_a_report_on_each_kind_of_data(stack):
    """**#435.** FastQC and QUAST share the role `qc_per_sample`, so routing MULTIQC's reports
    took one and the other never ran. One producer per kind of data: FastQC on the reads, QUAST
    on the assemblies, and QUAST's first report only, not all three of its outputs."""
    _, ir = _reads_and_assemblies(stack)
    assert _feeding(ir) == [("fastqc", "zip"), ("quast", "results")]
    assert [n.id for n in ir.nodes].index("multiqc") == len(ir.nodes) - 1
    assert not [d for d in ir.decisions if d.subject == "source:reports"]


def test_the_gathered_reports_are_mixed_into_one_call(stack):
    from comeni_core.artifact.pipeline import Pipeline

    goal, ir = _reads_and_assemblies(stack)
    workflow = emit(Pipeline.of(ir, stack.registry, stack.vocabulary, stack.measurements,
                                stack.paths, goal=goal))
    call = next(one for one in workflow.splitlines() if "MULTIQC(" in one)
    assert "FASTQC.out.zip.mix(QUAST.out.results)" in call, call.strip()


def test_one_kind_of_data_still_routes_one_producer(stack):
    """With reads alone QUAST could only be reached through an assembler, which competes with
    FastQC on the reads and loses; no assembler is added to feed a report."""
    from mendel_resolver.goal import Goal, GoalInput
    from mendel_resolver.resolve import resolve

    goal = Goal(have=[GoalInput(type_id="fastq.reads")], want=["qc.report"],
                constraints={"required_states": {"qc.report": ["aggregated"]}})
    ir = resolve(goal, stack.registry, stack.rules, stack.measurements,
                 vocabulary=stack.vocabulary)
    assert _feeding(ir) == [("fastqc", "zip")]

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

`InputPort.cardinality` existed, defaulted to `"1"`, and had **one reader**: `validate.py`,
counting *wires*. That is a different question — how many edges may target a port, not how many
items it consumes. A port can take one wire carrying a channel of five hundred reports.
"""

import pathlib

import pytest
from comeni_core.artifact.pipeline import Pipeline
from comeni_core.declared.contract import Cardinality
from comeni_core.plan.draft import DraftEdge, DraftGraph, DraftNode
from mendel_compiler.emit import emit
from mendel_resolver import layers
from mendel_resolver.materialise import goal_of, ir_of

ROOT = pathlib.Path(__file__).parent.parent

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
    assert port.cardinality is Cardinality.MANY


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


def test_a_one_item_port_is_not_collected(stack):
    """The other half, and the one that would make this vacuous if it failed.

    FASTQC takes one sample's reads per invocation. Collecting there would gather every
    sample into one call — the opposite defect, and the reason this is a per-port property
    rather than a per-step one.
    """
    workflow = _emitted(stack)
    call = next(one for one in workflow.splitlines() if "FASTQC(" in one)
    assert ".collect()" not in call, f"FASTQC gathers every sample into one call: {call.strip()}"


def test_the_default_is_one_and_the_vocabulary_is_closed():
    """`cardinality` was a bare `str` defaulting to `"1"`, and its one reader compared against
    that literal — so `"one"`, `"2"` and a typo all meant *many* by falling through.

    Two members, and a third is refused until somebody has a case: a number here would have to
    mean *invoked once per N items*, which nothing in Nextflow's channel algebra does without a
    `buffer` whose size is a pipeline's decision rather than a contract's.
    """
    from comeni_core.declared.contract import InputPort

    assert InputPort(name="x", type_id="a.b").cardinality is Cardinality.ONE
    assert [c.value for c in Cardinality] == ["1", "*"]
    with pytest.raises(ValueError):
        InputPort(name="x", type_id="a.b", cardinality="2")


def test_the_spine_is_unchanged_by_this(stack):
    """Nothing on the RNA-seq spine gathers, so phase 4.3 must move no byte of it.

    A fan-in that quietly appeared on a per-sample port would be 4.2's defect inverted — every
    sample folded into one invocation — and it would pass a determinism test, because the golden
    would move once and then be regenerated.
    """
    golden = (ROOT / "tests" / "golden" / "spine" / "main.nf").read_text()
    assert ".collect()" not in golden.replace("params.input.collect", "")

import pathlib

from comeni_core.ir import IREdge, IRNode, PipelineIR, ResolvedValue, Tier
from comeni_core.registry import Registry
from comeni_core.vocabulary import Vocabulary
from mendel_compiler.emit import emit

ROOT = pathlib.Path(__file__).parent.parent.parent.parent


def _registry():
    return Registry.load(
        ROOT / "examples" / "contracts", Vocabulary.load(ROOT / "examples" / "vocabularies")
    )


def _ir():
    return PipelineIR(
        nodes=[
            IRNode(id="trimgalore", contract_id="nf-core/trimgalore@0.6.10"),
            IRNode(
                id="star_align",
                contract_id="nf-core/star/align@1.11.0",
                params={
                    "seq_platform": ResolvedValue(
                        value="illumina", tier=Tier.CONVENTION, reason="contract default"
                    )
                },
            ),
        ],
        edges=[
            IREdge(
                from_node="trimgalore",
                from_port="reads",
                to_node="star_align",
                to_port="reads",
                type_id="fastq.reads",
                states=frozenset({"trimmed"}),
            )
        ],
    )


def test_emits_include_statements_for_every_node():
    source = emit(_ir(), _registry())
    assert "include { TRIMGALORE } from './modules/nf-core/trimgalore/main'" in source
    assert "include { STAR_ALIGN } from './modules/nf-core/star/align/main'" in source


def test_emits_workflow_block_wiring_edges():
    source = emit(_ir(), _registry())
    assert "workflow {" in source
    assert "TRIMGALORE(ch_reads)" in source
    assert "STAR_ALIGN(TRIMGALORE.out.reads" in source


def test_annotates_each_param_with_its_tier():
    source = emit(_ir(), _registry())
    assert "// tier 2 (none): contract default" in source
    assert "params.star_align_seq_platform = 'illumina'" in source


def test_emission_is_byte_identical_across_runs():
    assert emit(_ir(), _registry()) == emit(_ir(), _registry())


def test_carries_its_intended_purpose_statement():
    """The .nf travels alone. It has to say what it is without the rest of the repo."""
    source = emit(_ir(), _registry())
    assert "It is not a diagnostic" in source
    assert "must be validated by" in source


def test_matches_the_golden_file():
    golden = ROOT / "tests" / "golden" / "spine" / "main.nf"
    assert emit(_ir(), _registry()) == golden.read_text()

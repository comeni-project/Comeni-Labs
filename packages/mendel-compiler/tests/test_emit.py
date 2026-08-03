import pathlib

from comeni_core.ir import IREdge, IRNode, PipelineIR, ResolvedValue, Tier
from comeni_core.registry import Registry
from comeni_core.vocabulary import Vocabulary
from mendel_compiler.emit import emit

ROOT = pathlib.Path(__file__).parent.parent.parent.parent


def _vocab():
    return Vocabulary.load(ROOT / "examples" / "vocabularies")


def _registry():
    return Registry.load(ROOT / "examples" / "contracts", _vocab())


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
    source = emit(_ir(), _registry(), _vocab())
    assert "include { TRIMGALORE } from './modules/nf-core/trimgalore/main'" in source
    assert "include { STAR_ALIGN } from './modules/nf-core/star/align/main'" in source


def test_emits_workflow_block_wiring_edges():
    source = emit(_ir(), _registry(), _vocab())
    assert "workflow {" in source
    assert "TRIMGALORE(ch_reads)" in source
    assert "STAR_ALIGN(TRIMGALORE.out.reads" in source


def test_annotates_each_param_with_its_tier():
    source = emit(_ir(), _registry(), _vocab())
    assert "// tier 2 (none): contract default" in source
    assert "params.star_align_seq_platform = 'illumina'" in source


def test_emission_is_byte_identical_across_runs():
    assert emit(_ir(), _registry(), _vocab()) == emit(_ir(), _registry(), _vocab())


def test_carries_its_intended_purpose_statement():
    """The .nf travels alone. It has to say what it is without the rest of the repo."""
    source = emit(_ir(), _registry(), _vocab())
    assert "It is not a diagnostic" in source
    assert "must be validated by" in source


def test_matches_the_golden_file():
    golden = ROOT / "tests" / "golden" / "spine" / "main.nf"
    assert emit(_ir(), _registry(), _vocab()) == golden.read_text()


def test_call_arity_follows_the_declared_signature():
    """One contract port is not one process argument, and assuming so emits bad Nextflow.

    star/align declares four inputs for two ports; the two it does not model are an
    empty tuple and a plain value.
    """
    source = emit(_ir(), _registry(), _vocab())
    call = next(line for line in source.splitlines() if "STAR_ALIGN(" in line).strip()
    assert call == (
        "STAR_ALIGN(TRIMGALORE.out.reads, ch_star, Channel.value([[:], []]), false)"
    ), call


def test_empty_placeholders_match_the_declared_tuple_width():
    """Nextflow matches tuple arity: a 2-tuple handed to a 3-tuple input is a null path."""
    from comeni_core.contract import NfInput
    from mendel_compiler.emit import _argument

    assert _argument(_ir(), _registry(), "star_align", NfInput(empty=3)) == (
        "Channel.value([[:], [], []])"
    )


def test_a_none_value_renders_as_null_not_a_string():
    from mendel_compiler.emit import _render_literal

    assert _render_literal(None) == "null"
    assert _render_literal(None) != "'None'"


def test_config_declares_every_entry_parameter_as_null():
    """The pipeline describes a shape; the laboratory supplies the data. Invariant 15."""
    from mendel_compiler.emit import emit_config, entry_params

    config = emit_config(_ir(), _registry(), _vocab())
    for name in entry_params(_ir(), _registry(), _vocab()):
        assert f"{name} = null" in config
    assert "stub_data" in config

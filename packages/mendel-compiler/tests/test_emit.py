import pathlib

from comeni_core.ir import IREdge, IRNode, PipelineIR, ResolvedValue, Tier
from mendel_compiler.emit import emit
from mendel_resolver import layers

ROOT = pathlib.Path(__file__).parent.parent.parent.parent


def _vocab():
    return layers.load(ROOT / "registry").vocabulary


def _registry():
    return layers.load(ROOT / "registry").registry


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
    assert "TRIMGALORE(ch_fastq_reads)" in source
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


def test_the_config_matches_its_golden_file():
    """`nextflow.config` is the second output surface and it had no golden.

    `main.nf` goes through Jinja and looks like output; this file is assembled by f-strings and
    looks like plumbing, which is the same reason root C found it "also injectable" as the
    surface nobody was guarding. A28's `emitted:` digests catch that it *changed*, against what
    a build itself produced. Only a golden catches that it changed *to something wrong*, as a
    diff a person reads before merge — and `ext.args` is where a wrong flag would appear, which
    reaches the tool while every digest stays happy.
    """
    from mendel_compiler.emit import emit_config

    golden = ROOT / "tests" / "golden" / "spine" / "nextflow.config"
    assert emit_config(_ir(), _registry(), _vocab()) == golden.read_text()


def test_call_arity_follows_the_declared_signature():
    """One contract port is not one process argument, and assuming so emits bad Nextflow.

    star/align declares four inputs for three ports; the one it does not model is a plain
    value.

    The third argument used to be `Channel.value([[:], []])` — an empty tuple where the
    annotation belongs, while `ch_annotation_gtf` sat in the same workflow feeding
    featureCounts. Issue #8. `-stub-run` could never catch it, because nf-core stubs do
    not read their inputs, so the call was as green as a correct one.
    """
    source = emit(_ir(), _registry(), _vocab())
    call = next(line for line in source.splitlines() if "STAR_ALIGN(" in line).strip()
    assert call == (
        "STAR_ALIGN(TRIMGALORE.out.reads, ch_genome_index_star, ch_annotation_gtf, false)"
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


def test_a_quote_in_a_value_does_not_break_or_escape_the_literal():
    """Unescaped, "it's fine" is a Groovy syntax error and a crafted value runs code.

    In Plan 2 these values come from a model reading a user's prompt, so this is the
    boundary between goal text and executed Groovy.
    """
    from mendel_compiler.emit import _render_literal

    assert _render_literal("it's fine") == r"'it\'s fine'"
    assert _render_literal(r"a\b") == r"'a\\b'"
    injected = _render_literal("x'; new File('/etc/passwd').text; //")
    assert injected.count("'") == injected.count(r"\'") + 2


def test_a_control_character_is_refused():
    import pytest
    from mendel_compiler.emit import _render_literal

    with pytest.raises(ValueError, match="control character"):
        _render_literal("bad\nvalue")

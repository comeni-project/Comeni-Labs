"""Every input the emitted pipeline declares is fed by something real.

`gate stub: PASS` cannot prove this. nf-core stubs never read their inputs, so a process
handed `Channel.value([[:], []])` where a genome should be executes exactly as happily as
one handed a genome. The DAG was correct and the analysis was impossible.

`test_contract_input_signatures_match_the_vendored_modules` cannot prove it either: it
checks arity, and an empty placeholder has the same arity as a real channel.
"""

import pathlib

import pytest
from mendel_resolver import layers
from mendel_resolver.goal import Goal, GoalInput
from mendel_resolver.resolve import resolve

ROOT = pathlib.Path(__file__).parent.parent


@pytest.fixture
def loaded():
    return layers.load(ROOT / "examples")


@pytest.fixture
def spine(loaded):
    goal = Goal(
        have=[
            GoalInput(type_id="fastq.reads"),
            GoalInput(type_id="annotation.gtf"),
            GoalInput(type_id="genome.fasta"),
        ],
        want=["counts.matrix"],
        constraints={"required_states": {"counts.matrix": ["gene_level"]}},
        profile=loaded.measurements.profile({"read_length": 150, "strandedness": "reverse"}),
    )
    return resolve(goal, loaded.registry, loaded.rules)


def test_every_empty_placeholder_says_why_it_is_empty(loaded):
    """`NfInput.empty` was doing two different jobs, and nothing told them apart.

    "this input models nothing in the type system" and "we have not wired this yet" look
    identical in YAML and identical in the emitted Groovy. One is a design decision and
    the other is a bug, and the second shipped twice. Requiring a sentence turns the next
    one into something a reviewer reads rather than something a real run discovers.
    """
    unexplained = [
        f"{contract.id} input {position}"
        for contract in loaded.registry.all()
        for position, spec in enumerate(contract.input_signature())
        if spec.empty and not spec.because
    ]
    assert unexplained == [], (
        "an empty placeholder must say why the type system does not model this input: "
        + ", ".join(unexplained)
    )


def test_a_declared_type_is_never_replaced_by_a_placeholder(loaded):
    """The specific failure: `genome.fasta` exists, and STAR was handed an empty tuple.

    If a contract consumes a port, that port must appear in `nf_inputs`. A declared port
    that no channel carries is a port the router satisfied and the compiler discarded.
    """
    dropped = []
    for contract in loaded.registry.all():
        wired = {name for spec in contract.input_signature() for name in spec.ports}
        for port in contract.consumes:
            if port.name not in wired:
                dropped.append(f"{contract.id}.{port.name}")
    assert dropped == [], (
        "these ports are consumed but never reach the process call: " + ", ".join(dropped)
    )


def test_the_genome_is_a_declared_type(loaded):
    """You cannot build an aligner index without one."""
    assert "genome.fasta" in loaded.vocabulary.types
    assert loaded.vocabulary.entry_channels["genome.fasta"]


def test_both_index_builders_consume_the_genome(loaded):
    for contract_id in ("nf-core/star/genomegenerate@1.11.0", "nf-core/hisat2/build@2.2.2"):
        consumed = {p.type_id for p in loaded.registry.get(contract_id).consumes}
        assert "genome.fasta" in consumed, contract_id


def test_star_align_consumes_the_annotation(loaded):
    """It was handed an empty tuple while the GTF sat in the same workflow."""
    star = loaded.registry.get("nf-core/star/align@1.11.0")
    assert "annotation.gtf" in {p.type_id for p in star.consumes}


def test_the_emitted_workflow_feeds_the_genome_to_star(spine, loaded):
    from mendel_compiler.emit import emit

    source = emit(spine, loaded.registry, loaded.vocabulary)
    call = next(line for line in source.splitlines() if "STAR_GENOMEGENERATE(" in line)
    assert "ch_genome_fasta" in call, call
    assert "[[:], []]" not in call, call


def test_the_emitted_workflow_feeds_the_annotation_to_star_align(spine, loaded):
    from mendel_compiler.emit import emit

    source = emit(spine, loaded.registry, loaded.vocabulary)
    call = next(line for line in source.splitlines() if "STAR_ALIGN(" in line)
    assert "ch_annotation_gtf" in call, call


def test_the_config_asks_the_laboratory_for_a_genome(spine, loaded):
    from mendel_compiler.emit import emit_config, entry_params

    assert "fasta" in entry_params(spine, loaded.registry, loaded.vocabulary)
    assert "fasta = null" in emit_config(spine, loaded.registry, loaded.vocabulary)


def test_a_test_profile_is_emitted_when_every_input_declares_test_data(spine, loaded):
    """Gate.TEST runs `-profile test`. Until now nothing emitted one, so it could not pass.

    The URLs come from the vocabulary, for the same reason `entry_channel` does: the
    compiler has no built-in idea what a FASTQ is, and a type a lab invents has to be able
    to bring its own.
    """
    from mendel_compiler.emit import emit_config

    config = emit_config(spine, loaded.registry, loaded.vocabulary)
    assert "test {" in config
    assert "nf-core/test-datasets" in config


def test_the_test_profile_is_labelled_as_a_smoke_test(spine, loaded):
    """It proves the pipeline runs on a known dataset. It does not prove the analysis."""
    from mendel_compiler.emit import emit_config

    config = emit_config(spine, loaded.registry, loaded.vocabulary)
    assert "smoke test" in config.lower()
    assert "not" in config.lower() and "correct" in config.lower()


def test_a_contract_can_declare_flags_its_module_always_needs(loaded):
    """Not a decision, so it carries no tier. `nf_inputs` says which channels a module
    takes; this says which flags it takes. Both are "how is this called", and neither is
    "what should be decided" — giving it a tier would dilute what a tier means."""
    star = loaded.registry.get("nf-core/star/align@1.11.0")
    assert "--readFilesCommand zcat" in star.ext_args


def test_ext_args_reaches_the_emitted_config(spine, loaded):
    """STAR died on real data with 'wrong read ID line format' and a binary offending
    line: TrimGalore emits .fq.gz and nothing told STAR to decompress."""
    from mendel_compiler.emit import emit_config

    config = emit_config(spine, loaded.registry, loaded.vocabulary)
    assert "process {" in config
    assert "withName: STAR_ALIGN" in config
    assert "ext.args = '--readFilesCommand zcat'" in config


def test_a_module_with_no_ext_args_gets_no_withname_block(spine, loaded):
    """An empty block is noise, and noise in generated config is how nobody reads it."""
    from mendel_compiler.emit import emit_config

    config = emit_config(spine, loaded.registry, loaded.vocabulary)
    assert "withName: TRIMGALORE" not in config


def test_ext_args_is_escaped_like_any_other_literal():
    """These reach Groovy. An unescaped quote is a syntax error and a crafted value runs."""
    from mendel_compiler.emit import _render_literal

    assert "\\'" in _render_literal("--x 'quoted'")

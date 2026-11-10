"""A test becomes a small pipeline of exactly this tool, against the real registry."""

import pytest
from comeni_core.declared.tooltest import ToolTest
from mendel_compiler.emit import emit, emit_config, entry_params
from mendel_forge.testing import TESTDATA_BASE, build_test_pipeline, module_files, params_for
from mendel_resolver import layers
from support.paths import REGISTRY


@pytest.fixture(scope="module")
def stack():
    return layers.load(REGISTRY)


STAR_SETTINGS = {"seq_platform": "ILLUMINA"}


def _fastqc(**changes) -> ToolTest:
    return ToolTest(**{"contract": "nf-core/fastqc@0.12.1", "name": "one", "data_commit": "abc",
                       "inputs": {"reads": ["a/b_1.fq.gz", "a/b_2.fq.gz"]},
                       "expect": [{"port": "zip", "pattern": "*.zip"}], **changes})


def _star(**changes) -> ToolTest:
    return ToolTest(**{"contract": "nf-core/star/align@2.7.11b", "name": "one",
                       "data_commit": "abc",
                       "inputs": {"reads": ["a/b.fq.gz"], "index": ["a/star"], "gtf": ["a/c.gtf"]},
                       "params": STAR_SETTINGS,
                       "expect": [{"port": "bam", "pattern": "*.bam"}], **changes})


def test_a_test_pipeline_runs_only_this_tool(stack):
    pipeline = build_test_pipeline(_fastqc(), stack)
    assert [s.module.contract_id for s in pipeline.steps] == ["nf-core/fastqc@0.12.1"]
    assert "FASTQC" in emit(pipeline)


def test_the_urls_are_pinned_to_the_commit(stack):
    test = _fastqc()
    pipeline = build_test_pipeline(test, stack)
    base = TESTDATA_BASE.format(commit="abc")
    assert "/abc/" in base
    urls = [base + "a/b_1.fq.gz", base + "a/b_2.fq.gz"]
    assert list(params_for(test, pipeline).values()) == [urls]


@pytest.mark.parametrize("make", [_fastqc, _star])
def test_params_fill_exactly_the_pipelines_holes(stack, make):
    test = make()
    pipeline = build_test_pipeline(test, stack)
    assert sorted(params_for(test, pipeline)) == entry_params(pipeline)


def test_a_setup_step_feeds_the_tool(stack):
    generate = next(c for c in stack.registry.all() if c.nf_process == "STAR_GENOMEGENERATE")
    output = generate.produces[0].name
    fed = {p.name: [f"a/{p.name}"] for p in generate.consumes}
    test = _star(inputs={"reads": ["a/b.fq.gz"], "gtf": ["a/c.gtf"]},
                 setup=[{"tool": generate.id, "inputs": fed, "feeds": {output: "index"}}])
    pipeline = build_test_pipeline(test, stack)
    assert [s.id for s in pipeline.steps] == ["setup_1", "tool"]
    wired = next(i for i in pipeline.steps[1].inputs if i.port == "index")
    assert "setup_1" in str(wired.source)
    assert sorted(params_for(test, pipeline)) == entry_params(pipeline)


def test_a_setup_naming_a_port_that_does_not_exist_is_refused(stack):
    generate = next(c for c in stack.registry.all() if c.nf_process == "STAR_GENOMEGENERATE")
    test = _star(inputs={}, setup=[{"tool": generate.id, "feeds": {"nope": "index"}}])
    with pytest.raises(ValueError, match="MF0515"):
        build_test_pipeline(test, stack)


def test_the_bundle_holds_each_steps_module(stack):
    pipeline = build_test_pipeline(_fastqc(), stack)
    names = [name for name, _ in module_files(pipeline, stack)]
    assert "modules/nf-core/fastqc/main.nf" in names
    assert emit_config(pipeline)


QUAST = (REGISTRY.parent / "packages/comeni-core/tests/fixtures/constraints/quast.yml").read_text()
OVERLAY = {
    "assembly.family.yml": "declares: family\nid: assembly\ndescription: Genome assemblies\n",
    "assembly.fasta.yml": "declares: vocabulary\nid: assembly.fasta\nstates: []\n",
    "annotation.gff.yml": "declares: vocabulary\nid: annotation.gff\nstates: []\nscope: run\n",
    "quast.contract.yml": "declares: contract\n" + QUAST,
}


def test_an_optional_input_a_test_gives_no_data_is_off(tmp_path):
    """#470: `fasta: []` became a hole nothing could fill (MF0515 nothing feeds tool_fasta)."""
    for name, body in OVERLAY.items():
        (tmp_path / name).write_text(body)
    stack = layers.load([REGISTRY, tmp_path])
    test = ToolTest(contract="nf-core/quast@5.3.0", name="noref", data_commit="abc",
                    inputs={"consensus": ["a/contigs.fa"], "fasta": []},
                    expect=[{"port": "results", "pattern": "*"}])
    pipeline = build_test_pipeline(test, stack)
    assert [c.name for c in pipeline.channels] == ["tool_consensus"]
    assert sorted(params_for(test, pipeline)) == entry_params(pipeline)
    quast = pipeline.steps[0]
    assert [(r.port, r.state) for r in quast.input_states] == [("fasta", "off"), ("gff", "off")]
    assert emit(pipeline).count("Channel.value([[:], []])") == 2


# ── shared slots and accepted types (#464) ────────────────────────────────────────────────

FIXTURES = REGISTRY.parent / "packages/comeni-core/tests/fixtures/constraints"


def _overlaid(tmp_path, contract_file: str, extra: dict[str, str]):
    files = {"x.contract.yml": "declares: contract\n" + (FIXTURES / contract_file).read_text(),
             "roles.yml": "declares: role\nroles:\n  - {id: calling, explain: x}\n", **extra}
    for name, body in files.items():
        (tmp_path / name).write_text(body)
    return layers.load([REGISTRY, tmp_path])


def _family(name: str) -> str:
    return f"declares: family\nid: {name}\ndescription: {name}\n"


def _type(type_id: str, scope: str = "run") -> str:
    return f"declares: vocabulary\nid: {type_id}\nstates: []\nscope: {scope}\n"


SALMON_TYPES = {"salmon.family.yml": _family("salmon"),
                "transcripts.family.yml": _family("transcripts"),
                "salmon.index.yml": _type("salmon.index"),
                "salmon.quant.yml": _type("salmon.quant", "sample"),
                "transcripts.fasta.yml": _type("transcripts.fasta")}


def _salmon_test(**changes) -> ToolTest:
    return ToolTest(**{"contract": "nf-core/salmon/quant@1.10.3", "name": "bam",
                       "data_commit": "abc",
                       "inputs": {"reads": ["a/b.bam"], "transcript_fasta": ["a/t.fa"]},
                       "expect": [{"port": "results", "pattern": "*"}], **changes})


def test_a_test_says_which_type_an_accepts_port_gets(tmp_path):
    stack = _overlaid(tmp_path, "salmon_quant.yml", SALMON_TYPES)
    pipeline = build_test_pipeline(_salmon_test(types={"reads": "alignment.bam"}), stack)
    reads = next(c for c in pipeline.channels if c.name == "tool_reads")
    assert reads.type_id == "alignment.bam"
    first = build_test_pipeline(_salmon_test(inputs={"reads": ["a/b.fq.gz"], "index": ["a/i"]}),
                                stack)
    assert next(c for c in first.channels if c.name == "tool_reads").type_id == "fastq.reads"


def test_a_test_naming_a_type_the_port_does_not_accept_is_refused(tmp_path):
    stack = _overlaid(tmp_path, "salmon_quant.yml", SALMON_TYPES)
    with pytest.raises(ValueError, match="MF0515.*alignment.cram"):
        build_test_pipeline(_salmon_test(types={"reads": "alignment.cram"}), stack)


def test_a_test_may_leave_out_a_port_in_a_shared_slot(tmp_path):
    """gatk with no intervals: the tuple still has its position, as `[]`."""
    extra = {f"{f}.family.yml": _family(f) for f in ("regions", "dragstr", "variants")}
    extra |= {"regions.bed.yml": _type("regions.bed"),
              "dragstr.model.yml": _type("dragstr.model", "sample"),
              "variants.vcf.yml": _type("variants.vcf", "sample"),
              "variants.tbi.yml": _type("variants.tbi")}
    stack = _overlaid(tmp_path, "gatk4_haplotypecaller.yml", extra)
    test = ToolTest(contract="nf-core/gatk4/haplotypecaller@4.6.1", name="nointervals",
                    data_commit="abc",
                    inputs={"input": ["a/b.bam"], "input_index": ["a/b.bam.bai"],
                            "dragstr_model": ["a/m.txt"], "intervals": []},
                    expect=[{"port": "vcf", "pattern": "*.vcf.gz"}])
    pipeline = build_test_pipeline(test, stack)
    call = next(line for line in emit(pipeline).splitlines()
                if line.strip().startswith("GATK4_HAPLOTYPECALLER("))
    assert "[ meta, a, b, [], c ]" in call
    assert "tool_intervals" not in {c.name for c in pipeline.channels}


def test_an_input_that_accepts_several_types_round_trips_through_items():
    """An `accepts` port has no type of its own; re-forging dumped an empty `type_id`."""
    from comeni_core import yaml_strict
    from comeni_core.declared.contract import ModuleContract, Provenance
    from mendel_forge.forging.values import contract_of, items_of

    contract = ModuleContract.model_validate(yaml_strict.load(FIXTURES / "salmon_quant.yml"))
    back = contract_of(items_of(contract), contract.id, contract.provenance)
    assert back.consumes == contract.consumes
    assert back.constraints == contract.constraints
    assert isinstance(back.provenance, Provenance)

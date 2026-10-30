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
    return ToolTest(**{"contract": "nf-core/star/align@2.7.11b", "name": "one", "data_commit": "abc",
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
    assert list(params_for(test, pipeline).values()) == [[base + "a/b_1.fq.gz", base + "a/b_2.fq.gz"]]


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

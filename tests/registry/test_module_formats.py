"""What a module's output patterns say about its file formats."""

import pytest
from mendel_compiler.modulespec import formats_of


@pytest.mark.parametrize(("pattern", "formats"), [
    ('path("${prefix}.tsv")', ["tsv"]),
    ('path("*.html")', ["html"]),
    ('path("*.{bai,csi,crai}")', ["bai", "crai", "csi"]),
    ('path("${prefix}.${extension}.{crai,csi,bai}")', ["bai", "crai", "csi"]),
    ('path("*fastq.gz")', ["fastq"]),
    ("path('*.SJ.out.tab')", ["tab"]),
    ('path("hisat2")', ["folder"]),
    ('path("*_data")', ["folder"]),
    ('path("*.bam")', ["bam"]),
])
def test_a_pattern_names_its_formats(pattern, formats):
    assert formats_of(pattern) == formats


def test_a_value_is_not_a_file():
    assert formats_of('eval("fastqc --version")') == []


def test_every_registry_module_says_a_format_for_each_declared_output():
    from comeni_core.declared.module import key_of
    from mendel_compiler.conformance import module_path
    from mendel_compiler.modulespec import ModuleSpec
    from mendel_resolver import layers
    from support.paths import ROOT

    stack = layers.load(ROOT / "registry")
    contracts = stack.registry.all()
    assert contracts
    for contract in contracts:
        path = module_path(contract, stack.modules)
        assert path is not None, key_of(contract.nf_include)
        spec = ModuleSpec.parse(path)
        for port in contract.produces:
            assert spec.emit_formats[port.name], f"{contract.id}#{port.name}"


def test_a_format_the_module_does_not_write_is_refused(tmp_path):
    from comeni_core.declared.contract import OutputPort
    from mendel_compiler.conformance import against
    from mendel_compiler.modulespec import ModuleSpec
    from mendel_resolver import layers
    from support.paths import ROOT

    stack = layers.load(ROOT / "registry")
    fastqc = next(c for c in stack.registry.all() if "/fastqc@" in c.id)
    from mendel_compiler.conformance import module_path
    path = module_path(fastqc, stack.modules)
    spec = ModuleSpec.parse(path)
    ok = fastqc.model_copy(update={"produces": [
        OutputPort(name="zip", type_id="qc.report", format=["zip"])]})
    wrong = fastqc.model_copy(update={"produces": [
        OutputPort(name="zip", type_id="qc.report", format=["tsv"])]})
    assert "MD0109" not in [d.code for d in against(ok, spec, path)]
    assert "MD0109" in [d.code for d in against(wrong, spec, path)]

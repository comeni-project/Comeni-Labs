"""Each check, against a contract doctored to fail exactly it.

A conformance checker verified only on contracts that pass is a checker nobody has seen
work. Every test here breaks one thing and asserts one code.
"""

import pathlib

import pytest
from comeni_core.declared.module import Module
from comeni_core.declared.registry import Registry
from mendel_compiler.conformance import check
from mendel_resolver import layers
from support.paths import ROOT

_KIND_OF_DIR = {
    "contracts": "contract",
    "vocabularies": "vocabulary",
    "measurements": "measurement",
    "roles": "role",
    "rules": "rule",
}


def _declared(path, body: str) -> str:
    """Prepend what a fixture's file declares, derived from the directory it is written into.

    Since comeni-registry#1 a declared file says what it is and the loader no longer reads the
    directory. These fixtures still *write* into kind-named directories, which is now only a
    habit — and the habit is what tells this helper which line to add, so the fixtures keep
    their shape and their subject stays readable.

    Idempotent, because several fixtures write a file twice to check that something changed.
    """
    path = pathlib.Path(path)
    # Walk *ancestors*, not just the immediate parent: real layers nest, and
    # `tools/nf-core/fastqc/contract.yml` sits two levels down from the directory that
    # names it.
    kind = next(
        (_KIND_OF_DIR[p.name] for p in path.parents if p.name in _KIND_OF_DIR), None
    )
    if kind is None or body.lstrip().startswith("declares:"):
        return body
    header = f"declares: {kind}\n"
    if kind in ("vocabulary", "measurement"):
        header += f"id: {path.name.removesuffix('.yml').removesuffix('.yaml')}\n"
    return header + body

VENDOR = ROOT / "registry"
MODULES = dict(Module.load(ROOT / "registry").entries)



@pytest.fixture
def registry():
    return layers.load(ROOT / "registry").registry


def _doctored(registry: Registry, contract_id: str, **changes) -> Registry:
    """The registry with one contract altered. Returns a copy; the fixture is untouched."""
    contracts = dict(registry.contracts)
    contracts[contract_id] = contracts[contract_id].model_copy(update=changes)
    return Registry(contracts=contracts)


def codes(diagnostics) -> set[str]:
    return {d.code for d in diagnostics}


def test_the_shipped_registry_is_conformant(registry):
    """The baseline. If this fails, the checker or the contracts are wrong — and after
    Plan 1.5 the contracts have been run against real data, so suspect the checker."""
    assert check(registry, MODULES) == []


def test_M0101_a_process_name_that_does_not_exist(registry):
    doctored = _doctored(registry, "nf-core/star/align@1.11.0", nf_process="STAR_ALIGNN")
    assert "MD0101" in codes(check(doctored, MODULES))


def test_M0102_wrong_number_of_channels(registry):
    from comeni_core.declared.contract import NfInput

    doctored = _doctored(
        registry, "nf-core/star/align@1.11.0", nf_inputs=[NfInput(ports=["reads"])]
    )
    assert "MD0102" in codes(check(doctored, MODULES))


def test_M0103_an_empty_placeholder_of_the_wrong_width(registry):
    from comeni_core.declared.contract import NfInput

    sort = registry.get("nf-core/samtools/sort@1.21.0")
    wrong = [
        NfInput(ports=["bam"]),
        NfInput(empty=2, because="deliberately wrong width for this test"),
        NfInput(literal="bai"),
    ]
    doctored = _doctored(registry, sort.id, nf_inputs=wrong)
    diagnostics = check(doctored, MODULES)
    assert "MD0103" in codes(diagnostics)
    assert "3" in next(d for d in diagnostics if d.code == "MD0103").detail


def test_M0105_an_output_the_module_does_not_emit(registry):
    from comeni_core.declared.contract import OutputPort

    doctored = _doctored(
        registry,
        "nf-core/star/align@1.11.0",
        produces=[OutputPort(name="bams", type_id="alignment.bam")],
    )
    diagnostics = check(doctored, MODULES)
    assert "MD0105" in codes(diagnostics)
    # The fix must name what the module *does* emit, or it is half a diagnostic.
    assert "bam" in next(d for d in diagnostics if d.code == "MD0105").fix


def test_M0107_a_container_that_has_drifted(registry):
    doctored = _doctored(
        registry, "nf-core/star/align@1.11.0", container="quay.io/biocontainers/star:2.7.0"
    )
    assert "MD0107" in codes(check(doctored, MODULES))


def test_a_contract_with_no_module_source_is_unverified_not_broken(registry, tmp_path):
    """A laboratory wrapping a bare container has no nf-core-style module directory.
    That is legitimate, and must not fail a build."""
    diagnostics = check(registry, {})
    assert codes(diagnostics) == {"MD0100"}
    assert all("unverified" in d.summary for d in diagnostics)


def test_diagnostics_are_sorted(registry):
    """Byte-identical output is a hard requirement, and these are printed."""
    doctored = _doctored(registry, "nf-core/star/align@1.11.0", nf_process="NOPE")
    twice = [check(doctored, MODULES), check(doctored, MODULES)]
    assert [d.model_dump() for d in twice[0]] == [d.model_dump() for d in twice[1]]


def test_every_diagnostic_says_what_to_write_instead(registry):
    """The rule from the design record: a diagnostic that does not say what to write is
    half a diagnostic."""
    doctored = _doctored(registry, "nf-core/star/align@1.11.0", nf_process="NOPE")
    assert all(d.fix for d in check(doctored, MODULES))


def test_M0104_a_placeholder_where_the_module_wants_a_file(registry):
    """The missing genome. STAR_GENOMEGENERATE slot 0 is path(fasta), and for weeks the
    contract supplied an empty tuple — through a green suite and a passing stub gate."""
    from comeni_core.declared.contract import NfInput

    doctored = _doctored(
        registry,
        "nf-core/star/genomegenerate@1.11.0",
        consumes=registry.get("nf-core/star/genomegenerate@1.11.0").consumes[1:],
        nf_inputs=[NfInput(empty=2), NfInput(ports=["gtf"])],
    )
    diagnostics = check(doctored, MODULES)
    assert "MD0104" in codes(diagnostics)
    detail = next(d for d in diagnostics if d.code == "MD0104").detail
    assert "fasta" in detail
    assert "genome" in detail.lower(), "meta.yml's description must reach the diagnostic"


def test_M0104_names_the_file_element_not_the_meta_map(registry):
    """`tuple val(meta), path(fasta)` documents both `meta` and `fasta` in meta.yml, and
    `meta` comes first. Reporting "path(meta)" with the Groovy-map description would send
    the reader looking for a sample map where a genome is missing."""
    from comeni_core.declared.contract import NfInput

    doctored = _doctored(
        registry,
        "nf-core/star/genomegenerate@1.11.0",
        consumes=registry.get("nf-core/star/genomegenerate@1.11.0").consumes[1:],
        nf_inputs=[NfInput(empty=2), NfInput(ports=["gtf"])],
    )
    summary = next(d for d in check(doctored, MODULES) if d.code == "MD0104").summary
    assert "path(fasta)" in summary
    assert "path(meta)" not in summary


def test_M0104_is_satisfied_by_saying_why(registry):
    """samtools/sort genuinely does not need a reference to write BAM. The check is not
    'never use a placeholder' — it is 'say which of the two this is'."""
    assert "MD0104" not in codes(check(registry, MODULES))


def test_M0106_a_meta_key_the_module_reads_that_nothing_sets(registry, tmp_path):
    """The -s 0 defect, made unrepresentable. featurecounts reads meta.strandedness; if no
    declared measurement carries it, the module silently uses its default."""
    from comeni_core.declared.measurement import MeasurementRegistry

    measured = tmp_path / "measurements"
    measured.mkdir()
    (measured / "read_length.yml").write_text(
        _declared(
            measured / "read_length.yml",
            "kind: integer\nminimum: 1\n"))
    thin = MeasurementRegistry.load(tmp_path)

    diagnostics = check(registry, MODULES, measurements=thin)
    assert "MD0106" in codes(diagnostics)
    assert any("strandedness" in d.summary for d in diagnostics if d.code == "MD0106")


def test_M0106_is_satisfied_by_the_shipped_measurements(registry):
    """strandedness declares meta_key: strandedness, and paired declares single_end."""
    measurements = layers.load(ROOT / "registry").measurements
    assert "MD0106" not in codes(check(registry, MODULES, measurements=measurements))


def test_M0106_the_other_direction_a_meta_key_nobody_reads(registry, tmp_path):
    """A declaration with no effect. Dead code, in data."""
    from comeni_core.declared.measurement import MeasurementRegistry

    measured = tmp_path / "measurements"
    measured.mkdir()
    (measured / "strandedness.yml").write_text(
        _declared(
            measured / "strandedness.yml",
            "kind: enum\nvalues: [forward, reverse, unstranded]\n"
        "describes: fastq.reads\nmeta_key: strandedness\n")
    )
    (measured / "paired.yml").write_text(
        _declared(
            measured / "paired.yml",
            "kind: boolean\ndescribes: fastq.reads\nmeta_key: single_end\n")
    )
    (measured / "moon_phase.yml").write_text(
        _declared(
            measured / "moon_phase.yml",
            "kind: enum\nvalues: [waxing, waning]\ndescribes: fastq.reads\nmeta_key: moon_phase\n")
    )
    measurements = MeasurementRegistry.load(tmp_path)

    diagnostics = check(registry, MODULES, measurements=measurements)
    dead = [d for d in diagnostics if d.code == "MD0106" and "moon_phase" in d.summary]
    assert dead, "a meta_key no module reads should be reported"
    assert "no module in this registry reads" in dead[0].summary


def test_M0106_claims_nothing_dead_when_the_modules_could_not_be_read(registry, tmp_path):
    """"No module reads this meta_key" is a claim about every module, so it needs every
    module. A lab wrapping bare containers has no module source at all — every declared
    key would look dead, and since MD0106 blocks, the build would be refused over an
    inference drawn from nothing."""
    measurements = layers.load(ROOT / "registry").measurements
    diagnostics = check(registry, {}, measurements=measurements)
    assert codes(diagnostics) == {"MD0100"}


def test_M0106_does_not_fire_without_a_measurement_registry(registry):
    """`check` is called from places that have no measurements. Silence beats a wrong
    answer."""
    assert "MD0106" not in codes(check(registry, MODULES))


def test_M0106_ignores_meta_id_and_secondary_meta_variables(registry):
    """`meta.id` is set by every entry channel, and `meta2.id` belongs to a reference
    channel rather than the reads. Demanding a measurement for either would be noise, and
    a check that cries wolf is a check people switch off."""
    measurements = layers.load(ROOT / "registry").measurements
    diagnostics = [
        d for d in check(registry, MODULES, measurements=measurements) if d.code == "MD0106"
    ]
    assert not any(d.summary.split("'")[1] == "id" for d in diagnostics if "'" in d.summary)

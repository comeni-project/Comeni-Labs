"""Each check, against a contract doctored to fail exactly it.

A conformance checker verified only on contracts that pass is a checker nobody has seen
work. Every test here breaks one thing and asserts one code.
"""

import pathlib

import pytest
from comeni_core.registry import Registry
from mendel_compiler.conformance import check
from mendel_resolver import layers

ROOT = pathlib.Path(__file__).parent.parent
VENDOR = ROOT / "vendor"


@pytest.fixture
def registry():
    return layers.load(ROOT / "examples").registry


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
    assert check(registry, VENDOR) == []


def test_M0101_a_process_name_that_does_not_exist(registry):
    doctored = _doctored(registry, "nf-core/star/align@1.11.0", nf_process="STAR_ALIGNN")
    assert "M0101" in codes(check(doctored, VENDOR))


def test_M0102_wrong_number_of_channels(registry):
    from comeni_core.contract import NfInput

    doctored = _doctored(
        registry, "nf-core/star/align@1.11.0", nf_inputs=[NfInput(ports=["reads"])]
    )
    assert "M0102" in codes(check(doctored, VENDOR))


def test_M0103_an_empty_placeholder_of_the_wrong_width(registry):
    from comeni_core.contract import NfInput

    sort = registry.get("nf-core/samtools/sort@1.21.0")
    wrong = [
        NfInput(ports=["bam"]),
        NfInput(empty=2, because="deliberately wrong width for this test"),
        NfInput(literal="bai"),
    ]
    doctored = _doctored(registry, sort.id, nf_inputs=wrong)
    diagnostics = check(doctored, VENDOR)
    assert "M0103" in codes(diagnostics)
    assert "3" in next(d for d in diagnostics if d.code == "M0103").detail


def test_M0105_an_output_the_module_does_not_emit(registry):
    from comeni_core.contract import OutputPort

    doctored = _doctored(
        registry,
        "nf-core/star/align@1.11.0",
        produces=[OutputPort(name="bams", type_id="alignment.bam")],
    )
    diagnostics = check(doctored, VENDOR)
    assert "M0105" in codes(diagnostics)
    # The fix must name what the module *does* emit, or it is half a diagnostic.
    assert "bam" in next(d for d in diagnostics if d.code == "M0105").fix


def test_M0107_a_container_that_has_drifted(registry):
    doctored = _doctored(
        registry, "nf-core/star/align@1.11.0", container="quay.io/biocontainers/star:2.7.0"
    )
    assert "M0107" in codes(check(doctored, VENDOR))


def test_a_contract_with_no_module_source_is_unverified_not_broken(registry, tmp_path):
    """A laboratory wrapping a bare container has no nf-core-style module directory.
    That is legitimate, and must not fail a build."""
    diagnostics = check(registry, tmp_path)
    assert codes(diagnostics) == {"M0100"}
    assert all("unverified" in d.summary for d in diagnostics)


def test_diagnostics_are_sorted(registry):
    """Byte-identical output is a hard requirement, and these are printed."""
    doctored = _doctored(registry, "nf-core/star/align@1.11.0", nf_process="NOPE")
    twice = [check(doctored, VENDOR), check(doctored, VENDOR)]
    assert [d.model_dump() for d in twice[0]] == [d.model_dump() for d in twice[1]]


def test_every_diagnostic_says_what_to_write_instead(registry):
    """The rule from the design record: a diagnostic that does not say what to write is
    half a diagnostic."""
    doctored = _doctored(registry, "nf-core/star/align@1.11.0", nf_process="NOPE")
    assert all(d.fix for d in check(doctored, VENDOR))


def test_M0104_a_placeholder_where_the_module_wants_a_file(registry):
    """The missing genome. STAR_GENOMEGENERATE slot 0 is path(fasta), and for weeks the
    contract supplied an empty tuple — through a green suite and a passing stub gate."""
    from comeni_core.contract import NfInput

    doctored = _doctored(
        registry,
        "nf-core/star/genomegenerate@1.11.0",
        consumes=registry.get("nf-core/star/genomegenerate@1.11.0").consumes[1:],
        nf_inputs=[NfInput(empty=2), NfInput(ports=["gtf"])],
    )
    diagnostics = check(doctored, VENDOR)
    assert "M0104" in codes(diagnostics)
    detail = next(d for d in diagnostics if d.code == "M0104").detail
    assert "fasta" in detail
    assert "genome" in detail.lower(), "meta.yml's description must reach the diagnostic"


def test_M0104_names_the_file_element_not_the_meta_map(registry):
    """`tuple val(meta), path(fasta)` documents both `meta` and `fasta` in meta.yml, and
    `meta` comes first. Reporting "path(meta)" with the Groovy-map description would send
    the reader looking for a sample map where a genome is missing."""
    from comeni_core.contract import NfInput

    doctored = _doctored(
        registry,
        "nf-core/star/genomegenerate@1.11.0",
        consumes=registry.get("nf-core/star/genomegenerate@1.11.0").consumes[1:],
        nf_inputs=[NfInput(empty=2), NfInput(ports=["gtf"])],
    )
    summary = next(d for d in check(doctored, VENDOR) if d.code == "M0104").summary
    assert "path(fasta)" in summary
    assert "path(meta)" not in summary


def test_M0104_is_satisfied_by_saying_why(registry):
    """samtools/sort genuinely does not need a reference to write BAM. The check is not
    'never use a placeholder' — it is 'say which of the two this is'."""
    assert "M0104" not in codes(check(registry, VENDOR))


def test_M0106_a_meta_key_the_module_reads_that_nothing_sets(registry, tmp_path):
    """The -s 0 defect, made unrepresentable. featurecounts reads meta.strandedness; if no
    declared measurement carries it, the module silently uses its default."""
    from comeni_core.measurement import MeasurementRegistry

    (tmp_path / "read_length.yml").write_text("kind: integer\nminimum: 1\n")
    thin = MeasurementRegistry.load(tmp_path)

    diagnostics = check(registry, VENDOR, measurements=thin)
    assert "M0106" in codes(diagnostics)
    assert any("strandedness" in d.summary for d in diagnostics if d.code == "M0106")


def test_M0106_is_satisfied_by_the_shipped_measurements(registry):
    """strandedness declares meta_key: strandedness, and paired declares single_end."""
    measurements = layers.load(ROOT / "examples").measurements
    assert "M0106" not in codes(check(registry, VENDOR, measurements=measurements))


def test_M0106_the_other_direction_a_meta_key_nobody_reads(registry, tmp_path):
    """A declaration with no effect. Dead code, in data."""
    from comeni_core.measurement import MeasurementRegistry

    (tmp_path / "strandedness.yml").write_text(
        "kind: enum\nvalues: [forward, reverse, unstranded]\n"
        "describes: fastq.reads\nmeta_key: strandedness\n"
    )
    (tmp_path / "paired.yml").write_text(
        "kind: boolean\ndescribes: fastq.reads\nmeta_key: single_end\n"
    )
    (tmp_path / "moon_phase.yml").write_text(
        "kind: enum\nvalues: [waxing, waning]\ndescribes: fastq.reads\nmeta_key: moon_phase\n"
    )
    measurements = MeasurementRegistry.load(tmp_path)

    diagnostics = check(registry, VENDOR, measurements=measurements)
    dead = [d for d in diagnostics if d.code == "M0106" and "moon_phase" in d.summary]
    assert dead, "a meta_key no module reads should be reported"
    assert "no module in this registry reads" in dead[0].summary


def test_M0106_claims_nothing_dead_when_the_modules_could_not_be_read(registry, tmp_path):
    """"No module reads this meta_key" is a claim about every module, so it needs every
    module. A lab wrapping bare containers has no module source at all — every declared
    key would look dead, and since M0106 blocks, the build would be refused over an
    inference drawn from nothing."""
    measurements = layers.load(ROOT / "examples").measurements
    diagnostics = check(registry, tmp_path, measurements=measurements)
    assert codes(diagnostics) == {"M0100"}


def test_M0106_does_not_fire_without_a_measurement_registry(registry):
    """`check` is called from places that have no measurements. Silence beats a wrong
    answer."""
    assert "M0106" not in codes(check(registry, VENDOR))


def test_M0106_ignores_meta_id_and_secondary_meta_variables(registry):
    """`meta.id` is set by every entry channel, and `meta2.id` belongs to a reference
    channel rather than the reads. Demanding a measurement for either would be noise, and
    a check that cries wolf is a check people switch off."""
    measurements = layers.load(ROOT / "examples").measurements
    diagnostics = [
        d for d in check(registry, VENDOR, measurements=measurements) if d.code == "M0106"
    ]
    assert not any(d.summary.split("'")[1] == "id" for d in diagnostics if "'" in d.summary)

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

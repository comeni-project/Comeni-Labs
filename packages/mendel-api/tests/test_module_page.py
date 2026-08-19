"""One contract, the module it describes, and everything pointing at it."""

import pytest
from mendel_api.services import module_page


def _fastqc():
    return module_page.read("nf-core/fastqc@0.12.1")


def test_it_reports_how_many_emit_channels_are_declared():
    """One of two things the design says nothing else surfaces. It is a NUMBER, not a
    warning: a contract may legitimately model a subset — star/align emits nineteen and the
    spine needs one."""
    page = _fastqc()

    assert page.emits_total is not None and page.emits_total > 0
    assert page.emits_declared is not None
    assert page.emits_declared <= page.emits_total


def test_a_module_that_cannot_be_read_reports_nothing_rather_than_zero(monkeypatch, tmp_path):
    """`0 of 0` for a module nobody opened is the same falsehood as folding `skipped` into
    `matching`.

    **It cannot use a real contract.** Measured: every contract in this registry has a
    vendored `main.nf`, and the two `comeni/` ones are `unverifiable` because no *source
    adapter* can re-fetch them — which is a different condition from the module file being
    absent. An earlier draft of this test asserted they were the same and would have failed.
    """
    monkeypatch.setattr(module_page.settings, "source_root", tmp_path)

    page = _fastqc()

    assert page.emits_total is None
    assert page.emits_declared is None
    assert page.source_path is None


def test_pipeline_pins_are_absent_rather_than_zero():
    """Nothing stores pipelines. Reporting `0` would say *no pipeline uses this*, which is a
    different and unverified claim — spec §3.3."""
    assert _fastqc().pipeline_pins is None


def test_the_right_column_names_what_points_at_the_module():
    page = module_page.read("nf-core/samtools/index@1.21.0")

    # Something must produce a BAM for the index to consume, or this registry is broken and
    # the assertion below would pass by being empty.
    assert page.inputs_from, "samtools/index consumes a BAM and something produces one"
    assert page.id not in page.competes_with, "a module does not compete with itself"


def test_rules_aiming_at_a_role_are_found_by_role():
    """Measured: this registry has one tier-3 decision, and its `decides.of` is `alignment`.
    A contract with that role must see it; one without must not."""
    aligner = next(
        (c for c in module_page.contracts_with_role("alignment")), None
    )
    assert aligner is not None, "this registry declares a rule aiming at `alignment`"
    assert module_page.read(aligner).rules_aiming

    assert not _fastqc().rules_aiming, "fastqc is qc_per_sample, not alignment"


def test_an_unknown_contract_is_refused():
    with pytest.raises(ValueError, match="not in this registry"):
        module_page.read("nf-core/nonsense@1.0.0")

"""One contract, and everything anything can say about it.

The claim this file holds is spec §3.2's: a report that listed only what it checked would read
as a clean bill of health over an unchecked half.
"""

from pathlib import Path

from mendel_forge import drift, ops

ROOT = Path(__file__).resolve().parents[3]
FASTQC = "tools/nf-core/fastqc/contract.yml"


def _report(registry: Path, contract_id: str = "nf-core/fastqc@0.12.1") -> ops.DriftReport:
    return ops.drift(
        ops.DriftRequest(
            contract_id=contract_id, registry_root=registry, source_root=ROOT / "registry"
        )
    )


def test_a_clean_contract_agrees_on_every_field_it_can_check():
    report = _report(ROOT / "registry")
    assert report.verdict is drift.Verdict.AGREES
    assert [c.field for c in report.checks if not c.agrees] == []
    assert {c.field for c in report.checks} == {"nf_process", "nf_include", "container"}


def test_every_field_is_in_exactly_one_group():
    report = _report(ROOT / "registry")
    checked = {c.field for c in report.checks}
    structural = {f for f, facts in drift.FIELDS.items() if facts.codes and not facts.by_value}
    unchecked = {u.field for u in report.unchecked}
    assert checked | structural | unchecked == set(drift.FIELDS)
    assert checked & unchecked == set()


def test_the_unchecked_group_names_the_routing_fields_nothing_verifies():
    report = _report(ROOT / "registry")
    routing = {u.field for u in report.unchecked if u.impact is drift.Impact.ROUTES}
    assert routing == {"id", "consumes", "roles", "priority"}


def test_a_value_drift_is_reported_with_both_values_and_the_source_line(broken_registry):
    registry = broken_registry(FASTQC, "nf_process: FASTQC", "nf_process: WRONG")
    report = _report(registry)
    moved = [c for c in report.checks if not c.agrees]
    assert [c.field for c in moved] == ["nf_process"]
    assert moved[0].registry_says == "WRONG"
    assert moved[0].source_says == "FASTQC"
    assert moved[0].locator == "tools/nf-core/fastqc/module/main.nf:1"
    assert moved[0].impact is drift.Impact.BUILDS


def test_a_value_drift_on_a_building_field_does_not_reroute(broken_registry):
    registry = broken_registry(FASTQC, "nf_process: FASTQC", "nf_process: WRONG")
    report = _report(registry)
    # `nf_process` is also MD0101, and a refusing diagnostic outranks a field — which is the
    # right answer here rather than an inconvenience: a contract naming a process the module
    # does not declare cannot be emitted at all.
    assert report.verdict is drift.Verdict.BREAKS
    assert "MD0101" in [d.code for d in report.conformance]


def test_a_structural_drift_is_reported_even_though_no_value_check_sees_it(broken_registry):
    registry = broken_registry(FASTQC, "name: zip", "name: nonesuch")
    report = _report(registry)
    assert [c.field for c in report.checks if not c.agrees] == []
    assert "MD0105" in [d.code for d in report.conformance]
    assert report.verdict is drift.Verdict.BREAKS


def test_a_contract_no_source_can_reread_says_so_rather_than_agreeing():
    report = _report(ROOT / "registry", "comeni/profile/fastqc@0.12.1")
    assert report.verifiable is False
    assert report.checks == []
    # Phase 4 §3.4: unverifiable and "no module file" are different conditions, and this
    # contract is the one that proves it — nothing can re-draft it AND its module reads.
    assert report.module_read is True
    assert report.conformance == []

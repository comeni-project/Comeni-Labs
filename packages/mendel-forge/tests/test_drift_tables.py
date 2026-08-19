"""The two tables, and the two ways they can decay.

A table like this is wrong the first time somebody adds a field or a diagnostic and does not
come back here — which is exactly the failure `2026-08-18-plan-3.md` §4.7 predicted for a
hardcoded verdict. Both halves are total, and both totality checks are tests.
"""

from comeni_core.declared.contract import ModuleContract
from comeni_core.diagnostics import REGISTRY
from mendel_forge import drift
from mendel_forge.assemble import DERIVED_FIELDS


def test_every_contract_field_is_classified():
    assert set(drift.FIELDS) == set(ModuleContract.model_fields)


def test_every_conformance_code_is_claimed_or_declared_not_a_field():
    conformance_codes = {code for code, spec in REGISTRY.items() if spec.concern == "conformance"}
    assert conformance_codes, "no conformance codes found — the filter is wrong"
    claimed = {code for facts in drift.FIELDS.values() for code in facts.codes}
    unaccounted = conformance_codes - claimed - set(drift.NOT_A_FIELD)
    assert unaccounted == set()


def test_the_value_group_is_exactly_what_a_source_states():
    assert {field for field, facts in drift.FIELDS.items() if facts.by_value} == {
        field for _, field in DERIVED_FIELDS
    }


def test_three_of_the_five_routing_fields_are_checked_by_nothing():
    """The uncomfortable one, and it is asserted rather than left in prose — spec §3.2.

    If a checker ever learns to verify a port's `type_id`, this fails and the sentence on the
    screen has to change with it.
    """
    unchecked = {f for f, facts in drift.FIELDS.items() if not facts.checked}
    routes = {f for f, facts in drift.FIELDS.items() if facts.impact is drift.Impact.ROUTES}
    assert routes & unchecked == {"id", "consumes", "roles", "priority"}


def test_a_refusing_diagnostic_beats_every_field():
    assert drift.verdict_for(disagreeing=["container"], refusing=["MD0105"]) is drift.Verdict.BREAKS


def test_a_routing_field_reroutes_and_a_building_field_does_not():
    assert drift.verdict_for(disagreeing=["roles"], refusing=[]) is drift.Verdict.REROUTES
    assert drift.verdict_for(disagreeing=["container"], refusing=[]) is drift.Verdict.REBUILDS


def test_the_worst_impact_wins_when_several_moved():
    got = drift.verdict_for(disagreeing=["container", "roles"], refusing=[])
    assert got is drift.Verdict.REROUTES


def test_nothing_moving_agrees():
    assert drift.verdict_for(disagreeing=[], refusing=[]) is drift.Verdict.AGREES


def test_the_sentence_names_the_field_and_says_what_it_means():
    said = drift.sentence_for(drift.Verdict.REBUILDS, disagreeing=["container"], refusing=[])
    assert "container" in said
    assert "routes" in said.lower()

"""A reply is checked against the registry and the module before anything is stored (§3)."""

from pathlib import Path

import pytest
import yaml
from comeni_core.declared.contract import ModuleContract
from mendel_compiler.modulespec import ModuleSpec
from mendel_forge.forging.validate import check_items, known, pending_used
from mendel_forge.forging.values import items_of
from mendel_resolver import layers
from support.paths import REGISTRY

STAR_NF = Path(__file__).parent / "fixtures" / "nf-core" / "star" / "align" / "main.nf"


@pytest.fixture(scope="module")
def stack():
    return layers.load(REGISTRY)


@pytest.fixture(scope="module")
def star_items():
    data = yaml.safe_load((REGISTRY / "tools/nf-core/star/align/contract.yml").read_text())
    data.pop("declares")
    return items_of(ModuleContract(**data))


def _codes(problems) -> list[str]:
    return [p.code for p in problems]


def test_star_aligns_registry_items_pass(stack, star_items):
    assert check_items(star_items, known(stack), ModuleSpec.parse(STAR_NF)) == []


def test_an_unknown_type_is_MF0507(stack, star_items):
    items = {**star_items, "contract:input:reads": {**star_items["contract:input:reads"],
                                                    "type_id": "nothing.here"}}
    assert _codes(check_items(items, known(stack), ModuleSpec.parse(STAR_NF))) == ["MF0507"]


def test_a_type_proposed_in_this_adaptation_is_known(stack, star_items):
    items = {**star_items,
             "contract:input:reads": {**star_items["contract:input:reads"],
                 "type_id": "new.type", "state_required_conventional": []},
             "vocabulary:type:new.type": {"id": "new.type", "states": []}}
    assert check_items(items, known(stack), ModuleSpec.parse(STAR_NF)) == []


def test_a_type_in_another_adaptations_unassembled_draft_is_unknown(stack, star_items):
    """Review Focus 3: only assembled drafts are pending; anything else is simply unknown."""
    items = {**star_items, "contract:input:reads": {**star_items["contract:input:reads"],
                                                    "type_id": "draft.only"}}
    assert _codes(check_items(items, known(stack), ModuleSpec.parse(STAR_NF))) == ["MF0507"]


def test_a_pending_type_is_accepted_and_flagged(stack, star_items):
    items = {**star_items, "contract:input:reads": {**star_items["contract:input:reads"],
                                                    "type_id": "genome.index.bwa",
                                                    "state_required_conventional": []}}
    seen = known(stack, pending=frozenset({"genome.index.bwa"}))
    assert check_items(items, seen, ModuleSpec.parse(STAR_NF)) == []
    assert pending_used(items, seen) == {"genome.index.bwa"}


def test_a_port_main_nf_lacks_is_MF0508(stack, star_items):
    items = {**star_items, "contract:input:ghost": {"position": 9, "name": "ghost",
                                                    "type_id": "fastq.reads"}}
    assert _codes(check_items(items, known(stack), ModuleSpec.parse(STAR_NF))) == ["MF0508"]


def test_a_param_routed_nowhere_is_MF0509(stack, star_items):
    items = {**star_items, "parameters:param:loose": {"position": 9, "name": "loose",
                                                      "via": "ext", "default": 1}}
    assert _codes(check_items(items, known(stack), ModuleSpec.parse(STAR_NF))) == ["MF0509"]


def test_a_port_whose_name_differs_from_its_key_is_MF0508(stack, star_items):
    items = {**star_items, "contract:output:bam": {**star_items["contract:output:bam"],
                                                   "name": "bamm"}}
    assert _codes(check_items(items, known(stack), ModuleSpec.parse(STAR_NF))) == ["MF0508"]


def test_undeclared_output_state_requires_explicit_new_option(stack):
    question = {"asks": "What does this report hold?", "options": [
        {"id": "qc.report::assembly", "label": "assembly report", "because": "assembly metrics"}]}
    items = {"questions:output_type:report": question}
    assert _codes(check_items(items, known(stack), ModuleSpec.parse(STAR_NF))) == ["MF0507"]
    question["options"][0]["new"] = True
    assert check_items(items, known(stack), ModuleSpec.parse(STAR_NF)) == []


def test_an_undeclared_contract_state_requires_an_answer_or_vocabulary(stack, star_items):
    items = {**star_items, "contract:output:bam": {**star_items["contract:output:bam"],
                                                 "type_id": "alignment.bam::new_state"}}
    assert _codes(check_items(items, known(stack), ModuleSpec.parse(STAR_NF))) == ["MF0507"]
    items["questions:output_type:bam"] = {"choice": "alignment.bam::new_state", "new": True}
    assert check_items(items, known(stack), ModuleSpec.parse(STAR_NF)) == []
    del items["questions:output_type:bam"]
    items["vocabulary:type:alignment.bam"] = {"id": "alignment.bam", "add_states": ["new_state"]}
    assert check_items(items, known(stack), ModuleSpec.parse(STAR_NF)) == []


def test_approved_new_answers_permit_draft_references_without_declaring_vocabulary(
    stack, star_items,
):
    items = {**star_items,
        "questions:role": {"choice": "custom_alignment", "new": True},
        "questions:output_type:bam": {"choice": "alignment.custom::reviewed", "new": True},
        "contract:process": {**star_items["contract:process"], "roles": ["custom_alignment"]},
        "contract:output:bam": {**star_items["contract:output:bam"],
                                "type_id": "alignment.custom::reviewed"}}
    assert check_items(items, known(stack), ModuleSpec.parse(STAR_NF)) == []
    assert not any(key.startswith("vocabulary:") for key in items)


def test_an_offered_new_option_does_not_grant_contract_reference_permission(stack, star_items):
    items = {**star_items,
        "questions:output_type:bam": {"asks": "What is it?", "options": [
            {"id": "alignment.custom", "label": "Custom", "because": "New", "new": True}]},
        "contract:output:bam": {**star_items["contract:output:bam"], "type_id": "alignment.custom"}}
    assert "MF0507" in _codes(check_items(items, known(stack), ModuleSpec.parse(STAR_NF)))


@pytest.mark.parametrize("status", ["approved", "proposed", "reopened", "removed", "rejected"])
def test_only_approved_answer_values_reach_the_draft_permission_check(status):
    from mendel_forge.forging.model import Adaptation, Item, Revision
    from mendel_forge.forging.validate import validation_items

    key = "questions:output_type:bam"
    state = Adaptation(items={key: Item(key=key, piece="questions", status=status,
        revisions=(Revision(n=1, move="answer", actor="person",
                            value={"choice": "alignment.custom", "new": True}),))})
    assert (key in validation_items(state)) is (status == "approved")


def test_explicit_port_state_fields_require_the_same_permission_as_signatures(stack, star_items):
    items = {**star_items, "contract:output:bam": {**star_items["contract:output:bam"],
        "type_id": "alignment.bam", "state": ["reviewed"]}}
    assert "MF0507" in _codes(check_items(items, known(stack), ModuleSpec.parse(STAR_NF)))
    items["questions:output_type:bam"] = {"choice": "alignment.bam::reviewed", "new": True}
    assert check_items(items, known(stack), ModuleSpec.parse(STAR_NF)) == []


def test_input_alternatives_use_the_same_approved_new_type_permission(stack, star_items):
    items = {**star_items, "contract:input:reads": {"name": "reads", "position": 0,
        "accepts": [{"type_id": "fastq.reads"}, {"type_id": "alignment.custom"}]}}
    assert "MF0507" in _codes(check_items(items, known(stack), ModuleSpec.parse(STAR_NF)))
    items["questions:input_type:reads"] = {"choice": "alignment.custom", "new": True}
    assert check_items(items, known(stack), ModuleSpec.parse(STAR_NF)) == []

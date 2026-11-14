"""An item's value is the registry's own model, so the registry's checks are forging's."""

import pytest
import yaml
from comeni_core.declared.contract import ModuleContract, Provenance
from mendel_forge.forging.values import contract_of, items_of, validate_value
from pydantic import ValidationError
from support.paths import REGISTRY

STAR = REGISTRY / "tools" / "nf-core" / "star" / "align" / "contract.yml"


def _star() -> ModuleContract:
    data = yaml.safe_load(STAR.read_text())
    data.pop("declares")
    return ModuleContract(**data)


@pytest.mark.parametrize("key, good, bad", [
    ("contract:input:reads", {"position": 0, "name": "reads", "type_id": "fastq.reads"},
     {"position": 0, "name": "reads", "colour": "blue"}),
    ("parameters:param:min_contig", {"position": 0, "name": "min_contig", "default": 500,
                                     "via": "ext", "key": "args",
                                     "template": "--min-contig {value}"},
     {"name": "min contig", "via": "ext"}),
    ("vocabulary:type:assembly.contigs", {"id": "assembly.contigs", "states": []},
     {"id": "assembly.contigs", "colour": "blue"}),
    ("rules:none", {"because": "nothing competes for assembly_qc"}, {"reason": 3}),
    ("questions:role", {"asks": "Which role?", "options": [
        {"id": "assembly_qc", "label": "assembly_qc", "because": "new"}]}, {"asks": 3}),
])
def test_each_key_family_validates_its_registry_model(key, good, bad):
    validate_value(key, good)
    with pytest.raises(ValidationError):
        validate_value(key, bad)


def test_a_measurer_is_its_draft_and_nothing_else():
    from mendel_forge.forging.values import MeasurerDraft
    from support.forge_measurer import KEY, measurer
    assert isinstance(validate_value(KEY, measurer()), MeasurerDraft)
    with pytest.raises(ValidationError):  # `by`, `uses` and `runs` are the engine's
        validate_value(KEY, {**measurer(), "by": "code"})
    with pytest.raises(ValidationError):
        validate_value(KEY, {**measurer(), "code": ""})


def test_a_measurers_measurement_is_a_measurement():
    from comeni_core.declared.measurement import Measurement
    value = {"id": "n50", "kind": "integer", "description": "Assembly N50", "cite": "QUAST"}
    assert isinstance(validate_value("measurers:measurement:n50", value), Measurement)


def test_an_answer_is_a_choice_not_a_question():
    validate_value("questions:role", {"choice": "assembly_qc"}, answer=True)


def test_contract_of_star_align_items_equals_the_registry_contract():
    star = _star()
    values = items_of(star)
    assert values, "a contract has items"
    rebuilt = contract_of(values, star.id, star.provenance)
    assert rebuilt == star


def test_items_of_names_every_port_and_param():
    keys = set(items_of(_star()))
    assert {"contract:process", "contract:input:reads", "contract:output:bam",
            "parameters:param:seq_platform", "parameters:ext_args"} <= keys


def test_contract_of_records_the_forge_as_its_source():
    star = _star()
    provenance = Provenance(source="forge", drafted_by="ai", approved_by="rafael",
                            approved_at="2026-10-30")
    assert contract_of(items_of(star), star.id, provenance).provenance.source == "forge"


@pytest.mark.parametrize("identifier", [
    "../assembly", "assembly.fasta", "assembly/x", "", "x" * 65,
])
def test_family_id_is_a_safe_single_type_segment(identifier):
    with pytest.raises(ValidationError):
        validate_value("vocabulary:family:assembly", {
            "id": identifier, "description": "Assembled sequences"})


@pytest.mark.parametrize("description", ["", "x" * 201])
def test_family_description_uses_registry_bounds(description):
    with pytest.raises(ValidationError):
        validate_value("vocabulary:family:assembly", {"id": "assembly", "description": description})

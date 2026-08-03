import pytest
from comeni_core.contract import Alternative, InputPort
from comeni_core.vocabulary import Vocabulary


def test_the_single_form_is_one_alternative():
    """Existing contracts must not change. `type_id` + `state_required` is sugar."""
    port = InputPort(name="bam", type_id="alignment.bam", state_required=frozenset({"sorted"}))
    assert port.alternatives() == [
        Alternative(type_id="alignment.bam", states=frozenset({"sorted"}))
    ]


def test_accepts_declares_several_alternatives_in_order():
    port = InputPort(
        name="bam",
        accepts=[
            {"type_id": "alignment.bam", "states": ["coordinate_sorted"]},
            {"type_id": "alignment.cram", "states": ["coordinate_sorted"]},
        ],
    )
    assert [a.type_id for a in port.alternatives()] == ["alignment.bam", "alignment.cram"]


def test_a_port_declaring_both_forms_is_refused():
    with pytest.raises(ValueError, match="both"):
        InputPort(name="bam", type_id="alignment.bam", accepts=[{"type_id": "alignment.cram"}])


def test_a_port_declaring_neither_form_is_refused():
    with pytest.raises(ValueError, match="neither"):
        InputPort(name="bam")


def test_alternatives_are_validated_against_the_vocabulary(tmp_path):
    (tmp_path / "alignment.bam.yml").write_text("states: [coordinate_sorted]\n")
    vocab = Vocabulary.load(tmp_path)
    port = InputPort(
        name="bam", accepts=[{"type_id": "alignment.bam", "states": ["sorted_by_coord"]}]
    )
    with pytest.raises(Exception, match="sorted_by_coord"):
        for alternative in port.alternatives():
            vocab.validate(alternative.type_id, alternative.states)


def test_a_contract_checks_every_alternative_not_only_the_first(tmp_path):
    """`check_against` used to read `port.type_id`, which an `accepts` port does not have."""
    import yaml
    from comeni_core.contract import ModuleContract

    (tmp_path / "alignment.bam.yml").write_text("states: [coordinate_sorted]\n")
    (tmp_path / "alignment.cram.yml").write_text("states: []\n")
    (tmp_path / "counts.matrix.yml").write_text("states: []\n")
    vocab = Vocabulary.load(tmp_path)
    contract = tmp_path / "c.yml"
    contract.write_text(yaml.safe_dump({
        "id": "x/y@1",
        "nf_process": "Y",
        "nf_include": "modules/y/main",
        "consumes": [{
            "name": "bam",
            "accepts": [
                {"type_id": "alignment.bam", "states": ["coordinate_sorted"]},
                {"type_id": "alignment.cram", "states": ["coordinate_sorted"]},
            ],
        }],
        "produces": [{"name": "counts", "type_id": "counts.matrix"}],
        "provenance": {
            "source": "hand", "drafted_by": "hand",
            "approved_by": "r", "approved_at": "2026-08-03",
        },
    }))
    with pytest.raises(Exception, match="coordinate_sorted"):
        ModuleContract.load(contract, vocab)


def test_state_preferred_still_populates_prefer():
    """Vendored contracts wrote `state_preferred`; nothing on disk may break."""
    port = InputPort(
        name="bam", type_id="alignment.bam", state_preferred=frozenset({"deduplicated"})
    )
    assert port.prefer == frozenset({"deduplicated"})


def test_alternatives_serialise_their_states_sorted():
    """Byte-identical emission: anything serialising a frozenset sorts on the way out."""
    a = Alternative(type_id="alignment.bam", states=frozenset({"indexed", "coordinate_sorted"}))
    assert a.model_dump()["states"] == ["coordinate_sorted", "indexed"]

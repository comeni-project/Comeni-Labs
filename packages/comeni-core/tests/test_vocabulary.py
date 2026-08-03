import pytest
from comeni_core.vocabulary import UnknownStateError, UnknownTypeError, Vocabulary


def test_loads_states_for_a_type(tmp_path):
    (tmp_path / "alignment.bam.yml").write_text(
        "states: [coordinate_sorted, name_sorted, deduplicated]\n"
    )
    vocab = Vocabulary.load(tmp_path)
    assert vocab.states_for("alignment.bam") == frozenset(
        {"coordinate_sorted", "name_sorted", "deduplicated"}
    )


def test_validate_accepts_declared_states(tmp_path):
    (tmp_path / "alignment.bam.yml").write_text("states: [coordinate_sorted]\n")
    Vocabulary.load(tmp_path).validate("alignment.bam", ["coordinate_sorted"])


def test_validate_rejects_undeclared_state(tmp_path):
    (tmp_path / "alignment.bam.yml").write_text("states: [coordinate_sorted]\n")
    vocab = Vocabulary.load(tmp_path)
    with pytest.raises(UnknownStateError, match="sorted_by_coord"):
        vocab.validate("alignment.bam", ["sorted_by_coord"])


def test_validate_rejects_unknown_type(tmp_path):
    vocab = Vocabulary.load(tmp_path)
    with pytest.raises(UnknownTypeError, match="alignment.cram"):
        vocab.validate("alignment.cram", [])


def test_empty_state_list_is_always_valid(tmp_path):
    (tmp_path / "alignment.bam.yml").write_text("states: [coordinate_sorted]\n")
    Vocabulary.load(tmp_path).validate("alignment.bam", [])

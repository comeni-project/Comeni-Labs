import pathlib

import pytest
from comeni_core.declared.vocabulary import UnknownStateError, UnknownTypeError, Vocabulary

_KIND_OF_DIR = {
    "contracts": "contract",
    "vocabularies": "vocabulary",
    "measurements": "measurement",
    "roles": "role",
    "rules": "rule",
}


def _declared(path, body: str) -> str:
    """Add an explicit declaration kind and ID to a fixture body, if absent."""
    path = pathlib.Path(path)
    # Fixtures may nest files below their kind directory, so inspect every ancestor.
    kind = next(
        (_KIND_OF_DIR[p.name] for p in path.parents if p.name in _KIND_OF_DIR), None
    )
    if kind is None or body.lstrip().startswith("declares:"):
        return body
    header = f"declares: {kind}\n"
    if kind in ("vocabulary", "measurement"):
        header += f"id: {path.name.removesuffix('.yml').removesuffix('.yaml')}\n"
    return header + body


def _layer(root, **files):
    """Create and return a layer root containing vocabulary fixtures."""
    directory = root / "vocabularies"
    directory.mkdir(exist_ok=True)
    for name, body in files.items():
        (directory / f"{name.replace('__', '.')}.yml").write_text(
            _declared(
                directory / f"{name.replace('__',
                '.')}.yml", body))
    return root


def test_loads_states_for_a_type(tmp_path):
    layer = _layer(
        tmp_path, alignment__bam="states: [coordinate_sorted, name_sorted, deduplicated]\n"
    )
    vocab = Vocabulary.load(layer)
    assert vocab.states_for("alignment.bam") == frozenset(
        {"coordinate_sorted", "name_sorted", "deduplicated"}
    )


def test_validate_accepts_declared_states(tmp_path):
    layer = _layer(tmp_path, alignment__bam="states: [coordinate_sorted]\n")
    Vocabulary.load(layer).validate("alignment.bam", ["coordinate_sorted"])


def test_validate_rejects_undeclared_state(tmp_path):
    layer = _layer(tmp_path, alignment__bam="states: [coordinate_sorted]\n")
    vocab = Vocabulary.load(layer)
    with pytest.raises(UnknownStateError, match="sorted_by_coord"):
        vocab.validate("alignment.bam", ["sorted_by_coord"])


def test_validate_rejects_unknown_type(tmp_path):
    vocab = Vocabulary.load(_layer(tmp_path))
    with pytest.raises(UnknownTypeError, match="alignment.cram"):
        vocab.validate("alignment.cram", [])


def test_empty_state_list_is_always_valid(tmp_path):
    layer = _layer(tmp_path, alignment__bam="states: [coordinate_sorted]\n")
    Vocabulary.load(layer).validate("alignment.bam", [])


def test_a_misspelled_key_is_refused(tmp_path):
    """Strict declarations refuse unknown fields instead of silently dropping them."""
    layer = _layer(tmp_path, alignment__bam="state: [coordinate_sorted]\n")
    with pytest.raises(ValueError, match="state"):
        Vocabulary.load(layer)


def test_add_states_of_nothing_is_refused(tmp_path):
    layer = _layer(tmp_path, alignment__bam="add_states: [coordinate_sorted]\n")
    with pytest.raises(ValueError, match="which no layer declares"):
        Vocabulary.load(layer)


def test_a_derived_vocabulary_keeps_every_field():
    """Deriving measurement types changes only the vocabulary's type mapping."""
    from comeni_core.declared.measurement import MeasurementRegistry

    before = Vocabulary(
        types={"a.b": frozenset({"x"})},
        entry_channels={"a.b": "Channel.of(params.{param})"},
        params={"a.b": "ab"},
        test_data={"a.b": "https://example.invalid/x"},
    )
    after = before.with_measurements(MeasurementRegistry())

    for field in sorted(set(Vocabulary.model_fields) - {"types"}):
        assert getattr(after, field) == getattr(before, field), (
            f"`with_measurements` dropped {field!r} — it is building a new `Vocabulary` from a "
            f"hand-written field list instead of a `model_copy`"
        )
    assert after.types["a.b"] == frozenset({"x"})
    assert "measurement.read_length" not in after.types

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
    """Prepend what a fixture's file declares, derived from the directory it is written into.

    Since comeni-registry#1 a declared file says what it is and the loader no longer reads the
    directory. These fixtures still *write* into kind-named directories, which is now only a
    habit — and the habit is what tells this helper which line to add, so the fixtures keep
    their shape and their subject stays readable.

    Idempotent, because several fixtures write a file twice to check that something changed.
    """
    path = pathlib.Path(path)
    # Walk *ancestors*, not just the immediate parent: real layers nest, and
    # `tools/nf-core/fastqc/fastqc.contract.yml` sits two levels down from the directory that
    # names it.
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
    """A layer root holding a `vocabularies/` directory, which is what a layer is.

    `Vocabulary.load` takes layer roots since A24: a loader handed a bare directory of
    type files does not know which layer it is reading, so it had nothing to record a
    displacement against.
    """
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
    """`extra="forbid"`, for A10's reason and A35's.

    `add_states` was a key the loader ignored, so a file declaring only that produced a
    type with no states at all and the failure surfaced three files away.
    """
    layer = _layer(tmp_path, alignment__bam="state: [coordinate_sorted]\n")
    with pytest.raises(ValueError, match="state"):
        Vocabulary.load(layer)


def test_add_states_of_nothing_is_refused(tmp_path):
    layer = _layer(tmp_path, alignment__bam="add_states: [coordinate_sorted]\n")
    with pytest.raises(ValueError, match="which no layer declares"):
        Vocabulary.load(layer)


def test_a_derived_vocabulary_keeps_every_field():
    """`with_measurements` returns a new `Vocabulary` and must not lose one on the way.

    It listed every field by hand in a fresh `Vocabulary(...)`, which is correct only for as
    long as somebody remembers — and the failure mode is **silence**: a field added to the model
    and collected by `of()` is dropped here, leaving one populated and another empty a few lines
    apart in the same function, with nothing raising and nothing to grep for.

    It is a `model_copy` now, which cannot drop a field. This guard is for the next person who
    finds a reason to spell it out again: everything except the one field being changed survives.
    """
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

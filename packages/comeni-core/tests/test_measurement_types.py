import pathlib

import pytest
from comeni_core.declared.measurement import MeasurementRegistry
from comeni_core.declared.vocabulary import UnknownStateError, Vocabulary

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


def test_every_declared_measurement_becomes_a_type(tmp_path):
    """A measurement is a type modules produce, which is what makes profiling routable."""
    (m := tmp_path / "measurements").mkdir()
    (m / "read_length.yml").write_text(
        _declared(
            m / "read_length.yml",
            "kind: integer\nminimum: 1\n"))
    (v := tmp_path / "vocabularies").mkdir()
    (v / "fastq.reads.yml").write_text(_declared(v / "fastq.reads.yml", "states: []\n"))

    vocab = Vocabulary.load(tmp_path).with_measurements(MeasurementRegistry.load(tmp_path))
    assert vocab.states_for("measurement.read_length") == frozenset()
    assert vocab.states_for("fastq.reads") == frozenset()


def test_a_measurement_type_carries_no_states(tmp_path):
    (m := tmp_path / "measurements").mkdir()
    (m / "strandedness.yml").write_text(
        _declared(
            m / "strandedness.yml",
            "kind: enum\nvalues: [forward, reverse]\n"))
    vocab = Vocabulary.load([]).with_measurements(MeasurementRegistry.load(tmp_path))
    with pytest.raises(UnknownStateError):
        vocab.validate("measurement.strandedness", ["forward"])


def test_the_base_vocabulary_is_not_mutated(tmp_path):
    """`with_measurements` derives a new vocabulary; the loaded one is unchanged."""
    (m := tmp_path / "measurements").mkdir()
    (m / "read_length.yml").write_text(_declared(m / "read_length.yml", "kind: integer\n"))
    (v := tmp_path / "vocabularies").mkdir()
    (v / "fastq.reads.yml").write_text(
        _declared(
            v / "fastq.reads.yml",
            "states: [trimmed]\nentry_channel: 'Channel.of()'\n"))

    base = Vocabulary.load(tmp_path)
    derived = base.with_measurements(MeasurementRegistry.load(tmp_path))
    assert "measurement.read_length" not in base.types
    assert derived.entry_channels == base.entry_channels

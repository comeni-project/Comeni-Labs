import pytest
from comeni_core.measurement import MeasurementRegistry
from comeni_core.vocabulary import UnknownStateError, Vocabulary


def test_every_declared_measurement_becomes_a_type(tmp_path):
    """A measurement is a type modules produce, which is what makes profiling routable."""
    (m := tmp_path / "measurements").mkdir()
    (m / "read_length.yml").write_text("kind: integer\nminimum: 1\n")
    (v := tmp_path / "vocabularies").mkdir()
    (v / "fastq.reads.yml").write_text("states: []\n")

    vocab = Vocabulary.load(v).with_measurements(MeasurementRegistry.load(m))
    assert vocab.states_for("measurement.read_length") == frozenset()
    assert vocab.states_for("fastq.reads") == frozenset()


def test_a_measurement_type_carries_no_states(tmp_path):
    (m := tmp_path / "measurements").mkdir()
    (m / "strandedness.yml").write_text("kind: enum\nvalues: [forward, reverse]\n")
    vocab = Vocabulary.load([]).with_measurements(MeasurementRegistry.load(m))
    with pytest.raises(UnknownStateError):
        vocab.validate("measurement.strandedness", ["forward"])


def test_the_base_vocabulary_is_not_mutated(tmp_path):
    """`with_measurements` derives a new vocabulary; the loaded one is unchanged."""
    (m := tmp_path / "measurements").mkdir()
    (m / "read_length.yml").write_text("kind: integer\n")
    (v := tmp_path / "vocabularies").mkdir()
    (v / "fastq.reads.yml").write_text("states: [trimmed]\nentry_channel: 'Channel.of()'\n")

    base = Vocabulary.load(v)
    derived = base.with_measurements(MeasurementRegistry.load(m))
    assert "measurement.read_length" not in base.types
    assert derived.entry_channels == base.entry_channels

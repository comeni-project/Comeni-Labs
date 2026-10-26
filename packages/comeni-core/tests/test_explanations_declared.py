"""User-facing names and explanations are optional and do not affect pipeline construction."""

import pytest
from comeni_core.declared.measurement import MeasurementRegistry
from comeni_core.declared.vocabulary import Vocabulary


def _write(root, rel, body):
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body)


def test_a_type_carries_its_name_and_explanation(tmp_path):
    _write(tmp_path, "vocabulary/annotation.gtf.yml",
           "declares: vocabulary\nid: annotation.gtf\nscope: run\n"
           "name: gene annotation (GTF)\nexplain: Where each gene lies.\n")
    _write(tmp_path, "vocabulary/genome.fasta.yml",
           "declares: vocabulary\nid: genome.fasta\nscope: run\n")
    vocabulary = Vocabulary.load(tmp_path)
    assert vocabulary.names == {"annotation.gtf": "gene annotation (GTF)"}
    assert vocabulary.explains == {"annotation.gtf": "Where each gene lies."}


def test_an_extension_cannot_rename_a_type(tmp_path):
    _write(tmp_path, "vocabulary/x.yml",
           "declares: vocabulary\nid: annotation.gtf\nadd_states: [sorted]\nname: other\n")
    with pytest.raises(ValueError, match="MD0007"):
        Vocabulary.load(tmp_path)


def test_a_measurement_carries_its_explanation(tmp_path):
    _write(tmp_path, "measurements/read_length.yml",
           "declares: measurement\nid: read_length\nkind: integer\nminimum: 1\n"
           "description: Sequenced read length\nexplain: Bases per read.\n")
    _write(tmp_path, "measurements/organism.yml",
           "declares: measurement\nid: organism\nkind: boolean\n")
    registry = MeasurementRegistry.load(tmp_path)
    assert registry.get("read_length").explain == "Bases per read."
    assert registry.get("organism").explain is None


def test_an_explanation_too_long_to_show_is_refused_when_the_layer_loads(tmp_path):
    """Display-length constraints are enforced when declarations load."""
    _write(tmp_path, "measurements/read_length.yml",
           "declares: measurement\nid: read_length\nkind: integer\nminimum: 1\n"
           f"explain: {'x' * 601}\n")
    with pytest.raises(ValueError, match="explain"):
        MeasurementRegistry.load(tmp_path)

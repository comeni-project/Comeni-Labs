"""A type's second column may be blank, and a fact may be read off the row (#466, stage 3)."""

import pytest
from comeni_core.declared.measurement import Measurement
from mendel_resolver import layers
from support.paths import ROOT

LOADED = layers.load(ROOT / "registry")


def test_reads_may_leave_their_second_column_blank():
    assert "fastq.reads" in LOADED.vocabulary.blank_second
    assert "genome.fasta" not in LOADED.vocabulary.blank_second


def test_pairing_is_read_off_the_row():
    assert LOADED.measurements.get("paired").row == "second_file_present"


def test_a_row_fact_must_be_a_boolean():
    with pytest.raises(ValueError, match="MD0338"):
        Measurement.model_validate({"id": "x", "kind": "integer", "describes": "fastq.reads",
                                    "row": "second_file_present"})


def test_a_row_fact_must_describe_a_type_with_a_blank_second_column(tmp_path):
    import shutil

    layer = tmp_path / "layer"
    shutil.copytree(ROOT / "registry", layer, ignore=shutil.ignore_patterns(".git"))
    path = layer / "vocabulary/measurements/paired.yml"
    path.write_text(path.read_text().replace("describes: fastq.reads",
                                             "describes: genome.fasta"))
    with pytest.raises(ValueError, match="MD0338"):
        layers.load(layer)

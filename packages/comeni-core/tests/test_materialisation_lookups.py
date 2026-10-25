"""Regression checks for metadata batching and colliding channel names."""

import pytest
from comeni_core.artifact.materialise import _meta_entry, _unique
from comeni_core.artifact.param_refs import extract_param_refs
from comeni_core.declared.measurement import (
    Measurement,
    MeasurementKind,
    MeasurementRegistry,
    MetaValue,
)
from comeni_core.goal.profile import DataProfile, Evidence, Measured
from comeni_core.plan.tiers import ValueSource


def test_metadata_batch_preserves_translation_precedence_and_missing_values():
    def declaration(name, type_id, key, **kwargs):
        return Measurement(
            id=name, kind=MeasurementKind.INTEGER, describes=type_id, meta_key=key, **kwargs
        )

    declarations = [
        declaration("a_first", "fastq.reads", "count"),
        declaration("z_last", "fastq.reads", "count"),
        declaration(
            "b_translated", "annotation.gtf", "mode",
            meta_values=[MetaValue(when=0, then=2)],
        ),
        declaration("c_missing", "annotation.gtf", "missing"),
        declaration("d_unrequested", "genome.fasta", "count"),
    ]
    registry = MeasurementRegistry(measurements={m.id: m for m in reversed(declarations)})
    profile = DataProfile(measurements=[
        Measured(measurement="a_first", value=1),
        Measured(measurement="z_last", value=0),
        Measured(measurement="b_translated", value=0),
        Measured(measurement="d_unrequested", value=3),
    ])

    sources = registry.meta_sources_by_type({"fastq.reads", "annotation.gtf"}, profile)

    assert set(sources) == {"fastq.reads", "annotation.gtf"}
    assert sources["fastq.reads"]["count"] == (declarations[1], 0)
    assert sources["annotation.gtf"] == {"mode": (declarations[2], 2)}
    assert registry.meta_sources_for("fastq.reads", profile) == sources["fastq.reads"]
    assert registry.meta_sources_for("alignment.bam", profile) == {}


def test_name_suffixes_skip_explicit_names_and_overlapping_stems():
    taken = {"report_2": None}
    suffixes = {}
    stems = ["report", "report", "report_3", "report", "report_3", "report"]
    assert [_unique(stem, taken, suffixes) for stem in stems] == [
        "report", "report_3", "report_3_2", "report_4", "report_3_3", "report_5"
    ]


def test_repeated_names_do_not_rescan_all_previous_suffixes():
    class CountedNames(dict):
        probes = 0

        def __contains__(self, name):
            self.probes += 1
            return super().__contains__(name)

    taken = CountedNames()
    suffixes = {}
    names = [_unique("reads", taken, suffixes) for _ in range(1000)]
    assert len(set(names)) == 1000
    assert names[-1] == "reads_1000"
    assert taken.probes < 3000


@pytest.mark.parametrize(
    ("entry", "reason"),
    [
        (
            Measured(
                measurement="read_length",
                value=151,
                source=ValueSource.MEASURED,
                pieces=["fastq@1.0.0", "read_length@1.0.0"],
                evidence=Evidence(records=8412),
            ),
            "measured by fastq@1.0.0 + read_length@1.0.0, on 8,412 reads",
        ),
        (
            Measured(
                measurement="read_length",
                value=151,
                source=ValueSource.MEASURED,
                by="comeni/profile/fastqc@0.12.1",
                evidence=Evidence(rows=50),
            ),
            "measured by comeni/profile/fastqc@0.12.1, on 50 rows of reads",
        ),
        (
            Measured(measurement="read_length", value=151, source=ValueSource.MODEL),
            "read by AI from the start of a sample; check it",
        ),
    ],
)
def test_metadata_explains_how_each_non_asserted_value_was_obtained(entry, reason):
    measurement = Measurement(
        id="read_length",
        kind=MeasurementKind.INTEGER,
        describes="fastq.reads",
        meta_key="read_length",
        cite="doi:10.1/example",
        description="median read length",
    )

    meta = _meta_entry("read_length", measurement, entry.value, entry)

    assert meta.why.source is entry.source
    assert meta.why.reason == f"{reason}; doi:10.1/example — median read length"


def test_parameter_reference_scanning_ignores_empty_and_deduplicates_names():
    expression = "params. + params.reads + params.reads + params.reference-file"
    assert extract_param_refs(expression) == ["reads", "reference"]

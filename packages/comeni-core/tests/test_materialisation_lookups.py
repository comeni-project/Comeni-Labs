"""Regression checks for metadata batching and colliding channel names."""

from comeni_core.artifact.materialise import _unique
from comeni_core.declared.measurement import (
    Measurement,
    MeasurementKind,
    MeasurementRegistry,
    MetaValue,
)
from comeni_core.goal.profile import DataProfile, Measured


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

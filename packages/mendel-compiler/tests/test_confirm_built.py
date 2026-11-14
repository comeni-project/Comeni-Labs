"""The saved pipeline carries every estimate it confirms in the run (#465)."""

from comeni_core.declared.measurement import MeasuredEntry
from comeni_core.goal.profile import Evidence
from comeni_core.plan.tiers import ValueSource
from mendel_compiler import orchestrate
from mendel_resolver import layers
from mendel_resolver.goal import Goal
from support.at_run import ROOT


def test_the_pipeline_records_the_confirmation_and_the_step():
    stack = layers.load(ROOT / "registry")
    profile = stack.measurements.profile_of([
        MeasuredEntry("read_length", 150, ValueSource.MEASURED, None,
                      ("fastq@1.1.0", "read_length@1.0.0"), Evidence(records=2000,
                                                                    coverage="head")),
        MeasuredEntry("paired", True, ValueSource.SAID),
        MeasuredEntry("strandedness", "reverse", ValueSource.SAID),
    ])
    goal = Goal.model_validate({
        "have": [{"type_id": "fastq.reads"}, {"type_id": "annotation.gtf"},
                 {"type_id": "genome.fasta"}],
        "want": ["counts.matrix"],
        "constraints": {"required_states": [{"type_id": "counts.matrix",
                                             "states": ["gene_level"]}]},
        "profile": profile.model_dump(mode="json"),
    })
    pipeline = orchestrate.build(goal, registry_root=ROOT / "registry").pipeline
    (confirm,) = pipeline.confirms
    assert confirm.measurement == "read_length" and confirm.estimate == 150
    step = next(s for s in pipeline.steps if s.id == confirm.measured_at)
    assert step.process == "MEASURE_FASTQ"
    assert pipeline.intent.want == ["counts.matrix"]

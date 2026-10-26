"""Behavioral coverage for the pipeline changes shown by ``mendel upgrade``."""

import pytest
from comeni_core.artifact.pipeline import Pipeline
from comeni_core.plan.tiers import Tier
from mendel_resolver.diff import diff_pipeline
from mendel_resolver.goal import Goal, GoalInput
from mendel_resolver.resolve import resolve


@pytest.fixture(scope="module")
def pipeline(stack):
    goal = Goal(
        have=[
            GoalInput(type_id="fastq.reads"),
            GoalInput(type_id="annotation.gtf"),
            GoalInput(type_id="genome.fasta"),
        ],
        want=["counts.matrix"],
        profile=stack.measurements.profile({"read_length": 150}),
    )
    ir = resolve(
        goal,
        stack.registry,
        stack.rules,
        stack.measurements,
        vocabulary=stack.vocabulary,
    )
    return Pipeline.of(
        ir,
        stack.registry,
        stack.vocabulary,
        stack.measurements,
        stack.paths,
        goal=goal,
    )


def _replace_step(pipeline, step_id, replacement):
    return pipeline.model_copy(
        update={
            "steps": [replacement if step.id == step_id else step for step in pipeline.steps]
        }
    )


def test_identical_pipelines_have_no_reported_changes(pipeline):
    assert diff_pipeline(pipeline, pipeline.model_copy(deep=True)) == []


def test_module_replacement_reports_the_new_selection_evidence(pipeline):
    old = next(step for step in pipeline.steps if step.id == "star_align")
    changed = old.model_copy(
        update={
            "module": old.module.model_copy(
                update={"contract_id": "nf-core/hisat2/align@2.2.2"}
            )
        }
    )

    changes = diff_pipeline(pipeline, _replace_step(pipeline, old.id, changed))

    module = next(change for change in changes if change.what == old.id)
    assert module.before == "nf-core/star/align@1.11.0"
    assert module.after == "nf-core/hisat2/align@2.2.2"
    assert module.tier is old.why.tier
    assert module.reason == old.why.reason


def test_setting_value_tier_reason_and_removal_are_each_reported(pipeline):
    old = next(step for step in pipeline.steps if step.id == "star_align")
    seq_platform, ignored = old.settings
    changed = old.model_copy(
        update={
            "settings": [
                seq_platform.model_copy(update={"value": "illumina"}),
                ignored.model_copy(
                    update={
                        "why": ignored.why.model_copy(
                            update={
                                "tier": Tier.DATA_PROFILED,
                                "reason": "measured annotation policy",
                            }
                        )
                    }
                ),
            ]
        }
    )
    changes = diff_pipeline(pipeline, _replace_step(pipeline, old.id, changed))
    by_what = {change.what: change for change in changes}
    assert by_what["star_align.seq_platform"].after == "illumina"
    assert by_what["star_align.star_ignore_sjdbgtf"].after.endswith("(tier 3)")

    reason_only = ignored.model_copy(
        update={"why": ignored.why.model_copy(update={"reason": "new justification"})}
    )
    changed = old.model_copy(update={"settings": [reason_only]})
    changes = diff_pipeline(pipeline, _replace_step(pipeline, old.id, changed))
    by_what = {change.what: change for change in changes}
    assert by_what["star_align.seq_platform"].after == "(no longer a setting)"
    assert by_what["star_align.star_ignore_sjdbgtf (reason)"].after == "new justification"


def test_rewired_input_reports_the_old_and_new_origins(pipeline):
    old = next(step for step in pipeline.steps if step.id == "subread_featurecounts")
    bam = next(item for item in old.inputs if item.port == "bam")
    changed_bam = bam.model_copy(update={"source": "star_align.bam"})
    changed = old.model_copy(
        update={
            "inputs": [changed_bam if item.port == "bam" else item for item in old.inputs]
        }
    )

    changes = diff_pipeline(pipeline, _replace_step(pipeline, old.id, changed))

    wiring = next(change for change in changes if change.what.endswith("<- bam"))
    assert wiring.before == "samtools_sort.bam"
    assert wiring.after == "star_align.bam"
    assert wiring.tier is Tier.STRUCTURAL


def test_added_and_removed_steps_are_reported_and_sorted(pipeline):
    removed = next(step for step in pipeline.steps if step.id == "trimgalore")
    added = removed.model_copy(
        update={
            "id": "adapter_cleanup",
            "module": removed.module.model_copy(
                update={"contract_id": "lab/adapter-cleanup@1.0.0"}
            ),
        }
    )
    after = pipeline.model_copy(
        update={
            "steps": [step for step in pipeline.steps if step.id != removed.id] + [added]
        }
    )

    changes = diff_pipeline(pipeline, after)

    assert [change.what for change in changes] == ["adapter_cleanup", "trimgalore"]
    assert changes[0].before == "(absent)"
    assert changes[0].after == "lab/adapter-cleanup@1.0.0"
    assert changes[1].before == "nf-core/trimgalore@0.6.10"
    assert changes[1].after == "(removed)"

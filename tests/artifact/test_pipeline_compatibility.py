"""Saved-pipeline compatibility: observable CLI and artifact behavior."""

from comeni_core.artifact.pipeline import SCHEMA_VERSION, Pipeline, Setting, Why
from support.pipeline import (
    RELEASED_SCHEMA_VERSION,
    SERIALISED_SHAPE,
    _build,
    _declared,
    _emit,
)


def test_a_newer_version_is_refused(tmp_path, capsys):
    """Forward compatibility is a promise this format has not made.

    An older Mendel silently ignoring a section a newer one added is how a pipeline gets
    emitted without the thing that section carried.
    """
    out = _build(tmp_path)
    path = out / "pipeline.yml"
    # Relative to what this Mendel writes, never a literal: pinning `version: 2` here made
    # this test assert nothing the moment SCHEMA_VERSION reached 2, and it would have gone on
    # passing for a version that is no longer newer than anything. Plan 1.14 Task 0.
    path.write_text(
        _declared(
            path,
            path.read_text().replace(
                f"version: {SCHEMA_VERSION}", f"version: {SCHEMA_VERSION + 1}", 1
            ),
        )
    )
    code, err = _emit(out, capsys)
    assert code != 0 and "MD0207" in err


def test_a_schema_change_bumps_the_version():
    """Adding a field to the artifact moves every archived pipeline's digest. Announce it."""
    from comeni_core.artifact.emitted import Emitted
    from comeni_core.artifact.pipeline import (
        SCHEMA_VERSION,
        CallArg,
        ExtArgs,
        MetaEntry,
        Step,
    )
    from comeni_core.goal.premise import PremiseRecord
    from comeni_core.goal.profile import Evidence, Measured
    from comeni_core.plan.decision import ParamDecision

    actual = {
        "Pipeline": list(Pipeline.model_fields),
        "Step": list(Step.model_fields),
        "ExtArgs": list(ExtArgs.model_fields),
        "Setting": list(Setting.model_fields),
        "Why": list(Why.model_fields),
        "CallArg": list(CallArg.model_fields),
        "MetaEntry": list(MetaEntry.model_fields),
        "Emitted": list(Emitted.model_fields),
        "ParamDecision": list(ParamDecision.model_fields),
        "PremiseRecord": list(PremiseRecord.model_fields),
        "Measured": list(Measured.model_fields),
        "Evidence": list(Evidence.model_fields),
    }
    assert actual == SERIALISED_SHAPE, (
        "the artifact's shape moved. Every archived pipeline's `emitted.from_digest` just "
        "moved with it, so bump SCHEMA_VERSION and update SERIALISED_SHAPE together — "
        "updating either alone is the defect Plan 1.14 Task 0 fixed."
    )
    assert SCHEMA_VERSION > RELEASED_SCHEMA_VERSION, (
        "the shape moved, so SCHEMA_VERSION must be ahead of the last released one. Within a "
        "single unreleased bump, adding fields and updating SERIALISED_SHAPE is enough — "
        "version 2 covers everything Plan 1.14 adds. What must never happen is the shape "
        "moving while the version stays at what a laboratory already has on disk."
    )


# Regression evidence: A104, A105
def test_a_file_written_before_for_value_still_emits(tmp_path, capsys):
    """`for_value: null` means "written before 1.14", not "explains nothing".

    An archived pipeline has no such field and must still regenerate its Nextflow. The check
    fires only where the field is set and disagrees, which is also what gives it real
    negatives.
    """
    out = _build(tmp_path)
    path = out / "pipeline.yml"
    path.write_text(
        _declared(
            path,
            "\n".join(line for line in path.read_text().splitlines() if "for_value:" not in line)
            + "\n",
        )
    )

    code, err = _emit(out, capsys)

    assert code == 0, err

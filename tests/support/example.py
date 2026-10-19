"""The example analysis, `examples/rnaseq.yml`, as tests use it.

The file is a starter (`intent` and `facts`); tests resolve a `Goal`, or edit one as a mapping.
Read through `pipeline_file.goal_from`, the reader `mendel build` uses."""

from mendel_compiler import pipeline_file
from mendel_resolver.goal import Goal

from support.paths import ROOT

STARTER = ROOT / "examples" / "rnaseq.yml"


def example_goal() -> Goal:
    return pipeline_file.goal_from(STARTER)


def example_mapping() -> dict:
    """The example's goal as a mapping, its profile as `{measurement: value}`, to edit."""
    goal = example_goal()
    return {**goal.model_dump(mode="json", exclude={"profile"}),
            "profile": {m.measurement: m.value for m in goal.profile.measurements}}

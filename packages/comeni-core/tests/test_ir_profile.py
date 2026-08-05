import pathlib

from comeni_core.ir import PipelineIR
from mendel_resolver import layers
from mendel_resolver.goal import Goal, GoalInput
from mendel_resolver.resolve import resolve

ROOT = pathlib.Path(__file__).parents[3]


def test_an_ir_defaults_to_an_empty_profile():
    assert PipelineIR().profile.measurements == []


def test_a_resolved_ir_carries_the_profile_it_was_built_from():
    loaded = layers.load(ROOT / "registry")
    goal = Goal(
        have=[GoalInput(type_id="fastq.reads")],
        want=["qc.report"],
        profile=loaded.measurements.profile({"strandedness": "reverse", "paired": True}),
    )
    ir = resolve(goal, loaded.registry, loaded.rules, loaded.measurements)
    assert ir.profile.get("strandedness") == "reverse"
    assert ir.profile.get("paired") is True


def test_the_profile_survives_serialisation():
    """It reaches the emitter through pipeline.ir.json in the CLI, not through memory."""
    loaded = layers.load(ROOT / "registry")
    goal = Goal(
        have=[GoalInput(type_id="fastq.reads")],
        want=["qc.report"],
        profile=loaded.measurements.profile({"strandedness": "reverse"}),
    )
    ir = resolve(goal, loaded.registry, loaded.rules, loaded.measurements)
    round_tripped = PipelineIR.model_validate_json(ir.model_dump_json())
    assert round_tripped.profile.get("strandedness") == "reverse"

"""Ownership, compatibility imports, payload reachability, and closed goal shapes."""

import pytest
from pydantic import ValidationError


def test_goal_is_importable_from_core():
    from comeni_core.goal.asked import Constraints, Goal, GoalInput, ParamOverride

    goal = Goal(have=[GoalInput(type_id="fastq.reads")], want=["qc.report"])
    assert goal.want == ["qc.report"]
    assert isinstance(goal.constraints, Constraints)
    assert ParamOverride(name="x", value=1).value == 1


def test_the_resolver_re_export_is_the_same_class():
    """Not a copy. `isinstance` across the two import paths must hold."""
    from comeni_core.goal.asked import Goal as CoreGoal
    from mendel_resolver.goal import Goal as ResolverGoal

    assert CoreGoal is ResolverGoal


def test_the_publication_payload_carries_the_goal():
    """The publication payload can carry core goal projections without a resolver dependency."""
    from comeni_core.egress.boundaries import PAYLOADS
    from comeni_core.goal.asked import Goal

    goal = Goal(want=["counts.matrix"])
    payload = PAYLOADS["publication"](intent=goal.intent, facts=goal.facts)
    assert payload.goal.want == ["counts.matrix"]


def test_the_goal_still_has_nowhere_to_put_a_sample_identifier():
    """A goal describes data shape and rejects undeclared sample-identifying fields."""
    from comeni_core.goal.asked import Goal

    with pytest.raises(ValidationError):
        Goal(want=["counts.matrix"], samples=["patient_4471023_R1.fastq.gz"])


def test_required_states_accepts_both_forms():
    from comeni_core.goal.asked import Constraints

    mapping = Constraints(required_states={"counts.matrix": ["gene_level"]})
    listed = Constraints(
        required_states=[{"type_id": "counts.matrix", "states": ["gene_level"]}]
    )
    assert mapping.states_for("counts.matrix") == frozenset({"gene_level"})
    assert mapping.model_dump() == listed.model_dump()
    assert mapping.states_for("absent.type") == frozenset()

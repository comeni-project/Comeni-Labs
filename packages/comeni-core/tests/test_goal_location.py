"""`Goal` lives in comeni-core, and the resolver re-exports it.

The move exists so the publication payload can carry one. `mendel_resolver.goal` stays as a shim
because a goal is what most resolver code actually meets, and breaking every import to
relocate a type is churn nobody reviews carefully.
"""

import pytest
from pydantic import ValidationError


def test_goal_is_importable_from_core():
    from comeni_core.goal import Constraints, Goal, GoalInput, ParamOverride

    goal = Goal(have=[GoalInput(type_id="fastq.reads")], want=["qc.report"])
    assert goal.want == ["qc.report"]
    assert isinstance(goal.constraints, Constraints)
    assert ParamOverride(name="x", value=1).value == 1


def test_the_resolver_re_export_is_the_same_class():
    """Not a copy. `isinstance` across the two import paths must hold."""
    from comeni_core.goal import Goal as CoreGoal
    from mendel_resolver.goal import Goal as ResolverGoal

    assert CoreGoal is ResolverGoal


def test_the_publication_payload_carries_the_goal():
    """`Pipeline` is door 4's payload since Plan 1.10; `PublishBundle` was before it.

    The reason `Goal` lives in `comeni-core` is unchanged by the swap — the publication
    payload carries one, and `comeni-core` must not depend on `mendel-resolver`.
    """
    from comeni_core.egress import DOORS
    from comeni_core.goal import Goal

    payload = DOORS["publication"](goal=Goal(want=["counts.matrix"]))
    assert payload.goal.want == ["counts.matrix"]


def test_the_goal_still_has_nowhere_to_put_a_sample_identifier():
    """Invariant 15 survives the move. This is the test that makes the move safe."""
    from comeni_core.goal import Goal

    with pytest.raises(ValidationError):
        Goal(want=["counts.matrix"], samples=["patient_4471023_R1.fastq.gz"])


def test_required_states_accepts_both_forms():
    from comeni_core.goal import Constraints

    mapping = Constraints(required_states={"counts.matrix": ["gene_level"]})
    listed = Constraints(
        required_states=[{"type_id": "counts.matrix", "states": ["gene_level"]}]
    )
    assert mapping.states_for("counts.matrix") == frozenset({"gene_level"})
    assert mapping.model_dump() == listed.model_dump()
    assert mapping.states_for("absent.type") == frozenset()

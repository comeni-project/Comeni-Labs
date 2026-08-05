"""Re-export of the goal types, which live in `comeni_core.goal`.

They moved there so `PublishBundle` could carry a `Goal` — a shareable pipeline is
`Goal` + `PipelineIR` + `DecisionRecord[]` + lockfile, and `comeni-core` must not depend
on `mendel-resolver`. Same move `DataProfile` made, for the same reason.

This shim stays because a goal is what most resolver code actually meets, and rewriting
every import to relocate a type is churn nobody reviews carefully.
"""

from comeni_core.goal import Constraints, Goal, GoalInput, ParamOverride
from comeni_core.profile import DataProfile, Measured

__all__ = ["Constraints", "DataProfile", "Goal", "GoalInput", "Measured", "ParamOverride"]

"""Re-export of the goal types, which live in `comeni_core.goal.asked`.

They moved there so the publication payload could carry a `Goal`, and `comeni-core` must
not depend on `mendel-resolver`. Same move `DataProfile` made, for the same reason.

The payload was `PublishBundle` — `Goal` + `PipelineIR` + `DecisionRecord[]` + lockfile —
and is `Pipeline` since Plan 1.10, which carries the same information one layer less
assembled. The reason for the move is unchanged by that; it is why it is stated as a reason
rather than as a reference.

This shim stays because a goal is what most resolver code actually meets, and rewriting
every import to relocate a type is churn nobody reviews carefully.
"""

from comeni_core.goal.asked import Constraints, Goal, GoalInput, ParamOverride
from comeni_core.goal.profile import DataProfile, Measured

__all__ = ["Constraints", "DataProfile", "Goal", "GoalInput", "Measured", "ParamOverride"]

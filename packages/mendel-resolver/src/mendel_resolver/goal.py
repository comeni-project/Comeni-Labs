"""Compatibility imports for goal models owned by :mod:`comeni_core.goal`.

Resolver callers may continue importing these names here while the shared artifact and resolver
layers use the same dependency-neutral model definitions.
"""

from comeni_core.goal.asked import Constraints, Goal, GoalInput, ParamOverride
from comeni_core.goal.profile import DataProfile, Measured

__all__ = ["Constraints", "DataProfile", "Goal", "GoalInput", "Measured", "ParamOverride"]

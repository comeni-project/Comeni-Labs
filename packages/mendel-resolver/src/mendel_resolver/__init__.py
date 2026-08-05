"""Mendel's four-tier resolver: typed goal in, pipeline IR out.

Every module choice and every parameter exits at exactly one tier — structural,
convention, data-profiled or ambiguous — and carries it forever. A tier-3 miss demotes to
tier 4 and never reaches for a model; that is what keeps the labels meaningful and the
common case free.

Start with `layers.load()`, which loads a registry layer stack in the one order that
works, then `resolve()`::

    from mendel_resolver import Goal, GoalInput, layers, resolve

    loaded = layers.load("registry")
    goal = Goal(have=[GoalInput(type_id="fastq.reads")], want=["qc.report"])
    ir = resolve(goal, loaded.registry, loaded.rules, loaded.measurements)

This package is **pure** — see `comeni_core`. AI plugs in through the `Protocol`s in
`mendel_resolver.ports`, and the dependency arrow points at this package, never out of it.
"""

from mendel_resolver import layers
from mendel_resolver.goal import (
    Constraints,
    DataProfile,
    Goal,
    GoalInput,
    Measured,
    ParamOverride,
)
from mendel_resolver.layers import Layers
from mendel_resolver.ports import AmbiguityResolver, FlagOnlyResolver, NoCandidatesError
from mendel_resolver.replay import ReplayResolver
from mendel_resolver.resolve import resolve
from mendel_resolver.router import (
    RoutePlan,
    RouteStep,
    UnroutableError,
    UnroutablePinError,
    route,
)
from mendel_resolver.rules import (
    Decision,
    DecisionRow,
    DecisionTarget,
    RuleTable,
    RuleValidationError,
)

__version__ = "0.1.0"

__all__ = [
    "AmbiguityResolver",
    "Constraints",
    "DataProfile",
    "Decision",
    "DecisionRow",
    "DecisionTarget",
    "FlagOnlyResolver",
    "Goal",
    "GoalInput",
    "Layers",
    "Measured",
    "NoCandidatesError",
    "ParamOverride",
    "ReplayResolver",
    "RoutePlan",
    "RouteStep",
    "RuleTable",
    "RuleValidationError",
    "UnroutableError",
    "UnroutablePinError",
    "layers",
    "resolve",
    "route",
]

"""Public tier-3 rule models, table, and validation errors.

The submodules have separate responsibilities:

| module | question |
|---|---|
| `format` | what a rule *is* |
| `table` | how the ones on disk become the ones in force |
| `validate` | why yours was refused |

The re-exports below are the supported import surface. A rule miss demotes to tier 4; it does not
invoke a model.
"""

from mendel_resolver.rules.format import (
    Aggregate,
    Decision,
    DecisionRow,
    DecisionTarget,
    Derivation,
    Effect,
    Fired,
    Pin,
    Predicate,
    RuleValidationError,
    Transform,
)
from mendel_resolver.rules.format import (
    _comparison as _comparison,
)
from mendel_resolver.rules.table import RuleTable
from mendel_resolver.rules.validate import _computed_over as _computed_over

__all__ = [
    "Aggregate",
    "Decision",
    "DecisionRow",
    "DecisionTarget",
    "Derivation",
    "Effect",
    "Fired",
    "Pin",
    "Predicate",
    "RuleTable",
    "RuleValidationError",
    "Transform",
]
"""Private validation helpers remain importable for focused tests but are absent from `__all__`."""

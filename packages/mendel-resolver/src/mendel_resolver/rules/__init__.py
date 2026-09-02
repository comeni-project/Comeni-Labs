"""Tier 3: two layers of declared data, and every way they are refused at load.

A miss is not an escalation to a model. It is a demotion to tier 4.

A package rather than a module since issue #41 — `rules.py` was 1,170 lines and the validator
alone was ~450 of them. The three parts answer different questions:

| module | question |
|---|---|
| `format` | what a rule *is* |
| `table` | how the ones on disk become the ones in force |
| `validate` | why yours was refused |

**These re-exports are the module's own surface, not a shim.** `rules` was a module and is now
a package, so `from mendel_resolver.rules import RuleTable` means exactly what it always meant
and nineteen importers keep working. The ban issue #41 imposes is on a *second* spelling of a
third module's name — `comeni_core.pipeline` surviving as an alias for
`comeni_core.artifact.pipeline` — which is a different thing and is how two spellings come to
disagree.
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
"""`_comparison` and `_computed_over` are imported above and deliberately absent here.

They are private and two test files reach them directly — `test_rules.py` for the comparison
predicate and `tests/regressions/test_rules.py` for A118's computed-`then` check. Importing them
keeps those tests working without inventing a public name for something that is not public, and
leaving them out of `__all__` is what says so.
"""

"""Thin by design: load the cached stack, call the pure verb.

Nothing is decided here. If a rule about what may feed what appears in this file, it is in the
wrong package — `mendel-resolver` is where a check is golden-testable and where the CLI can
reach it too.

**No private cache.** `registry.stack()` is already `lru_cache`d on the registry digest, and a
second cache here would pay the 244ms cold load a second time — the mistake `checked.py`'s
docstring records.
"""

from comeni_core.plan.draft import DraftGraph
from comeni_core.review.verdict import Verdict
from mendel_resolver import compatibility
from mendel_resolver import validate as verb

from mendel_api.services import registry


def of(graph: DraftGraph) -> Verdict:
    return verb.validate(graph, registry.stack())


def index() -> compatibility.Compatibility:
    return compatibility.index(registry.stack())

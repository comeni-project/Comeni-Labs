"""`ops.check` for a registry in this exact state, computed once.

**Extracted from `services/contracts.py` in phase 5**, when the queue became a second caller.
The cache key is the registry's digest rather than a clock, so a changed registry invalidates
it and an unchanged one never re-reads — phase 4 §3.1, unchanged. What is new is only that two
services share it; a second private `lru_cache` in `queue.py` would have paid the cold cost
twice, on the home page, and gone stale independently of this one.

**The cold path is what breaks first at scale.** Measured on this registry: 0.39s for the
value half and 0.09s for the conformance half, over twelve contracts. At the 5,800 the design
says these pages must survive that is roughly three minutes, and the fix then is a table the
worker writes — the operator's decision on 2026-08-18 deliberately declined it for now.

**Per process.** Two API workers each pay the cold cost once, and a write in one leaves the
other's cache warm until its next digest check. The commit changes the digest, so the window
is one request rather than unbounded.
"""

from functools import lru_cache

from comeni_core.artifact.digest import digest_of_directory
from mendel_forge import ops

from mendel_api.services import registry
from mendel_api.settings import settings


@lru_cache(maxsize=4)
def _run(digest: str) -> ops.CheckResult:
    """The digest is the argument rather than a global, so `lru_cache` does the invalidation
    and there is no hand-written expiry to get wrong."""
    return ops.check(
        ops.CheckRequest(
            registry_root=settings.registry_root,
            source_root=settings.source_root,
            # The cached stack, or this verb reloads the registry underneath the cache and
            # the endpoint the cache exists for is the one it cannot reach.
            stack=registry.stack(),
        )
    )


def result() -> ops.CheckResult:
    return _run(str(digest_of_directory(settings.registry_root)))

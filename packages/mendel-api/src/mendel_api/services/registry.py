"""The loaded registry, for a registry in this exact state.

**Cached here and not in `mendel_resolver`.** A cache in a pure package is a module-level
mutable store on the path invariant 10 is about, and the 1346-test suite — the biggest single
beneficiary of phase 7 — is the caller a cache serves worst, because its tests mutate
registries in temporary directories. So the pure packages were made *faster* instead
(244ms → 17.8ms, audit A133/A134) and this is the only place that remembers. Spec §3.1.

**The same key as `checked.py`**, and deliberately: `digest_of_directory` is 4.6ms over the
shipped registry, and a changed registry invalidates by construction where a clock would serve
a stale answer for exactly as long as it was wrong.

**Two things this deliberately does not do.** It does not single-flight, so two concurrent cold
requests both load — at 244ms that mattered and at 17.8ms it does not (A144). And it does not
try to be cheap at scale: the digest is O(files), ~240ms at 2039 of them, so at the 5,800 the
design talks about the *key* becomes the cost (A138). The answer there is a key that is not
O(files), and nobody is near it.

**A `Layers` returned from here is shared between requests, so nothing may mutate it.** Every
current reader takes `.registry`, `.vocabulary` or `.rules` and reads.
"""

from functools import lru_cache

from comeni_core.artifact.digest import digest_of_directory
from mendel_resolver import layers
from mendel_resolver.layers import Layers

from mendel_api.settings import settings


@lru_cache(maxsize=4)
def _load(digest: str) -> Layers:
    """The digest is the argument rather than a global, so `lru_cache` does the invalidating
    and there is no hand-written expiry to get wrong. `maxsize=4` so switching between a couple
    of registries — which the tests do constantly — does not thrash."""
    return layers.load(settings.registry_root)


def digest() -> str:
    """The cache key, borrowed as an ETag.

    The same string that decides whether `_load` reloads decides whether a client's copy is
    stale — one definition of "the registry changed", not two. It costs 4.6ms per call, which
    the performance audit measured and which is the real per-request floor.
    """
    return str(digest_of_directory(settings.registry_root))


def stack() -> Layers:
    return _load(digest())

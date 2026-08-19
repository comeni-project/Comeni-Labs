"""The loaded registry, cached on its digest.

The same shape as `services/checked.py`, which phase 4 built for `ops.check`, and for the same
reason: a digest is a key a changed registry invalidates by construction, where a clock serves
a stale answer for exactly as long as it is wrong.

**It is here and not in `mendel_resolver`** — spec §3.1. A cache in a pure package is a
module-level mutable store on the path invariant 10 is about, and the test suite is the caller
a cache serves worst, because its tests mutate registries in temporary directories. The pure
packages got faster instead: 244ms to 17.8ms.
"""

from mendel_api.services import registry


def test_a_second_read_does_not_reload(monkeypatch):
    calls = []
    real = registry.layers.load

    def counting(root):
        calls.append(root)
        return real(root)

    monkeypatch.setattr(registry.layers, "load", counting)
    registry._load.cache_clear()

    registry.stack()
    registry.stack()

    assert len(calls) == 1, f"the registry was loaded {len(calls)} times"
    registry._load.cache_clear()


def test_a_changed_registry_invalidates_it(monkeypatch, broken_registry_copy):
    """The half that must fail otherwise: a cache that never invalidates passes the test above
    perfectly, and would serve a contract that no longer exists."""
    from mendel_api.settings import settings

    registry._load.cache_clear()
    first = registry.stack()
    assert first.registry.contracts["nf-core/fastqc@0.12.1"].nf_process == "FASTQC"

    changed = broken_registry_copy(
        "tools/nf-core/fastqc/fastqc.contract.yml", "nf_process: FASTQC", "nf_process: OTHER"
    )
    monkeypatch.setattr(settings, "registry_root", changed)

    second = registry.stack()
    assert second is not first
    assert second.registry.contracts["nf-core/fastqc@0.12.1"].nf_process == "OTHER"
    registry._load.cache_clear()


def test_the_services_read_through_it(monkeypatch):
    """Six call sites loaded a registry, and one module did it twice. A cache nothing reads is
    a cache that measures nothing — this is what makes the endpoint numbers real."""
    from mendel_api.services import contracts, sources

    calls = []
    real = registry.layers.load

    def counting(root):
        calls.append(root)
        return real(root)

    monkeypatch.setattr(registry.layers, "load", counting)
    registry._load.cache_clear()

    contracts.listing()
    sources.catalogue()
    contracts.listing()

    assert len(calls) == 1, f"three service calls loaded the registry {len(calls)} times"
    registry._load.cache_clear()

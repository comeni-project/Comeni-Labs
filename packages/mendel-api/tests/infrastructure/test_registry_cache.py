"""The loaded registry, cached on its digest.

The same shape as `services/checked.py`, which phase 4 built for `ops.check`, and for the same
reason: a digest is a key a changed registry invalidates by construction, where a clock serves
a stale answer for exactly as long as it is wrong.

**It is here and not in `mendel_resolver`** — spec §3.1. A cache in a pure package is a
module-level mutable store on the path invariant 10 is about, and the test suite is the caller
a cache serves worst, because its tests mutate registries in temporary directories. The pure
packages got faster instead: 244ms to 17.8ms.
"""

import os

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
        "tools/nf-core/fastqc/contract.yml", "nf_process: FASTQC", "nf_process: OTHER"
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


def test_an_unchanged_registry_is_not_hashed_again(monkeypatch):
    """The per-request cost: reading every byte to learn nothing changed (#216)."""
    hashed = []
    real = registry.digest_of_directory

    def counting(root):
        hashed.append(root)
        return real(root)

    monkeypatch.setattr(registry, "digest_of_directory", counting)
    registry._digest_for.cache_clear()
    registry.stack()
    registry.stack()
    registry.digest()
    assert len(hashed) == 1


def test_an_edit_of_the_same_size_is_still_seen(monkeypatch, broken_registry_copy):
    """`FASTQC` → `FASTQX` keeps the size; the modification time still moves."""
    import os
    import time

    from mendel_api.settings import settings

    changed = broken_registry_copy(
        "tools/nf-core/fastqc/contract.yml", "nf_process: FASTQC", "nf_process: FASTQC"
    )
    monkeypatch.setattr(settings, "registry_root", changed)
    registry._digest_for.cache_clear()
    first = registry.digest()
    contract = changed / "tools/nf-core/fastqc/contract.yml"
    text = contract.read_text().replace("nf_process: FASTQC", "nf_process: FASTQX")
    time.sleep(0.01)
    contract.write_text(text)
    os.utime(contract)
    assert registry.digest() != first
    registry._digest_for.cache_clear()


def test_a_copy_with_the_same_times_is_hashed_on_its_own(monkeypatch, tmp_path):
    """`copytree` keeps modification times, so a copy's signature could equal the original's:
    the root is part of the key, or one registry answers for another. The signature now carries
    inodes too, so two signatures are made equal here to keep the root's part watched."""
    import shutil

    from mendel_api.settings import settings

    hashed = []
    real = registry.digest_of_directory

    def counting(root):
        hashed.append(root)
        return real(root)

    monkeypatch.setattr(registry, "digest_of_directory", counting)
    monkeypatch.setattr(registry, "signature", lambda: ("the same",))
    registry._digest_for.cache_clear()
    registry.digest()
    copy = tmp_path / "registry"
    shutil.copytree(settings.registry_root, copy, ignore=shutil.ignore_patterns(".git"))
    monkeypatch.setattr(settings, "registry_root", copy)
    registry.digest()
    assert len(hashed) == 2
    registry._digest_for.cache_clear()


# ── what `signature()` must see (issue 223) ───────────────────────────────────────────────


def _layer(tmp_path, monkeypatch):
    from mendel_api.settings import settings

    root = tmp_path / "layer"
    (root / "tools" / "a").mkdir(parents=True)
    (root / "tools" / "a" / "tool.yml").write_text("declares: tool\n")
    monkeypatch.setattr(settings, "registry_root", root)
    return root


def test_a_symlinked_folder_added_to_the_layer_is_seen(tmp_path, monkeypatch):
    root = _layer(tmp_path, monkeypatch)
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    (elsewhere / "tool.yml").write_text("declares: tool\n")
    before = registry.signature()
    (root / "tools" / "b").symlink_to(elsewhere, target_is_directory=True)
    assert registry.signature() != before


def test_a_git_file_below_the_root_is_seen(tmp_path, monkeypatch):
    """Only the root's `.git` names the checkout; a `module/.git` is covered by the digest."""
    root = _layer(tmp_path, monkeypatch)
    (root / "tools" / "a" / "module").mkdir()
    before = registry.signature()
    (root / "tools" / "a" / "module" / ".git").write_text("gitdir: x\n")
    assert registry.signature() != before


def test_a_same_size_edit_within_one_tick_is_seen(tmp_path, monkeypatch):
    root = _layer(tmp_path, monkeypatch)
    path = root / "tools" / "a" / "tool.yml"
    status = path.stat()
    before = registry.signature()
    path.write_text("declares: tooL\n")
    os.utime(path, ns=(status.st_atime_ns, status.st_mtime_ns))
    assert registry.signature() != before

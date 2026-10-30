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

import os
import subprocess
from functools import lru_cache
from pathlib import Path

from comeni_core import yaml_strict
from comeni_core.artifact.digest import digest_of_directory
from mendel_compiler.locate import RELEASE_FILE
from mendel_resolver import layers
from mendel_resolver.layers import Layers

from mendel_api.settings import active_registry


@lru_cache(maxsize=4)
def _load(root: Path, digest: str) -> Layers:
    """The digest is the argument rather than a global, so `lru_cache` does the invalidating
    and there is no hand-written expiry to get wrong. `maxsize=4` so switching between a couple
    of registries — which the tests do constantly — does not thrash. **The root is part of the
    key**: a release can hold the same bytes as the last one, and a `Layers` carries its paths,
    which a pipeline's lockfile names."""
    return layers.load(root)


def signature() -> tuple[tuple[str, int, int, int, int], ...]:
    """Every file's size and modification time under the layer, never its bytes (#216).

    **What a request pays to learn nothing changed.** The digest read every byte of the layer,
    module sources included, on every request: 10.7ms measured on 2026-10-01, and growing with
    each tool. `stat` is enough to know whether to look again; the exact digest is still what a
    pipeline pins, computed only when this moves. Nanoseconds, the inode and the change time, so
    an edit that keeps a file's size, even within one modification-time tick, is still seen.

    **Every file, not `declared_entries`.** That allowlist cost 6ms of the 10.7 on its own,
    pathlib per file. A superset of what the digest covers is safe — a README edit costs one
    needless re-hash, never a stale answer — so this walks with `os.walk` and skips only the
    root's `.git`: a submodule's `.git` file names the checkout (issue #46), and a clone's `.git`
    directory would make its object store the most expensive thing here. A `.git` deeper down is
    the layer's own content, and the digest covers it. A symlinked folder is recorded, not
    followed, so adding one is seen and the load decides what it means (issue 223).
    """
    root = str(active_registry())
    found = []

    def entry(path: str) -> tuple[str, int, int, int, int]:
        status = os.lstat(path)
        return (
            os.path.relpath(path, root),
            status.st_size,
            status.st_mtime_ns,
            status.st_ctime_ns,
            status.st_ino,
        )

    for folder, folders, files in os.walk(root):
        at_root = folder == root
        folders[:] = sorted(name for name in folders if not (at_root and name == ".git"))
        for name in folders:
            if os.path.islink(os.path.join(folder, name)):
                found.append(entry(os.path.join(folder, name)))
        for name in sorted(files):
            if at_root and name == ".git":
                continue
            found.append(entry(os.path.join(folder, name)))
    return tuple(found)


@lru_cache(maxsize=4)
def _digest_for(root: Path, _signature: tuple) -> str:
    """**The root is part of the key**: `copytree` keeps modification times, so a copy's
    signature can equal the original's, and one registry would answer for another."""
    return str(digest_of_directory(root))


def digest() -> str:
    """The cache key, borrowed as an ETag.

    The same string that decides whether `_load` reloads decides whether a client's copy is
    stale — one definition of "the registry changed", not two. Exact, and recomputed only when
    `signature()` moves.
    """
    return _digest_for(active_registry(), signature())


def stack() -> Layers:
    return _load(active_registry(), digest())


def builder_types(stack: Layers) -> dict[str, frozenset[str]]:
    """The types a builder want, input, state or pin may name: the declared vocabulary without
    the `measurement.<id>` types `Vocabulary.with_measurements` derives (#346).

    Those route profiling, and the `mendel profile` CLI wants them; nothing in the builder does.
    Offered on the goal card, the walk saw `measurement.read_length` beside `fastq.reads`, and a
    model's `requires measurement.read_length` with no states would have been admitted. **One
    filter for every builder door** — the card, the prompt, each reply and each change — so a
    door added later does not reopen it by reading `stack.vocabulary.types` directly.
    """
    return {
        type_id: states
        for type_id, states in stack.vocabulary.types.items()
        if not type_id.startswith("measurement.")
    }


def registry_label() -> str:
    """What the builder loads, as a person can name it: `git describe` of the registry root
    (`v0.4.0-37-g98b4566`), else the layer digest. A fetched release is its tag; a production
    image without git metadata and without a release answers with the digest."""
    if (marker := active_registry().parent / RELEASE_FILE).is_file():
        return yaml_strict.load(marker)["tag"]
    try:
        described = subprocess.run(
            ["git", "-C", str(active_registry()), "describe", "--tags", "--always"],
            check=True, capture_output=True, text=True, timeout=5,
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        described = ""
    return described or digest()

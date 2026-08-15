"""A layer is a value, and stacking is one mechanism.

Invariant 11 talks about layers. Until this module the code had no such thing: `layers.load`
hand-assembled four loaders and passed `Path` around, so a layer had no identity (a name
recomputed by `layer_name(path)` at three call sites), no position (implicit in list order and
lost before provenance was recorded), and no contents (each loader discovered its own slice).

Four independent implementations disagreed on six axes — how to find files, how to key an
entry, what a missing directory means, what stacking means, whether displacement is recorded,
and whether the loader even knows its layer's name. Every finding in audit root B is a cell in
that table: A22, A23, A24, A25, A26, A35.

**Identity is `Layer.index`, never `Layer.name`.** Names are not unique — the lockfile's own
docstring says a lab stacking the public `registry/` over their own `registry/` hits it on day
one — and keying displacement on a name is A25.

`dataclasses` is not on `comeni-core`'s purity allowlist, so `Kind` and `Stacked` are plain
classes. That is a constraint worth keeping rather than working around: the allowlist has no
unknown unknowns.
"""

from collections.abc import Callable, Iterable, Sequence
from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from comeni_core.declared.layer import layer_name
from comeni_core.spell.marks import AnyKey, LayerName

MANIFEST = "registry.yml"
"""A layer's account of itself. Part of the layer, so a rename or a relicence is covered."""


def declared_entries(path: Path) -> list[Path]:
    """The files that *are* layer data: the `DeclaredKind` directories, and the manifest.

    **One definition, used by everything that reads a layer as a whole** — the layer digest
    in `comeni_core.artifact.digest` and the symlink refusal in `mendel_resolver.layers`.
    Both used to walk `path.rglob("*")`, and issue #46 showed why that is wrong: `registry/`
    became a git submodule, which puts a `.git` *file* beside the kinds reading
    `gitdir: ../../../.git/worktrees/<name>/modules/registry`. That names the worktree and
    the checkout location, so the layer digest became **machine-dependent** — two clones of
    the same pinned commit pinned different digests, with `make verify` green throughout
    because nothing compares a digest across machines.

    **An allowlist, not a list of things to skip.** A blocklist would have to name `.git`,
    then `.github`, then whatever the next layer repository carries. `DeclaredKind` already
    *is* the definition of a layer's contents (invariant 11), so a kind declared later is
    covered the day it is declared. Same reasoning that turned `test_egress.py` into an
    allowlist after `object`, `Path` and `Any` arrived one audit apart.

    **What this deliberately stops covering: anything outside a declared kind.** A symlink
    at the layer root is no longer refused, and it no longer needs to be — nothing loads it
    and nothing digests it, so it cannot reroute a pipeline or move a digest. Audit A9's
    exploit was a symlinked *contract*, which lives under `contracts/` and is still refused
    at both sites. Walking a real `.git` directory was also a cost nobody had measured:
    `--registry ../comeni-registry` against an ordinary clone rglobbed the object store.
    """
    found: list[Path] = []
    for root in [path / kind.value for kind in DeclaredKind] + [path / MANIFEST]:
        if root.is_symlink():
            # Returned rather than skipped, so the caller's refusal fires. `is_dir()`
            # *follows* a link, so a `contracts/` symlinked out of the layer would
            # otherwise be walked as an ordinary directory and its target hashed — which
            # is precisely A9 arriving through the allowlist written after it.
            found.append(root)
        elif root.is_dir():
            found += [p for p in root.rglob("*") if p.is_symlink() or p.is_file()]
        elif root.is_file():
            found.append(root)
    return found


class DeclaredKind(StrEnum):
    """The kinds of declared data. Invariant 11 says every one of them stacks.

    This said **four** from Plan 1.9 until Plan 1.15 added `ROLES`, and the number is now
    written in one place — here — rather than repeated in prose that drifts. That is A33's
    lesson and A71/A72's: two counts in `CLAUDE.md` were stale for three plans because
    nothing counted them. `len(DeclaredKind)` is the honest count.
    """

    CONTRACTS = "contracts"
    RULES = "rules"
    VOCABULARIES = "vocabularies"
    MEASUREMENTS = "measurements"
    ROLES = "roles"
    """The jobs a contract can do — the only thing a tier-3 rule may target.

    A kind rather than a field on the vocabulary because a lab vendoring a step type we do
    not ship must be able to name it in an overlay, and because a rule targeting a *type*
    is what audit A119 and A123 both are.
    """


class Policy(StrEnum):
    """What a higher layer does to an entry a lower layer already supplied."""

    REPLACE = "replace"
    """The whole entry is replaced. The default, and what a reader expects."""

    MERGE = "merge"
    """The entries are combined by the kind's `merge`. Opt-in and explicit in the file —
    `add_values` for a measurement, `add_states` for a vocabulary type. A35 is what happens
    when a loader merges some fields and replaces others without saying which."""

    DELETE_GROUP = "delete_group"
    """Every lower-layer entry sharing a *group* key is removed, not merely overwritten.
    Contracts: a higher layer supplying `nf-core/star/align@2.0.0` displaces
    `@1.11.0` even though the storage keys differ, because the module key is the same."""


class Layer(BaseModel):
    """Where a layer is, what it calls itself, and where it sits in the stack."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    path: Path
    name: LayerName
    """From `registry.yml`, falling back to the basename. **For rendering only.**"""
    index: int
    """Position in the stack, lowest first. **This is identity.** Two layers may share a
    name; they cannot share an index."""


def layers_of(paths: "Path | Sequence[Path]") -> list[Layer]:
    """Turn a stack of directories into `Layer` values, lowest first.

    The one place `layer_name()` is called. It used to be called at three sites, each of
    which could disagree about what a layer is called; a layer now carries its own name
    from the moment it exists, and its index — which is its identity — from the same
    moment.

    A bare `Path` is accepted for the single-layer case, which is the common one.
    """
    if isinstance(paths, Path | str):
        paths = [paths]
    return [
        Layer(path=Path(path), name=layer_name(Path(path)), index=index)
        for index, path in enumerate(paths)
    ]


class Displacement(BaseModel):
    """A higher layer replaced something a lower layer declared.

    One shape for all four kinds, so measurements and vocabularies — which have no `IRNode`
    to hang off — finally have somewhere to be reported. Every field is a `StrEnum` or a
    marked string, so this satisfies the egress leaf allowlist and may cross a door.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: DeclaredKind
    key: AnyKey
    winning_layer: LayerName
    displaced_layer: LayerName
    """Which layer lost.

    Under `REPLACE` each arriving layer records against the layer immediately below it, so a
    three-deep stack produces two records rather than one. Under `DELETE_GROUP` a single
    record can cover victims from several layers at once, and it names the **lowest** — the
    one a reader is most surprised to have lost."""
    displaced_keys: list[AnyKey] = []
    """The full keys removed, when the group key is not the storage key — contract ids, in
    the one kind that has a group.

    `list[ContractId]` until root C gave that alias a validator, at which point this field
    started refusing every key that is not literally `<owner>/<name>@<version>` — including
    the synthetic ones `test_layered.py` stacks, which exist precisely so the mechanism can
    be tested without a registry. It then became `Subject`, and **A64 broke it the same way**:
    that alias got a validator too, and `nf-core/samtools/sort@1.21.0` is not a subject.

    Twice is the argument for its own alias. `AnyKey` says what is true of every kind's key
    and nothing more — no whitespace, no control character, not empty — which refuses what
    invariant 14 is about and refuses nothing any kind legitimately keys on."""
    winning_key: AnyKey | None = None
    """Which incoming entry won, when the group key is not the storage key.

    A layer may legitimately hold two versions of one module, so naming the group is not
    enough — the record has to name the one routing will actually prefer, or it can
    contradict the build it describes. `ShadowRecord.winning_id` carried this and the
    property is preserved rather than dropped. `None` when the key *is* the winner, which is
    every kind except contracts."""


class Kind[K, T]:
    """How one sort of declared data is found, parsed, keyed and merged.

    Everything a kind does *not* declare — recursion, `*.yml` and `*.yaml`, a missing
    subdirectory, stack order, recording what displaced what — belongs to `stack()` and is
    therefore identical for all four. That is the whole point.
    """

    def __init__(
        self,
        which: DeclaredKind,
        parse: Callable[[Path], Iterable[T]],
        key: Callable[[T], K],
        group: Callable[[T], K] | None = None,
        policy: Policy = Policy.REPLACE,
        merge: Callable[[T, T], T] | None = None,
        prefer: Callable[[Sequence[T]], T] | None = None,
    ) -> None:
        self.which = which
        self.parse = parse
        self.key = key
        self.group = group or key
        self.policy = policy
        self.merge = merge
        self.prefer = prefer
        if policy is Policy.MERGE and merge is None:
            raise ValueError(f"{which}: Policy.MERGE needs a merge function")


class Stacked[K, T]:
    """The result of stacking one kind across a layer stack."""

    def __init__(
        self,
        entries: dict[K, T],
        origin: dict[K, int],
        displaced: list[Displacement],
        claimed: set[Path],
    ) -> None:
        self.entries = entries
        self.origin = origin
        """Key -> the **index** of the layer that supplied it. An index, not a name (A25)."""
        self.displaced = displaced
        self.claimed = claimed
        """Every file `stack()` read. `layers.load` unions these and raises on the residue,
        so a file in a layer that nothing reads is an error rather than silence (A26)."""


def _files(directory: Path) -> list[Path]:
    """Every declared-data file under a subdirectory, recursively, in a stable order.

    **Recursive, and both extensions.** Three of the four loaders globbed one level and all
    four matched `*.yml` only, so a nested vocabulary and a contract named `.yaml` were both
    invisible while still being hashed into the layer digest — an overlay that did nothing
    looked exactly like one that worked (A26).
    """
    return sorted({*directory.rglob("*.yml"), *directory.rglob("*.yaml")})


def stack[K, T](layers: Sequence[Layer], kind: Kind[K, T]) -> Stacked[K, T]:
    """Load one kind across a layer stack. Later layers win, and say so."""
    entries: dict[K, T] = {}
    origin: dict[K, int] = {}
    displaced: list[Displacement] = []
    claimed: set[Path] = set()
    name_of = {layer.index: layer.name for layer in layers}

    for layer in layers:
        directory = layer.path / kind.which.value
        if not directory.exists():
            continue

        incoming: dict[K, T] = {}
        first_declared: dict[K, Path] = {}
        for path in _files(directory):
            claimed.add(path)
            for entry in kind.parse(path):
                key = kind.key(entry)
                if key in incoming:
                    # Between layers this is a declaration and is recorded. Twice inside one
                    # layer is a copy-paste, and resolving it by glob order would be the
                    # silent arbitrary pick invariant 8 exists to prevent.
                    here = path.relative_to(layer.path)
                    there = first_declared[key].relative_to(layer.path)
                    place = f"twice in {here}" if here == there else f"in {here} and in {there}"
                    raise ValueError(
                        f"{key} is declared {place}, both under layer {layer.path}. "
                        "Shadowing happens between layers, not inside one."
                    )
                incoming[key] = entry
                first_declared[key] = path
        if not incoming:
            continue

        if kind.policy is Policy.DELETE_GROUP:
            for group in sorted({str(kind.group(e)) for e in incoming.values()}):
                victims = sorted(
                    (k for k, e in entries.items() if str(kind.group(e)) == group), key=str
                )
                if not victims:
                    continue
                arrivals = [e for e in incoming.values() if str(kind.group(e)) == group]
                winner = kind.prefer(arrivals) if kind.prefer else arrivals[0]
                # Every victim of a group shares one origin: an arriving layer deletes the
                # whole group before adding its own, so a group's survivors can only ever
                # come from the layer that last supplied it. This was `min(origin[k] ...)`
                # until a revert of `min` -> `max` changed nothing in any test, which is how
                # a line that cannot be wrong looks exactly like a line that is untested.
                losing = {origin[k] for k in victims}
                assert len(losing) == 1, f"victims of {group} span layers {sorted(losing)}"
                displaced.append(
                    Displacement(
                        kind=kind.which,
                        key=group,
                        winning_layer=layer.name,
                        displaced_layer=name_of[losing.pop()],
                        displaced_keys=[str(k) for k in victims],
                        winning_key=str(kind.key(winner)),
                    )
                )
                for victim in victims:
                    del entries[victim]
                    origin.pop(victim, None)
        else:
            for key in sorted(incoming, key=str):
                if key in entries:
                    # A key already here can only have come from a *lower* layer: a repeat
                    # inside one layer raises above, so `origin[key] != layer.index` was a
                    # condition that could never be false — the same shape as the `min`/`max`
                    # this module already turned into an assertion. Reverting it changed no
                    # test, which is how a guard on an impossible case reads as a guard.
                    assert origin[key] != layer.index, f"{key} re-declared in one layer"
                    displaced.append(
                        Displacement(
                            kind=kind.which,
                            key=str(key),
                            winning_layer=layer.name,
                            displaced_layer=name_of[origin[key]],
                        )
                    )

        for key, entry in incoming.items():
            if kind.policy is Policy.MERGE and key in entries and kind.merge is not None:
                entries[key] = kind.merge(entries[key], entry)
            else:
                entries[key] = entry
            origin[key] = layer.index

    return Stacked(entries, origin, displaced, claimed)

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

import yaml
from pydantic import BaseModel, ConfigDict, ValidationError

from comeni_core import yaml_strict
from comeni_core.declared.layer import layer_name
from comeni_core.diagnostics import coded
from comeni_core.spell.marks import AnyKey, LayerName

MANIFEST = "registry.yml"
"""A layer's account of itself. Part of the layer, so a rename or a relicence is covered."""


def declared_entries(path: Path) -> list[Path]:
    """The files that *are* layer data: every `.yml`/`.yaml` outside a dot-directory, and the
    manifest.

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
    if not path.is_dir():
        return []
    found = [
        p for p in path.rglob("*") if p.is_symlink() or (p.is_file() and _declared(p, path))
    ]
    return found


_DECLARED_SUFFIXES = (".yml", ".yaml")


def _declared(path: Path, root: Path) -> bool:
    """Is this file part of the layer's declared data, or something git left beside it?

    The allowlist is *by extension* rather than by directory, because a layer no longer has
    kind directories to enumerate (comeni-registry#1). What it must still exclude is what issue
    #46 found: a submodule's `.git` file holds
    `gitdir: …/worktrees/<name>/modules/registry`, which names the checkout and made the layer
    digest **machine-dependent**. `LICENSE` and `README.md` are the same class — real files a
    layer repository carries that are not layer data.

    **Judged relative to `root`, and that is the whole of this signature.** The first version
    read `path.parts` on an absolute path, so a layer checked out under `.worktrees/`,
    `.cache/` or `~/.local/` contained *nothing* — every file has a dot-prefixed ancestor
    somewhere above it. The layer digest became the SHA-256 of the empty string, and
    `CLAUDE.md` requires plans to execute in `.worktrees/`, so it fired on the sanctioned
    workflow while `make verify` stayed green.

    That is `test_architecture.py`'s own bug — a filter on absolute path parts matching the
    whole tree — arriving in production code, and issue #46's machine-dependent digest
    arriving a second time by a different route. Where a layer sits cannot decide what it
    contains.
    """
    if any(part.startswith(".") for part in path.relative_to(root).parts):
        # `.git`, `.github`, `.gitlab-ci` — metadata a layer repository carries, by a
        # convention every tool shares. Issue #46 found the `.git` case the expensive way: a
        # submodule's `.git` file holds `gitdir: …/worktrees/<name>/modules/registry`, so
        # hashing it made the layer digest machine-dependent. `.github/workflows/ci.yml` is
        # the same thing wearing a `.yml`, and `comeni-registry` is the first layer to have
        # one — which is what caught the absolute-path version of this check.
        return False
    return path.suffix in _DECLARED_SUFFIXES or path.name == MANIFEST


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


def _nested_layers(root: Path) -> list[Path]:
    """Directories under `root` that are layers in their own right.

    **A layer does not contain another layer.** Since comeni-registry#1 a kind is read from the
    file rather than the directory, so `stack()` globs the whole layer — and without this a lab
    overlay checked out *inside* the public registry would be swallowed by it, its files loaded
    as though they were the base layer's own. That is not hypothetical: `--registry` takes
    several roots, and putting one inside another is an ordinary mistake to make.

    A directory carrying its own `registry.yml` is the marker, because that file is already
    what a layer uses to name itself.
    """
    return [p.parent for p in root.rglob(MANIFEST) if p.parent != root]


def _files(directory: Path) -> list[Path]:
    """Every declared-data file in a layer, recursively, in a stable order.

    **Recursive, and both extensions.** Three of the four loaders globbed one level and all
    four matched `*.yml` only, so a nested vocabulary and a contract named `.yaml` were both
    invisible while still being hashed into the layer digest — an overlay that did nothing
    looked exactly like one that worked (A26).

    **`_declared` decides, so the loader and the digest cannot disagree.** They did: this
    globbed `*.yml` with no dot-exclusion while `declared_entries` had one, so a layer
    repository's own `.github/workflows/ci.yml` was hashed by neither and *loaded* by this —
    refused as a contract with `MD0010`. `comeni-registry` is the first layer to carry CI of
    its own, and it found this on the first run. There is one answer to "what are a layer's
    files" now, which is what invariant 11 already claimed.
    """
    found = {*directory.rglob("*.yml"), *directory.rglob("*.yaml")}
    return sorted(p for p in found if _declared(p, directory))



DECLARES = "declares"
"""The key by which a file says what it is.

**Not `kind:`** — a measurement already has one, and it means the kind of its *value*
(`integer`, `enum`). Two meanings for one key in the same file is how a loader comes to strip a
field it did not write, which is exactly what happened the first time this was implemented.
"""

_KIND_OF = {
    "contract": DeclaredKind.CONTRACTS,
    "rule": DeclaredKind.RULES,
    "vocabulary": DeclaredKind.VOCABULARIES,
    "measurement": DeclaredKind.MEASUREMENTS,
    "role": DeclaredKind.ROLES,
}
"""The singular a file writes, to the kind it means. Derived from `DeclaredKind` by hand rather
than by stripping an `s`, because `vocabularies` is not `vocabularys`."""


def declared_kind(path: Path) -> DeclaredKind:
    """What this file says it is. `MD0010` if it says nothing, `MD0011` if it says nonsense.

    **This is the whole of comeni-registry#1.** A layer used to be one directory per kind
    because the directory was how the loader knew what a file was; a file that announces itself
    can live anywhere, so a laboratory can group a tool's contract, its types and its rule
    together instead of navigating three trees for one module.

    What weakened, recorded rather than discovered: the directory prevented a misfiled document
    *by construction*, so a misspelled `contract/` was caught by `MD0003`. A misspelled
    `declares:` can only be *detected*, which is `MD0011`. Same class of error, one less
    guarantee.
    """
    try:
        data = yaml_strict.load(path)
    except yaml.YAMLError as error:
        # `MD0001` belongs here as well as in `stack()`: since this function reads the file
        # *first*, a file that does not parse now fails on the way in, and an uncoded parser
        # error would escape ahead of the code written for exactly this.
        raise ValueError(coded("MD0001", f"{path} is not valid YAML.\n  {error}")) from error
    if not isinstance(data, dict) or DECLARES not in data:
        raise ValueError(
            coded(
                "MD0010",
                f"{path} does not say what it is. Every declared file needs a "
                f"`{DECLARES}:` line — one of {', '.join(sorted(_KIND_OF))}.",
            )
        )
    said = data[DECLARES]
    if said not in _KIND_OF:
        raise ValueError(
            coded(
                "MD0011",
                f"{path} declares {said!r}, which is not a kind of declared data. "
                f"Expected one of {', '.join(sorted(_KIND_OF))}.",
            )
        )
    return _KIND_OF[said]


def stack[K, T](layers: Sequence[Layer], kind: Kind[K, T]) -> Stacked[K, T]:
    """Load one kind across a layer stack. Later layers win, and say so."""
    entries: dict[K, T] = {}
    origin: dict[K, int] = {}
    displaced: list[Displacement] = []
    claimed: set[Path] = set()
    name_of = {layer.index: layer.name for layer in layers}

    for layer in layers:
        # **The layer, not a subdirectory of it.** Which files belong to this kind is decided
        # by what each one declares, so the layout is the author's business (comeni-registry#1).
        # `registry.yml` is the layer's account of *itself*, read by `layer_name` before any
        # kind runs — it declares nothing and is exempt, exactly as it was from the
        # unclaimed-file check when kinds were directories.
        nested = _nested_layers(layer.path)
        mine = [
            p
            for p in _files(layer.path)
            if p != layer.path / MANIFEST
            and not any(p.is_relative_to(other) for other in nested)
            and declared_kind(p) is kind.which
        ]
        if not mine:
            continue

        incoming: dict[K, T] = {}
        first_declared: dict[K, Path] = {}
        for path in mine:
            claimed.add(path)
            where = path.relative_to(layer.path)
            try:
                # `list(...)` before the loop: `kind.parse` returns an `Iterable`, and a
                # generator would raise inside the body below — where `path` is still in
                # scope but this `try` is not.
                parsed = list(kind.parse(path))
            except yaml.YAMLError as error:
                raise ValueError(
                    coded("MD0001", f"{where} in layer {layer.path} is not valid YAML.\n  {error}")
                ) from error
            except ValidationError as error:
                singular = kind.which.value.removesuffix("s")
                raise ValueError(
                    coded("MD0002", f"{where} in layer {layer.path} is not a valid {singular}.\n")
                    + "\n".join(
                        f"  {'.'.join(str(part) for part in problem['loc']) or '(root)'}: "
                        f"{problem['msg']}"
                        for problem in error.errors()
                    )
                ) from error
            for entry in parsed:
                key = kind.key(entry)
                if key in incoming:
                    # Between layers this is a declaration and is recorded. Twice inside one
                    # layer is a copy-paste, and resolving it by glob order would be the
                    # silent arbitrary pick invariant 8 exists to prevent.
                    here = path.relative_to(layer.path)
                    there = first_declared[key].relative_to(layer.path)
                    place = f"twice in {here}" if here == there else f"in {here} and in {there}"
                    raise ValueError(
                        coded("MD0006", f"{key} is declared {place}, both under layer "
                        f"{layer.path}. Shadowing happens between layers, not inside one.")
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

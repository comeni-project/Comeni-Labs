"""Loading a stack of registry layers, in the one order that works.

A layer is a directory of files that each declare their own `DeclaredKind`, and the kinds are
not independent:

    measurements  ->  vocabulary (a measurement derives a `measurement.<id>` type)
                  ->  registry   (contracts are validated against that vocabulary,
                  ->              and against the roles they claim to fill)
                  ->  rules      (a rule is validated against all of the above)

Getting that order wrong does not raise where the mistake is. Loading the vocabulary before
the measurements gives a vocabulary with no `measurement.*` types, so every profiling
contract fails to load with `UnknownTypeError` pointing at the contract rather than at the
caller — which is what happened the first time this was four separate calls in five places.
One function, so the order is a fact rather than a convention.

`roles` joins between the vocabulary and the registry (Plan 1.15): a contract declares the
roles it fills, so the names must exist before a contract is checked against them, and
nothing above it depends on a role.
"""

from collections.abc import Sequence
from pathlib import Path

from comeni_core.declared.layered import (
    Displacement,
    bucket,
    declared_entries,
    layers_of,
    stack,
)
from comeni_core.declared.measurement import MeasurementRegistry
from comeni_core.declared.registry import Registry
from comeni_core.declared.roles import RoleVocabulary
from comeni_core.declared.vocabulary import UnknownStateError, Vocabulary
from comeni_core.diagnostics import coded
from pydantic import BaseModel, ConfigDict, Field

from mendel_resolver.rules import RuleTable


class Layers(BaseModel):
    """Everything a build needs from disk, loaded and cross-validated."""

    model_config = ConfigDict(extra="forbid")

    measurements: MeasurementRegistry
    vocabulary: Vocabulary
    registry: Registry
    roles: RoleVocabulary
    rules: RuleTable

    paths: list[Path] = Field(default_factory=list)
    """The layer directories this was loaded from, in order.

    Carried so a build can lock itself: a build cannot pin what it does not know it loaded.
    `Lockfile.of` reduces these to *names* — never a filesystem path, which is meaningless
    on the machine that reads it. The name comes from each layer's `registry.yml`, falling
    back to its basename; it was the basename alone until audit A12.
    """

    displaced: list[Displacement] = Field(default_factory=list)
    """What a higher layer replaced, across every kind that stacks.

    Measurements and vocabularies had nowhere to report this — they have no `IRNode` to
    hang a record off — so an overlay changing what a module is told about a library it
    never saw was silent (A23, A24). One list, in load order, so the answer to "what did
    my overlay change" is one field rather than four conventions.
    """


def load(layers: str | Path | Sequence[str | Path]) -> Layers:
    """Load a registry layer stack. Later layers win, as everywhere else.

    A bare `str` is accepted because a `str` is also a `Sequence`, so refusing it by type
    is not something the signature can do: `load("registry")` would iterate the string
    into single characters and fail somewhere unrecognisable.
    """
    if isinstance(layers, str | Path):
        layers = [layers]
    layers = [Path(layer) for layer in layers]
    for layer in layers:
        # **Any declared file, not any kind directory.** Since comeni-registry#1 a layer is
        # files that say what they are, so a perfectly good layer may be one flat folder with
        # no `contracts/` in sight. What this still catches is the case it was written for: a
        # submodule that was never checked out, which leaves a directory that exists and is
        # empty.
        # **Completely empty, not merely holding no declared data.** An overlay that declares
        # nothing yet is legitimate — a lab creates the layer before it has anything to put in
        # it, and it carries a `registry.yml` naming itself. An unchecked-out submodule has
        # nothing at all, which is the case this was written for and the only one it should
        # refuse.
        if layer.is_dir() and not any(layer.iterdir()):
            raise ValueError(
                coded(
                    "MD0005",
                    f"{layer} holds no declared data — no `.yml` or `.yaml` file in it.\n"
                    "\n"
                    "If this is `registry/`, it is a git submodule and was not checked out:\n"
                    "\n"
                    "    git submodule update --init\n"
                    "\n"
                    "`git clone --recurse-submodules` avoids this. "
                    "See docs/guides/contributing.md.",
                )
            )
        # `declared_entries`, not `rglob("*")`: since issue #46 `registry/` is a git
        # submodule, so a bare walk descends into git metadata — and against an ordinary
        # clone passed as `--registry ../comeni-registry`, into the whole object store.
        # One definition of what a layer's files are, shared with the layer digest.
        for entry in sorted(declared_entries(layer)):
            if entry.is_symlink():
                # `digest_of_directory` refuses this too, but that is publish time and
                # publication is the door with no undo — by then the reroute has already
                # been emitted. A layer is a unit that gets distributed: a link out of it
                # is meaningless to whoever receives it, and a link inside it is a copy
                # with extra steps. Audit 2026-08-06, A9.
                raise ValueError(
                    coded("MD0004", f"registry layer {layer} contains a symlink at "
                    f"{entry.relative_to(layer)}. A layer may not contain one: the loader "
                    "follows it and the layer digest cannot, so the bytes routed on would "
                    "not be the bytes pinned.")
                )
    stacked = layers_of(layers)
    # **One walk for five kinds.** `stack()` computes this itself when it is not given one,
    # which is what made a load 244ms: five kinds meant five walks of the layer and five
    # parses of every file to read its `declares:` line. Audit A133.
    buckets = bucket(stacked)
    measured = stack(stacked, MeasurementRegistry.kind(), buckets=buckets)
    measurements = MeasurementRegistry.of(measured)
    declared_types = stack(stacked, Vocabulary.kind(), buckets=buckets)
    vocabulary = Vocabulary.of(declared_types).with_measurements(measurements)
    named_roles = stack(stacked, RoleVocabulary.kind(), buckets=buckets)
    roles = RoleVocabulary(names=frozenset(named_roles.entries))
    try:
        contracts = stack(stacked, Registry.kind(vocabulary), buckets=buckets)
    except UnknownStateError as error:
        raise _blame_the_overlay(error, declared_types.displaced) from error
    registry = Registry.of(contracts, stacked)
    # After the registry is assembled rather than inside `Registry.kind`'s parse, so the
    # message can name every role that exists across the whole stack. A contract in the base
    # layer may legitimately fill a role an overlay declares.
    for contract in registry.all():
        roles.check(contract.id, contract.roles)
    decided = stack(stacked, RuleTable.kind(registry, vocabulary, measurements), buckets=buckets)
    rules = RuleTable.of(decided, stacked)
    # After assembly, so a decision may read a fact a derivation in another file
    # supplies. Same reason `roles.check` runs here rather than inside a parse.
    rules.check_premise_names(measurements)
    # `_every_file_is_claimed` was here until comeni-registry#1, emitting `MD0003` for a
    # `.yml` no kind read. It is retired because it can no longer fire: a file either declares
    # a kind and is loaded wherever it sits, or declares none and is refused by `MD0010`.
    #
    # **A26 is prevented now rather than detected.** Its defect was an overlay contract saved
    # as `.yaml` that every loader ignored while the layer digest hashed it — the lockfile said
    # the overlay was there and the pipeline said it was not. A file that announces itself is
    # read from anywhere in the layer, so there is no position left for it to be invisible in.
    return Layers(
        measurements=measurements,
        vocabulary=vocabulary,
        registry=registry,
        roles=roles,
        rules=rules,
        paths=list(layers),
        displaced=[
            *measured.displaced,
            *declared_types.displaced,
            *named_roles.displaced,
            *contracts.displaced,
            *decided.displaced,
        ],
    )


def _blame_the_overlay(
    error: UnknownStateError, displaced: list[Displacement]
) -> UnknownStateError:
    """A35 — join the state that is missing to the layer that removed it.

    A contract cannot know why a state it has always required stopped existing; the loader
    can, because it stacked the vocabulary a moment earlier. Without the join the build
    dies naming a base contract in a layer the laboratory does not own, which is the most
    expensive kind of correct error message.
    """
    culprit = next((d for d in displaced if d.key == error.type_id), None)
    if culprit is None:
        return error
    return UnknownStateError(
        f"{error}\n"
        f"  layer {culprit.winning_layer!r} replaced the declared states of "
        f"{culprit.key!r}, which layer {culprit.displaced_layer!r} declared.\n"
        f"  `states:` replaces the set. An overlay meaning to *add* a state declares "
        f"`add_states:` instead.",
        type_id=error.type_id,
        state=error.state,
    )

"""Loading a stack of registry layers, in the one order that works.

A layer is a directory holding `contracts/`, `rules/`, `vocabularies/` and `measurements/`,
and the four are not independent:

    measurements  ->  vocabulary (a measurement derives a `measurement.<id>` type)
                  ->  registry   (contracts are validated against that vocabulary)
                  ->  rules      (a rule is validated against all three)

Getting that order wrong does not raise where the mistake is. Loading the vocabulary before
the measurements gives a vocabulary with no `measurement.*` types, so every profiling
contract fails to load with `UnknownTypeError` pointing at the contract rather than at the
caller — which is what happened the first time this was four separate calls in five places.
One function, so the order is a fact rather than a convention.
"""

from collections.abc import Sequence
from pathlib import Path

from comeni_core.layer import layer_name
from comeni_core.layered import Displacement, layers_of, stack
from comeni_core.measurement import MeasurementRegistry
from comeni_core.registry import Registry
from comeni_core.vocabulary import UnknownStateError, Vocabulary
from pydantic import BaseModel, ConfigDict, Field

from mendel_resolver.rules import RuleTable


class Layers(BaseModel):
    """Everything a build needs from disk, loaded and cross-validated."""

    model_config = ConfigDict(extra="forbid")

    measurements: MeasurementRegistry
    vocabulary: Vocabulary
    registry: Registry
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
        for entry in sorted(layer.rglob("*")):
            if entry.is_symlink():
                # `digest_of_directory` refuses this too, but that is publish time and
                # publication is the door with no undo — by then the reroute has already
                # been emitted. A layer is a unit that gets distributed: a link out of it
                # is meaningless to whoever receives it, and a link inside it is a copy
                # with extra steps. Audit 2026-08-06, A9.
                raise ValueError(
                    f"registry layer {layer} contains a symlink at "
                    f"{entry.relative_to(layer)}. A layer may not contain one: the loader "
                    "follows it and the layer digest cannot, so the bytes routed on would "
                    "not be the bytes pinned."
                )
    stacked = layers_of(layers)
    measured = stack(stacked, MeasurementRegistry.kind())
    measurements = MeasurementRegistry.of(measured)
    declared_types = stack(stacked, Vocabulary.kind())
    vocabulary = Vocabulary.of(declared_types).with_measurements(measurements)
    with_contracts = [layer for layer in layers if (layer / "contracts").exists()]
    try:
        registry = _load_contracts(with_contracts, vocabulary)
    except UnknownStateError as error:
        raise _blame_the_overlay(error, declared_types.displaced) from error
    rules = RuleTable.load(
        [layer / "rules" for layer in layers],
        registry=registry,
        vocabulary=vocabulary,
        measurements=measurements,
        # The layer's name, for the same reason contracts get one: a rule block replacing
        # a lower layer's must say which layer it came from, and `rules/`'s basename is
        # "rules" everywhere. Audit A15.
        names=[layer_name(layer) for layer in layers],
    )
    return Layers(
        measurements=measurements,
        vocabulary=vocabulary,
        registry=registry,
        rules=rules,
        paths=list(layers),
        displaced=[*measured.displaced, *declared_types.displaced],
    )


def _load_contracts(with_contracts: list[Path], vocabulary: Vocabulary) -> Registry:
    return Registry.load(
        [layer / "contracts" for layer in with_contracts],
        vocabulary,
        # The layer's name, not its `contracts/` subdirectory and not its path. A shadow
        # record reaches a publish bundle, so this is the same identifier the lockfile
        # uses — and a path there would be both meaningless elsewhere and a leak.
        #
        # Read from `registry.yml` when the layer declares one, because a basename is not
        # an identity: `--registry .` produced `''`. Audit 2026-08-06, A12.
        names=[layer_name(layer) for layer in with_contracts],
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

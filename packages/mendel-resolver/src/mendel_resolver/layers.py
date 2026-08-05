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

from comeni_core.measurement import MeasurementRegistry
from comeni_core.registry import Registry
from comeni_core.vocabulary import Vocabulary
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
    `Lockfile.of` reduces these to basenames — a lockfile never stores a filesystem path,
    because a path is meaningless on the machine that reads it.
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
    measurements = MeasurementRegistry.load([layer / "measurements" for layer in layers])
    vocabulary = Vocabulary.load(
        [layer / "vocabularies" for layer in layers if (layer / "vocabularies").exists()]
    ).with_measurements(measurements)
    with_contracts = [layer for layer in layers if (layer / "contracts").exists()]
    registry = Registry.load(
        [layer / "contracts" for layer in with_contracts],
        vocabulary,
        # The layer's name, not its `contracts/` subdirectory and not its path. A shadow
        # record reaches a publish bundle, so this is the same identifier the lockfile
        # uses — and a path there would be both meaningless elsewhere and a leak.
        names=[layer.name for layer in with_contracts],
    )
    rules = RuleTable.load(
        [layer / "rules" for layer in layers],
        registry=registry,
        vocabulary=vocabulary,
        measurements=measurements,
    )
    return Layers(
        measurements=measurements,
        vocabulary=vocabulary,
        registry=registry,
        rules=rules,
        paths=list(layers),
    )

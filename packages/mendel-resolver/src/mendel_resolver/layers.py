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
from pydantic import BaseModel, ConfigDict

from mendel_resolver.rules import RuleTable


class Layers(BaseModel):
    """Everything a build needs from disk, loaded and cross-validated."""

    model_config = ConfigDict(extra="forbid")

    measurements: MeasurementRegistry
    vocabulary: Vocabulary
    registry: Registry
    rules: RuleTable


def load(layers: Path | Sequence[Path]) -> Layers:
    """Load a registry layer stack. Later layers win, as everywhere else."""
    if isinstance(layers, Path):
        layers = [layers]
    measurements = MeasurementRegistry.load([layer / "measurements" for layer in layers])
    vocabulary = Vocabulary.load(
        [layer / "vocabularies" for layer in layers if (layer / "vocabularies").exists()]
    ).with_measurements(measurements)
    registry = Registry.load(
        [layer / "contracts" for layer in layers if (layer / "contracts").exists()], vocabulary
    )
    rules = RuleTable.load(
        [layer / "rules" for layer in layers],
        registry=registry,
        vocabulary=vocabulary,
        measurements=measurements,
    )
    return Layers(
        measurements=measurements, vocabulary=vocabulary, registry=registry, rules=rules
    )

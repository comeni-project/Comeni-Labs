"""Closed state vocabularies. A type declares exactly the states it may carry."""

from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import TYPE_CHECKING

import yaml
from pydantic import BaseModel

if TYPE_CHECKING:  # `measurement` imports `profile`, which imports nothing from here
    from comeni_core.measurement import MeasurementRegistry


class UnknownTypeError(KeyError):
    """Raised when a type id has no vocabulary file."""


class UnknownStateError(ValueError):
    """Raised when a state is not declared for its type."""


class Vocabulary(BaseModel):
    types: dict[str, frozenset[str]]
    entry_channels: dict[str, str] = {}
    """How a type enters a pipeline when nothing upstream produces it.

    Declared per type rather than hardcoded in the compiler, so a type the compiler
    has never seen — from a pegi3s image, an in-house process — can say how it
    arrives without a code change. Absent means the default in
    `mendel_compiler.emit`.
    """

    @classmethod
    def load(cls, layers: "Path | Sequence[Path]") -> "Vocabulary":
        """Stacked like the registry: later layers win, keyed on type id.

        A laboratory adding a state — or, once the rule-tables spec lands, a measurement —
        needs types to stack the way contracts already do. Only contracts stacked before
        the 2026-08-03 audit, so a lab could ship modules but not the vocabulary they
        depend on.
        """
        if isinstance(layers, Path):
            layers = [layers]
        types: dict[str, frozenset[str]] = {}
        entry_channels: dict[str, str] = {}
        for directory in layers:
            for path in sorted(directory.glob("*.yml")):
                type_id = path.name.removesuffix(".yml")
                data = yaml.safe_load(path.read_text()) or {}
                types[type_id] = frozenset(data.get("states", []))
                if data.get("entry_channel"):
                    entry_channels[type_id] = data["entry_channel"]
        return cls(types=types, entry_channels=entry_channels)

    def with_measurements(self, registry: "MeasurementRegistry") -> "Vocabulary":
        """Derive a stateless `measurement.<id>` type per declaration.

        This is what makes profiling free: a measurement is a type a module produces, so
        "measure the read length" is an ordinary routing problem and the router needs no
        profiling code at all.

        Derived rather than declared twice: the measurement file already says what the
        measurement is, and a second vocabulary file saying it again is a thing to drift.
        Stateless because a measurement has a *value*, not a condition — `strandedness`'s
        three values are declared values, not states, and letting them be both would give
        routing two places to disagree.
        """
        types = dict(self.types)
        for measurement_id in registry.ids():
            types[f"measurement.{measurement_id}"] = frozenset()
        return Vocabulary(types=types, entry_channels=dict(self.entry_channels))

    def states_for(self, type_id: str) -> frozenset[str]:
        if type_id not in self.types:
            raise UnknownTypeError(type_id)
        return self.types[type_id]

    def validate(self, type_id: str, states: Iterable[str]) -> None:
        allowed = self.states_for(type_id)
        for state in states:
            if state not in allowed:
                raise UnknownStateError(
                    f"{state!r} is not a declared state for {type_id!r}; allowed: {sorted(allowed)}"
                )

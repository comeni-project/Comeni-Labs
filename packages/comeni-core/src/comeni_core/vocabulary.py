"""Closed state vocabularies. A type declares exactly the states it may carry."""

from collections.abc import Iterable, Sequence
from pathlib import Path

import yaml
from pydantic import BaseModel


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

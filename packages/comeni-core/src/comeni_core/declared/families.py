"""Load and query the declared families that group data types.

A family is the segment before the first dot in a type ID. Layer overlays may add families or
replace their descriptions. Validation rejects type IDs whose family is absent from the stack.
"""

from collections.abc import Iterable, Sequence
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from comeni_core import yaml_strict
from comeni_core.declared.layered import DeclaredKind, Kind, Policy, Stacked, layers_of, stack
from comeni_core.diagnostics import coded


class UnknownFamilyError(ValueError):
    """A type named a family no layer in the stack declares."""


def family_of(type_id: str) -> str:
    """The family a type belongs to: the part of its id before the first dot."""
    return type_id.split(".", 1)[0]


class Family(BaseModel):
    """One family, as a model choosing among them reads it."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str = Field(min_length=1, max_length=64)
    description: str = Field(min_length=1, max_length=200)
    """One line on what the family holds. The model picks from these, so it is the whole of
    what separates `alignment` from `genome` for a reader who does not know the ids."""


def _parse_family(path: Path) -> list[Family]:
    """Parse one family declaration, ignoring its loader-facing kind marker."""
    data = yaml_strict.load(path) or {}
    data.pop("declares", None)
    return [Family.model_validate(data)]


class FamilyVocabulary(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    families: dict[str, Family]

    @staticmethod
    def kind() -> Kind[str, Family]:
        """Keyed on the family id; a higher layer replaces a lower one's description."""
        return Kind(
            DeclaredKind.FAMILIES,
            parse=_parse_family,
            key=lambda family: family.id,
            policy=Policy.REPLACE,
        )

    @classmethod
    def of(cls, stacked: Stacked[str, Family]) -> "FamilyVocabulary":
        return cls(families=dict(stacked.entries))

    @classmethod
    def load(cls, layers: Path | Sequence[Path]) -> "FamilyVocabulary":
        """Load families from one or more layer roots."""
        return cls.of(stack(layers_of(layers), cls.kind()))

    def check(self, type_ids: Iterable[str]) -> None:
        """Reject the first type whose family is undeclared, in sorted order."""
        for type_id in sorted(type_ids):
            family = family_of(type_id)
            if family not in self.families:
                raise UnknownFamilyError(
                    coded(
                        "MD0316",
                        f"type {type_id!r} names family {family!r}, which no layer in this "
                        f"stack declares.\n  Families that do exist: "
                        f"{', '.join(sorted(self.families)) or '(none)'}",
                    )
                )

    def types_of(self, family_ids: Iterable[str], type_ids: Iterable[str]) -> list[str]:
        """Return all types in the requested families, sorted by type ID."""
        wanted = set(family_ids)
        return sorted(t for t in type_ids if family_of(t) in wanted)

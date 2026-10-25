"""Load and validate the closed vocabulary of contract roles.

Roles name jobs such as alignment or trimming. Layers may add role names, while contracts are
rejected if they name a role absent from the complete stack.
"""

from collections.abc import Sequence
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from comeni_core import yaml_strict
from comeni_core.declared.layered import DeclaredKind, Kind, Policy, Stacked, layers_of, stack
from comeni_core.diagnostics import coded
from comeni_core.spell.marks import _role_name


class UnknownRoleError(ValueError):
    """A contract named a role no layer in the stack declares."""


class RoleVocabulary(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    names: frozenset[str]

    @staticmethod
    def kind() -> Kind[str, str]:
        """Describe role files as replacement-stacked bare names."""

        def parse(path: Path) -> list[str]:
            declared = list((yaml_strict.load(path) or {}).get("roles", []))
            for name in declared:
                # Apply the same spelling rule to declarations and contract references.
                try:
                    _role_name(name)
                except ValueError as exc:
                    raise ValueError(coded("MD0302", f"{path}: {exc}")) from exc
            return declared

        return Kind(
            DeclaredKind.ROLES,
            parse=parse,
            key=lambda name: name,
            policy=Policy.REPLACE,
        )

    @classmethod
    def load(cls, layers: Path | Sequence[Path]) -> "RoleVocabulary":
        """Load role names from one or more layer roots."""
        stacked: Stacked[str, str] = stack(layers_of(layers), cls.kind())
        return cls(names=frozenset(stacked.entries))

    def check(self, contract_id: str, roles: Sequence[str]) -> None:
        """Refuse a contract naming a role nothing declares.

        The contract ID is used only to make any diagnostic actionable.
        """
        for role in roles:
            if role not in self.names:
                raise UnknownRoleError(
                    coded("MD0302", f"{contract_id} declares role {role!r}, which no layer in this "
                    f"stack declares.\n"
                    f"  Roles that do exist: {', '.join(sorted(self.names)) or '(none)'}")
                )

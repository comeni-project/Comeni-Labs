"""Load and validate the closed vocabulary of contract roles.

Roles name jobs such as alignment or trimming. Layers may add role names, while contracts are
rejected if they name a role absent from the complete stack.
"""

from collections.abc import Mapping, Sequence
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from comeni_core import yaml_strict
from comeni_core.declared.layered import DeclaredKind, Kind, Policy, Stacked, layers_of, stack
from comeni_core.diagnostics import coded
from comeni_core.spell.marks import _role_name


class UnknownRoleError(ValueError):
    """A contract named a role no layer in the stack declares."""


class RoleDeclaration(BaseModel):
    """One job: its name, and what it means in words a person reads when choosing it."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    explain: str = Field(min_length=1, max_length=600)


class RoleVocabulary(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    names: frozenset[str]
    explains: dict[str, str] = {}
    """What each role means, by name."""

    @staticmethod
    def kind() -> Kind[RoleDeclaration, str]:
        """Describe role files as replacement-stacked declarations."""

        def parse(path: Path) -> list[RoleDeclaration]:
            declared = []
            for entry in (yaml_strict.load(path) or {}).get("roles", []):
                # Apply the same spelling rule to declarations and contract references.
                try:
                    role = RoleDeclaration.model_validate(entry)
                    _role_name(role.id)
                except ValidationError as exc:
                    raise ValueError(coded(
                        "MD0302", f"{path}: a role is an `id` and an `explain`, not {entry!r}"
                    )) from exc
                except ValueError as exc:
                    raise ValueError(coded("MD0302", f"{path}: {exc}")) from exc
                declared.append(role)
            return declared

        return Kind(
            DeclaredKind.ROLES,
            parse=parse,
            key=lambda role: role.id,
            policy=Policy.REPLACE,
        )

    @classmethod
    def load(cls, layers: Path | Sequence[Path]) -> "RoleVocabulary":
        """Load role names from one or more layer roots."""
        stacked: Stacked[RoleDeclaration, str] = stack(layers_of(layers), cls.kind())
        return cls.of(stacked.entries)

    @classmethod
    def of(cls, entries: Mapping[str, RoleDeclaration]) -> "RoleVocabulary":
        """The vocabulary a stack of role files adds up to."""
        return cls(names=frozenset(entries), explains={k: r.explain for k, r in entries.items()})

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

"""The closed vocabulary of jobs a contract can fill.

A tier-3 rule targets a **role**, never a type id and never a contract. Audit A119 and A123
are one defect seen from two sides: the old format's `decides:` admitted `{param: X}` and
`{producer_of: T}`, so a rule about duplicate handling and a rule about which aligner to use
both had to key on `alignment.bam`, and REPLACE stacking resolved that collision by deleting
one of them. Reproduced 2026-08-15 — installing a lab's duplicate-handling overlay swapped
HISAT2 for STAR on a 50bp goal, and both builds passed `gate lint` at exit 0.

Naming the job instead also dissolves R20, the shape a lab writing overlay rules meets first:
a rule that named `nf-core/salmon@1.10.0` was refused because the contract was absent, where a
rule naming `alignment` is refused because *nothing fills that role*, which is the thing the
author can act on.

Roles are closed (invariant 7) and they stack (invariant 11), through the same `stack()` as
every other kind — so they live in a layer's `roles/` directory, because that is what
`stack()` reads.
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
        """Keyed on the role name itself.

        A higher layer declaring a role the base already has is a no-op rather than a
        displacement, which is the one place this kind differs from the other four: a role
        is a bare name with nothing to replace. `Policy.REPLACE` is still correct — it
        replaces the name with itself — and it keeps `stack()`'s displacement bookkeeping
        uniform rather than adding a sixth code path for the one kind that has no body.
        """

        def parse(path: Path) -> list[str]:
            declared = list((yaml_strict.load(path) or {}).get("roles", []))
            for name in declared:
                # Validated *here* as well as on `ModuleContract.roles`, because otherwise a
                # vocabulary could declare `Ribo-Depletion` — which loads — and no contract
                # could ever legally name it, `RoleName` having refused the spelling. A
                # declaration nothing can use is the same defect as a rule that can never
                # fire (A122): legal, silent, and useless.
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
        """Load the role vocabulary across a layer stack. **Layer roots, not `roles/`.**"""
        stacked: Stacked[str, str] = stack(layers_of(layers), cls.kind())
        return cls(names=frozenset(stacked.entries))

    def check(self, contract_id: str, roles: Sequence[str]) -> None:
        """Refuse a contract naming a role nothing declares.

        Takes the id and the roles rather than the contract, so `comeni_core.declared.contract` does
        not have to import this module to be type-checked against it — the same reason
        `layer_of` is not a field on `ModuleContract`.
        """
        for role in roles:
            if role not in self.names:
                raise UnknownRoleError(
                    coded("MD0302", f"{contract_id} declares role {role!r}, which no layer in this "
                    f"stack declares.\n"
                    f"  Roles that do exist: {', '.join(sorted(self.names)) or '(none)'}")
                )

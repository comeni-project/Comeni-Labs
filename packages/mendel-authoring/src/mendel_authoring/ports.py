"""What the pure core reads from the registry, and nothing more.

The shell owns the loaded layers; the core names the few lookups it needs as `Protocol`s and the
shell adapts to them — the arrow points shell → core, as `mendel_resolver/ports.py` does for the
resolver. A narrow port is also what lets the core's tests use a dictionary instead of a registry.
"""

from typing import Protocol

from comeni_core.declared.contract import ModuleContract


class Contracts(Protocol):
    """A contract by id. `comeni_core.declared.registry.Registry` satisfies it as it stands."""

    def get(self, contract_id: str) -> ModuleContract: ...


class Declared(Protocol):
    """What a step's card is written from: declared data, used as written."""

    def outputs(self, contract_id: str) -> list[str]:
        """The type ids a contract produces, in its declared order."""
        ...

    def tool(self, tool_id: str) -> str | None:
        """A tool's declared description (`tool.yml`), or `None` when none is declared."""
        ...

    def family(self, family_id: str) -> str | None:
        """A family's declared description, or `None`."""
        ...

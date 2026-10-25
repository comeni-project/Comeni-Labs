"""The contract registry: what exists, what produces what, and which layer won."""

from collections.abc import Sequence
from pathlib import Path

from pydantic import BaseModel

from comeni_core.declared.contract import ModuleContract
from comeni_core.declared.layered import (
    DeclaredKind,
    Displacement,
    Kind,
    Layer,
    Policy,
    Stacked,
    layers_of,
    stack,
)
from comeni_core.declared.vocabulary import Vocabulary
from comeni_core.spell.marks import LayerName


def module_key(contract_id: str) -> str:
    """A contract ID minus its version. Shadowing is decided on this, not the full ID."""
    return contract_id.rsplit("@", 1)[0]


class Registry(BaseModel):
    contracts: dict[str, ModuleContract]

    displaced: list[Displacement] = []
    """Declarations removed by higher layers, including the preferred winning contract."""

    layer_of: dict[str, int] = {}
    """Map each surviving contract ID to its supplying layer index.

    Provenance stays on the registry rather than the content-addressed contract, so contract
    digests do not depend on checkout location.
    """

    layer_order: list[LayerName] = []
    """The stack's names, lowest first — for rendering a record, never for comparing."""

    @staticmethod
    def kind(vocab: Vocabulary) -> Kind[str, ModuleContract]:
        """How contracts are found, keyed and stacked.

        Contract storage uses full IDs, while displacement groups all versions under the
        versionless module key.
        """
        return Kind(
            DeclaredKind.CONTRACTS,
            parse=lambda path: [ModuleContract.load(path, vocab)],
            key=lambda contract: contract.id,
            group=lambda contract: module_key(contract.id),
            policy=Policy.DELETE_GROUP,
            # The same `(-priority, id)` order `producers_of` returns, so the record names
            # the contract routing will actually prefer.
            prefer=lambda contracts: min(contracts, key=lambda c: (-c.priority, c.id)),
        )

    @classmethod
    def of(cls, stacked: Stacked[str, ModuleContract], layers: Sequence[Layer]) -> "Registry":
        return cls(
            contracts=dict(stacked.entries),
            displaced=list(stacked.displaced),
            layer_of=dict(stacked.origin),
            layer_order=[layer.name for layer in layers],
        )

    @classmethod
    def load(cls, layers: Path | Sequence[Path], vocab: Vocabulary) -> "Registry":
        """Load and stack contracts from one or more layer roots."""
        as_layers = layers_of(layers)
        return cls.of(stack(as_layers, cls.kind(vocab)), as_layers)

    def get(self, contract_id: str) -> ModuleContract:
        if contract_id not in self.contracts:
            raise KeyError(contract_id)
        return self.contracts[contract_id]

    def all(self) -> list[ModuleContract]:
        return sorted(self.contracts.values(), key=lambda c: c.id)

    def producers_of(self, type_id: str, states: frozenset[str]) -> list[ModuleContract]:
        # Deduplicated on contract id: a contract declaring several outputs of one type —
        # real `star/align` has three BAM outputs — otherwise appeared once per port, tied
        # with itself, and raised a tier-4 ambiguity a human had to clear between a thing
        # and itself.
        matches = {
            contract.id: contract
            for contract in self.contracts.values()
            for port in contract.produces
            if port.type_id == type_id and states <= port.state
        }
        return sorted(matches.values(), key=lambda c: (-c.priority, c.id))

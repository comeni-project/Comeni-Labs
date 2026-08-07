"""The contract registry: what exists, what produces what, and which layer won."""

from collections.abc import Sequence
from pathlib import Path

from pydantic import BaseModel

from comeni_core.contract import ModuleContract
from comeni_core.layered import (
    DeclaredKind,
    Displacement,
    Kind,
    Layer,
    Policy,
    Stacked,
    layers_of,
    stack,
)
from comeni_core.marks import LayerName
from comeni_core.vocabulary import Vocabulary


def module_key(contract_id: str) -> str:
    """A contract ID minus its version. Shadowing is decided on this, not the full ID."""
    return contract_id.rsplit("@", 1)[0]


class Registry(BaseModel):
    contracts: dict[str, ModuleContract]

    displaced: list[Displacement] = []
    """What this stack's higher layers removed. Was `list[ShadowRecord]`.

    `ShadowRecord` is deleted rather than kept as a projection: an abstraction with one
    kind opted out decays back into four loaders, which is the whole of root B. Its one
    distinctive property survives as `Displacement.winning_key` — a layer may hold two
    versions of one module, so a record naming only the module key can contradict the
    build it describes.
    """

    layer_of: dict[str, int] = {}
    """Which layer each surviving contract came from, **by index**.

    An index, not a name: names are not unique, and `--registry registry/ --registry
    ./registry` is a day-one collision that made `order.index(name)` answer about the
    wrong layer (A25). Identity is position.

    Here rather than on `ModuleContract` on purpose: a contract is content-addressed
    (audit A10), and a field recording where it was found would make its digest depend on
    the machine that read it — reopening A10 sideways. A `Registry` is never reachable
    from `PublishBundle`, so a mapping is legal here in a way it is not on the IR.
    """

    layer_order: list[LayerName] = []
    """The stack's names, lowest first — for rendering a record, never for comparing."""

    @staticmethod
    def kind(vocab: Vocabulary) -> Kind[str, ModuleContract]:
        """How contracts are found, keyed and stacked.

        The one kind that needs a `group`: the storage key is the full id and displacement
        is decided on the id minus its version, so `@2.0.0` displaces both `@1.11.0` and
        `@1.21.0`. Keying displacement on the full id would make a version bump ambiguity
        rather than a decision — invariant 11's reason for the module key.
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
        """Load contracts across a layer stack. **Layer roots, not `contracts/`.**

        The `names` argument is gone: it existed because this was handed
        `<layer>/contracts` directories and the layer's name lives one level up, so the
        caller had to supply what the loader could not see. A layer is now a value that
        carries its own name and index, so there is nothing left to forward.
        """
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

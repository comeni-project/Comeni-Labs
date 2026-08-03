"""The contract registry: what exists, what produces what, and which layer won."""

from collections.abc import Sequence
from pathlib import Path

from pydantic import BaseModel

from comeni_core.contract import ModuleContract
from comeni_core.vocabulary import Vocabulary


def module_key(contract_id: str) -> str:
    """A contract ID minus its version. Shadowing is decided on this, not the full ID."""
    return contract_id.rsplit("@", 1)[0]


class ShadowRecord(BaseModel):
    """A higher layer displaced every lower-layer contract for one module key."""

    module_key: str
    winning_id: str
    winning_layer: str
    displaced_ids: list[str]


class Registry(BaseModel):
    contracts: dict[str, ModuleContract]
    shadowed: list[ShadowRecord] = []

    @classmethod
    def load(cls, layers: Path | Sequence[Path], vocab: Vocabulary) -> "Registry":
        if isinstance(layers, Path):
            layers = [layers]

        contracts: dict[str, ModuleContract] = {}
        shadowed: list[ShadowRecord] = []

        for layer in layers:
            incoming = {}
            for path in sorted(layer.rglob("*.yml")):
                contract = ModuleContract.load(path, vocab)
                incoming[contract.id] = contract

            keys = {module_key(cid) for cid in incoming}
            for key in sorted(keys):
                displaced = sorted(c for c in contracts if module_key(c) == key)
                if not displaced:
                    continue
                # A layer may legitimately hold two versions of one module. Name the one
                # routing would actually prefer, so the record does not contradict the build:
                # the same (-priority, id) order producers_of returns.
                winner = min(
                    (c for cid, c in incoming.items() if module_key(cid) == key),
                    key=lambda c: (-c.priority, c.id),
                ).id
                shadowed.append(
                    ShadowRecord(
                        module_key=key,
                        winning_id=winner,
                        winning_layer=str(layer),
                        displaced_ids=displaced,
                    )
                )
                for cid in displaced:
                    del contracts[cid]

            contracts.update(incoming)

        return cls(contracts=contracts, shadowed=shadowed)

    def get(self, contract_id: str) -> ModuleContract:
        if contract_id not in self.contracts:
            raise KeyError(contract_id)
        return self.contracts[contract_id]

    def all(self) -> list[ModuleContract]:
        return sorted(self.contracts.values(), key=lambda c: c.id)

    def producers_of(self, type_id: str, states: frozenset[str]) -> list[ModuleContract]:
        matches = [
            contract
            for contract in self.contracts.values()
            for port in contract.produces
            if port.type_id == type_id and states <= port.state
        ]
        return sorted(matches, key=lambda c: (-c.priority, c.id))

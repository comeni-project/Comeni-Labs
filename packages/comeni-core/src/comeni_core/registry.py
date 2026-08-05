"""The contract registry: what exists, what produces what, and which layer won."""

from collections.abc import Sequence
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from comeni_core.contract import ModuleContract
from comeni_core.marks import ContractId, LayerName, ModuleKey
from comeni_core.vocabulary import Vocabulary


def module_key(contract_id: str) -> str:
    """A contract ID minus its version. Shadowing is decided on this, not the full ID."""
    return contract_id.rsplit("@", 1)[0]


class ShadowRecord(BaseModel):
    """A higher layer displaced every lower-layer contract for one module key.

    Every field is a declared ID and `extra` is forbidden, because this became reachable
    from `PublishBundle` when `PipelineIR.shadowed` landed. Until then nothing had walked
    it, and it was carrying `winning_layer` as an absolute filesystem path — straight into
    a publishable artifact, past the rule the lockfile has an explicit test for.
    """

    model_config = ConfigDict(extra="forbid")

    module_key: ModuleKey
    winning_id: ContractId
    winning_layer: LayerName
    """The layer's *name*, never where it sat. A path is meaningless on the machine that
    reads a published bundle, and says more about the machine that wrote it than anyone
    intended."""
    displaced_ids: list[ContractId]


class Registry(BaseModel):
    contracts: dict[str, ModuleContract]
    shadowed: list[ShadowRecord] = []

    @classmethod
    def load(
        cls,
        layers: Path | Sequence[Path],
        vocab: Vocabulary,
        names: Sequence[str] | None = None,
    ) -> "Registry":
        """`names[i]` is what layer `i` is called in a shadow record.

        Passed in rather than derived, because this method is handed `<layer>/contracts`
        directories and the layer's name lives one level up — knowledge the caller has and
        this does not. Defaulting to the directory's own name keeps every existing caller
        working and, crucially, keeps a *name* in that field rather than a path.
        """
        if isinstance(layers, Path):
            layers = [layers]
        layer_names = list(names) if names is not None else [layer.name for layer in layers]

        contracts: dict[str, ModuleContract] = {}
        shadowed: list[ShadowRecord] = []

        for layer, layer_name in zip(layers, layer_names, strict=True):
            incoming: dict[str, ModuleContract] = {}
            for path in sorted(layer.rglob("*.yml")):
                contract = ModuleContract.load(path, vocab)
                if contract.id in incoming:
                    # Shadowing *between* layers is a declaration and is recorded. Twice
                    # in one layer is a copy-paste, and resolving it by glob order would
                    # be the silent arbitrary pick invariant 8 exists to prevent.
                    raise ValueError(
                        f"{contract.id} is declared twice in {layer}: {path.name} "
                        f"duplicates an earlier file"
                    )
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
                        winning_layer=layer_name,
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

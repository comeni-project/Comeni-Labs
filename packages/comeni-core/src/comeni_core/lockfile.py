"""What a pipeline was built against, pinned by content.

Federation §4.1. A version string cannot pin a contract — a contract can be edited without
its `@version` moving, and in a private overlay it routinely is. Digests can.

Two deliberate absences:

**No filesystem paths.** A layer is identified by name and digest. Where it sat on the
machine that built it is meaningless to the machine that reads it, and invariant 15 keeps
paths out of anything that can be published.

**No timestamps.** Determinism is a test: the same inputs produce the same bytes. A
`generated_at` field would make every lockfile differ from every other one, and the
determinism tests would go from meaningful to noise.
"""

from collections.abc import Sequence
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from comeni_core.digest import digest_of, digest_of_directory
from comeni_core.ir import PipelineIR
from comeni_core.marks import ContainerRef, ContractId, Digest, LayerName
from comeni_core.registry import Registry


class LockedContract(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: ContractId
    digest: Digest
    container: ContainerRef | None = None
    """The container as the contract declared it, tag and all.

    Resolving a tag to an immutable digest needs a registry client, which means the
    network, which `comeni-core` may not have. That belongs with `mendel-api`, and the
    `sealed` profile's digests-required rule depends on it.
    """


class LockedLayer(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: LayerName
    digest: Digest


class Lockfile(BaseModel):
    """Enough to reproduce a build, and enough to detect that you cannot."""

    model_config = ConfigDict(extra="forbid")

    version: int = 1
    contracts: list[LockedContract] = Field(default_factory=list)
    layers: list[LockedLayer] = Field(default_factory=list)

    @classmethod
    def of(cls, ir: PipelineIR, registry: Registry, layers: Sequence[Path]) -> "Lockfile":
        """Pin the contracts this pipeline actually used, and the layers it came from.

        Used, not available: the example registry holds twelve contracts and the RNA-seq
        spine uses five. Pinning all twelve would report drift for a module the pipeline
        never touched, and a lockfile that cries wolf gets ignored.
        """
        used = sorted({node.contract_id for node in ir.nodes})
        return cls(
            contracts=[
                LockedContract(
                    id=contract_id,
                    digest=digest_of(registry.get(contract_id)),
                    container=registry.get(contract_id).container,
                )
                for contract_id in used
            ],
            layers=[
                LockedLayer(name=path.name, digest=digest_of_directory(path))
                for path in layers
            ],
        )

    def drift_against(
        self, ir: PipelineIR, registry: Registry, layers: Sequence[Path]
    ) -> list[str]:
        """Every way the world has moved since this lockfile was written.

        Returned as prose lines for a human, not as a structured diff, because the caller
        is `mendel upgrade` printing to a terminal and every line here is something a
        person has to decide about. Empty means reproducible.
        """
        found: list[str] = []

        # Deliberately not `Lockfile.of`. A contract deleted from the registry is one of
        # the things this method exists to report, and `of` calls `registry.get`, which
        # raises `KeyError` on exactly that contract — so routing the comparison through
        # `of` made the missing-contract case crash instead of report it.
        #
        # Each locked contract is then re-digested on its own terms, *not* by looking it up
        # among the ones the new pipeline happens to use. Drift asks "has anything I pinned
        # moved?", which is a question about the registry and has nothing to do with what
        # this re-resolve chose; whether a module dropped out of the pipeline is
        # `diff_ir`'s to report, and reporting it here as well would be noise. Deriving the
        # comparison from the new IR's nodes instead made `mendel upgrade` raise KeyError
        # the moment a rule change routed away from a locked contract — which is the one
        # thing upgrade exists to do.
        locked = {c.id: c for c in self.contracts}

        for contract_id, pinned in sorted(locked.items()):
            if contract_id not in registry.contracts:
                found.append(f"{contract_id} is no longer in the registry")
            elif digest_of(registry.get(contract_id)) != pinned.digest:
                found.append(f"{contract_id} has been edited since it was locked")

        used_now = {node.contract_id for node in ir.nodes} & set(registry.contracts)
        for added in sorted(used_now - set(locked)):
            found.append(f"{added} is used now but was not locked")

        # Layers compare **positionally**, not by name, because a registry is a stack and
        # its order is semantic: invariant 11 has a higher layer shadowing every
        # lower-layer contract for a module key. Comparing a name-keyed mapping — which is
        # what this did first — reported no drift at all when the stack was inverted, and
        # silently collapsed two layers that share a basename. The second is not exotic:
        # Task 8 names the public layer `registry/`, so a lab stacking it over their own
        # `registry/` hits it on day one.
        locked_names = [layer.name for layer in self.layers]
        current = [(path.name, digest_of_directory(path)) for path in layers]
        current_names = [name for name, _ in current]

        if locked_names != current_names:
            found.append(
                f"the layer stack changed: locked [{', '.join(locked_names) or '(none)'}], "
                f"now [{', '.join(current_names) or '(none)'}]"
            )
        else:
            for locked_layer, (name, digest) in zip(self.layers, current, strict=True):
                if locked_layer.digest != digest:
                    found.append(f"layer {name} has changed since it was locked")

        return found

"""Record the contracts and registry layers used to build a pipeline.

These fingerprints are stored in pipeline.yml and compared with the current
registry during mendel upgrade. Layer records use names rather than local
paths, and omit timestamps so identical inputs produce identical records."""

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, Field

from comeni_core.artifact.digest import digest_of, digest_of_directory
from comeni_core.declared.layer import layer_name
from comeni_core.declared.registry import Registry
from comeni_core.plan.ir import PipelineIR
from comeni_core.spell.marks import (
    CommitSha,
    ContainerRef,
    ContractId,
    Digest,
    LayerName,
    RepoPath,
    RepoUrl,
)

if TYPE_CHECKING:  # pragma: no cover — the import exists for the annotation only
    # `comeni_core.artifact.pipeline` imports this module, so a runtime import here would be
    # a cycle.
    from comeni_core.artifact.pipeline import Pipeline


class LockedContract(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: ContractId
    digest: Digest
    container: ContainerRef | None = None
    """Container reference as declared; tags are not resolved to immutable digests here."""


class Locator(BaseModel):
    """Optional repository coordinates for fetching a layer.

    Location remains separate from content identity. ``None`` means unknown; the compiler may
    discover these values, while this core model performs no Git operations.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    source: RepoUrl | None = None
    commit: CommitSha | None = None
    dirty: bool | None = None
    """Uncommitted edits under the layer: the commit alone does not rebuild it."""
    path: RepoPath | None = None
    """The layer's folder in the repository; `None` when it is the repository's top folder."""
    release: str | None = None
    """The registry release this layer is, when it was fetched as one (`v0.5.0`)."""


def _unknown(value: object) -> bool:
    return value is None


class LockedLayer(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    name: LayerName
    digest: Digest
    # Unknown locator fields stay out of the serialized artifact.
    source: RepoUrl | None = Field(default=None, exclude_if=_unknown)
    commit: CommitSha | None = Field(default=None, exclude_if=_unknown)
    dirty: bool | None = Field(default=None, exclude_if=_unknown)
    path: RepoPath | None = Field(default=None, exclude_if=_unknown)
    release: str | None = Field(default=None, exclude_if=_unknown)
    """A pipeline names the release it was built with. Omitted when unknown, so existing
    pipelines keep their digests."""


class Lockfile(BaseModel):
    """Contract and ordered registry-layer fingerprints for a pipeline."""

    model_config = ConfigDict(extra="forbid")

    version: int = 1
    contracts: list[LockedContract] = Field(default_factory=list)
    layers: list[LockedLayer] = Field(default_factory=list)

    @classmethod
    def of(cls, ir: PipelineIR, registry: Registry, layers: Sequence[Path],
           locators: Mapping[LayerName, Locator] | None = None) -> "Lockfile":
        """Fingerprint each used contract and each supplied registry layer.

        Contracts are deduplicated and sorted by ID. Layer order is preserved."""
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
                # Use the manifest name so moving a directory does not change its identity.
                LockedLayer(name=layer_name(path), digest=digest_of_directory(path),
                            **(locators or {}).get(layer_name(path), Locator()).model_dump())
                for path in layers
            ],
        )

    @classmethod
    def from_pipeline(cls, pipeline: "Pipeline") -> "Lockfile":
        """Recover the fingerprints stored in steps[].module and registry.layers.

        Contracts shared by multiple steps are deduplicated and sorted by ID."""
        pinned = {
            step.module.contract_id: LockedContract(
                id=step.module.contract_id,
                digest=step.module.digest,
                container=step.module.container,
            )
            for step in pipeline.steps
        }
        return cls(
            contracts=[pinned[key] for key in sorted(pinned)],
            layers=list(pipeline.registry.layers),
        )

    def drift_against(
        self, ir: PipelineIR, registry: Registry, layers: Sequence[Path]
    ) -> list[str]:
        """Describe changes between the recorded inputs and the current registry.

        Checks for edited or missing contracts, newly used contracts, and changes
        to layer names, order, or content. Returns human-readable messages; an
        empty list means no differences were found by these checks."""
        found: list[str] = []

        # Check every pinned contract, including ones the new pipeline no longer uses.
        # Handle missing contracts before looking them up in the registry.
        locked = {c.id: c for c in self.contracts}

        for contract_id, pinned in sorted(locked.items()):
            if contract_id not in registry.contracts:
                found.append(f"{contract_id} is no longer in the registry")
            elif digest_of(registry.get(contract_id)) != pinned.digest:
                found.append(f"{contract_id} has been edited since it was locked")

        used_now = {node.contract_id for node in ir.nodes} & set(registry.contracts)
        for added in sorted(used_now - set(locked)):
            found.append(f"{added} is used now but was not locked")

        # Compare the ordered stack: layer precedence affects contract selection.
        locked_names = [layer.name for layer in self.layers]
        current = [(layer_name(path), digest_of_directory(path)) for path in layers]
        current_names = [name for name, _ in current]

        if locked_names != current_names:
            found.append(
                f"the layer stack changed: locked [{', '.join(locked_names) or '(none)'}], "
                f"now [{', '.join(current_names) or '(none)'}]"
            )
        else:
            for locked_layer, (name, digest) in zip(self.layers, current, strict=True):
                if locked_layer.digest != digest:
                    # Include recovery coordinates when the build recorded them.
                    folder = f", in {locked_layer.path}" if locked_layer.path else ""
                    where = (f"; it was locked at {locked_layer.commit} of {locked_layer.source}"
                             f"{folder}" if locked_layer.commit and locked_layer.source else "")
                    found.append(f"layer {name} has changed since it was locked{where}")

        return found

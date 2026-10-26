"""Load the manifest that names a registry layer and declares its format level."""

from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, model_validator

from comeni_core import yaml_strict
from comeni_core.diagnostics import coded
from comeni_core.spell.marks import LayerName

REGISTRY_FORMAT = 2
"""Highest registry format understood by this runtime.

Increase the level when an older runtime could accept a layer but interpret it incorrectly.
Optional backward-compatible fields do not require a new level.
"""


class LayerManifest(BaseModel):
    """The strict, optional ``registry.yml`` at a layer root."""

    model_config = ConfigDict(extra="forbid")

    name: LayerName
    version: str = ""
    licence: str = ""
    description: str = ""

    requires_format: int = 1
    """Minimum registry format required by the layer; omitted manifests default to level 1."""

    layout: dict[str, list[str]] = Field(default_factory=dict)
    """Optional kind-to-directory policy enforced by registry lint, not by the loader."""

    @model_validator(mode="after")
    def _this_mendel_can_read_it(self) -> "LayerManifest":
        """Reject a layer that requires a registry format newer than this runtime."""
        if self.requires_format > REGISTRY_FORMAT:
            raise ValueError(
                coded(
                    "MD0020",
                    f"layer {self.name!r} needs registry format {self.requires_format} and this "
                    f"Mendel understands {REGISTRY_FORMAT}. This registry needs a newer Mendel — "
                    f"upgrade it, or pin the layer to an older commit.",
                )
            )
        return self

    @classmethod
    def of(cls, layer: Path) -> "LayerManifest | None":
        """The layer's manifest, or `None` if it does not declare one.

        Absent is ordinary rather than broken: a private overlay a lab assembled by hand
        is the common case, and requiring a manifest to load one would make the guard
        more annoying than the bug it closes.
        """
        path = Path(layer) / "registry.yml"
        if not path.exists():
            return None
        return cls.model_validate(yaml_strict.load(path))


def layer_name(layer: Path) -> LayerName:
    """Return the manifest name, falling back to the resolved directory basename."""
    manifest = LayerManifest.of(layer)
    if manifest is not None:
        return manifest.name
    return Path(layer).resolve().name

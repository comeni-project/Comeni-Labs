"""A registry layer's manifest: what the layer calls itself.

`registry.yml` sits at a layer's root beside `contracts/`, and Plan 1.7 added it for one
reason, written down at the time: *a layer that moves to its own repository cannot rely on
the directory it happened to be checked out into.* Nothing then read it.

Layer identity was `Path.name` — in `mendel_resolver.layers.load` and in `Lockfile.of` —
and a basename is not an identity. `--registry .` recorded `name: ''` into a published
bundle and into every `ShadowRecord` in it; renaming a checkout reported *"the layer stack
changed"* against a pipeline that had not moved a byte. Audit 2026-08-06, A12 and A7.
"""

from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from comeni_core import yaml_strict
from comeni_core.marks import LayerName


class LayerManifest(BaseModel):
    """The contents of a layer's `registry.yml`.

    `extra="forbid"`, for the reason A10 gave for every contract model: a key that is
    ignored is a key that can be misspelled in silence, and this file is the one a
    stranger reads to decide whether to trust the layer.
    """

    model_config = ConfigDict(extra="forbid")

    name: LayerName
    version: str = ""
    licence: str = ""
    kinds: list[str] = Field(default_factory=list)
    description: str = ""

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
    """What this layer is called — its manifest's name, or its directory's.

    Falling back to the basename keeps every manifest-less overlay working. The fallback
    is still a basename and still carries A12's weaknesses; declaring a manifest is how a
    layer opts out of them, which is the incentive that belongs here.
    """
    manifest = LayerManifest.of(layer)
    if manifest is not None:
        return manifest.name
    return Path(layer).resolve().name

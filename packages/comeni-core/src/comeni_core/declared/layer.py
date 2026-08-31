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

from pydantic import BaseModel, ConfigDict, Field, model_validator

from comeni_core import yaml_strict
from comeni_core.diagnostics import coded
from comeni_core.spell.marks import LayerName

REGISTRY_FORMAT = 2
"""The highest registry format this Mendel understands.

═══ WHY A FORMAT LEVEL AND NOT A MENDEL VERSION ══════════════════════════════════════════════

Plan 5B §2.1 asks for *"a version floor on the layer: `registry.yml` declares the minimum Mendel
it needs"*, and **there is no such number to declare.** `CLAUDE.md`: *releases are per package,
and versions are independent* — `comeni-core-v0.2.0` is not a Mendel version, and a registry
author asking *which release learned `{param}`?* would have to answer it for `mendel-resolver`
and `mendel-compiler` separately and get both right.

So the layer declares what it **uses** and Mendel declares what it **understands**, which is one
integer on each side and no cross-repository release archaeology. It is `metadata_version` in a
Python wheel and `version` in a Nextflow DSL directive: the same problem, solved the same way,
for the same reason.

The message a person sees is still §2.1's — *this registry needs a newer Mendel* — because that
is the sentence that has to be true, and it is true of either mechanism.

═══ WHEN TO BUMP IT ══════════════════════════════════════════════════════════════════════════

**When an older Mendel would read a new layer WRONGLY rather than not at all.** That is a
narrower test than "the format changed", and it is the whole value of the number:

- A new *optional* field an old Mendel ignores is not a bump. `extra="forbid"` already refuses
  it on the manifest, and elsewhere an ignored key is a key that can be misspelled in silence
  (A10) — which is a different problem with a different answer.
- **`entry_channel` gaining `{param}` IS a bump**, and it is why this exists. An old Mendel does
  no substitution, so it writes the seven literal characters `{param}` into Groovy and emits a
  pipeline that dies at launch. A refusal that names the cause is strictly better than a
  `.nf` nobody can read.

Level 1 is everything up to and including Plan 5A. **Level 2 is the `{param}` template.**

The two halves land in this order and it is the only order that works: this constant rises
*before* any registry declares `requires_format: 2`, because the registry's own CI pins an
engine commit and would otherwise refuse its own layer. The floor itself shipped one commit
earlier still, so that a Mendel predating the whole idea fails on the *field* rather than on
the Groovy.
"""


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
    description: str = ""

    requires_format: int = 1
    """The registry format level this layer uses. **Defaults to 1, which is every layer that
    exists today** — so no manifest has to be edited to keep working, and a layer that never
    uses a new feature never declares one.

    `REGISTRY_FORMAT` above is the other half and carries the argument, including the test for
    when this is worth bumping: an older Mendel reading the layer **wrongly**, not merely a
    format that changed."""

    layout: dict[str, list[str]] = Field(default_factory=dict)
    """Where this layer keeps each kind — `{"contract": ["tools/"], "role": ["roles/"]}`.

    **This replaced `kinds:`, which was read by nobody.** That field listed the kinds the layer
    held and its own comment said so: *"read by nobody and pinned by a test, which is the
    point"*. A self-description with no consumer can only rot, and it did — it named four kinds
    for the whole of Plan 1.15 Task 0, which shipped `roles/` beside it. A33's lesson in a file
    whose entire job is to describe itself.

    This one has a consumer: `mendel registry lint` refuses a file whose kind is not under one
    of the directories declared here. **A manifest that is the lint's argument cannot drift** —
    if it is wrong, the lint refuses files that are correctly placed, which is loud.

    **The loader ignores it entirely, and that is invariant 11 holding.** A layer's layout is
    the author's business: a file declares its own kind, so `layers.load` reads a flat folder
    as happily as a tree. What the *curated* registry does is hold itself to a layout its own
    CI enforces, which is nixpkgs's `pkgs/by-name` move. Empty means unenforced, which is every
    private overlay.
    """

    @model_validator(mode="after")
    def _this_mendel_can_read_it(self) -> "LayerManifest":
        """MD0020. **Refuse a layer from the future rather than misread it.**

        On the model rather than in `layers.load`, so every reader is covered by construction:
        `layer_name`, `mendel lint`, `Lockfile.of` and the loader all go through
        `LayerManifest.of`, and a check in one of them is a check the other three do not have.

        `REGISTRY_FORMAT` carries the argument for the number. What belongs here is why this is
        a **refusal**: the alternative is emitting a `.nf` with `params.{param}` in it, which
        fails inside Nextflow minutes later with a message about Groovy syntax, on a machine
        that has no idea a registry was ever involved.
        """
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
    """What this layer is called — its manifest's name, or its directory's.

    Falling back to the basename keeps every manifest-less overlay working. The fallback
    is still a basename and still carries A12's weaknesses; declaring a manifest is how a
    layer opts out of them, which is the incentive that belongs here.
    """
    manifest = LayerManifest.of(layer)
    if manifest is not None:
        return manifest.name
    return Path(layer).resolve().name

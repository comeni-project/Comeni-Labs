"""Declare module source, provenance, licensing, and layer ownership.

``module.yml`` describes the adjacent ``module/`` source directory. The declaration and source
stack on the same module key, while upstream-owned files inside ``module/`` are not parsed as
registry declarations.
"""

from collections.abc import Sequence
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from comeni_core import yaml_strict
from comeni_core.declared.layered import (
    MODULE_DIR,
    DeclaredKind,
    Kind,
    Policy,
    Stacked,
    layers_of,
    stack,
)
from comeni_core.spell.marks import Digest, ModuleKey, NfPath, SpdxId

EMITTED_UNDER = "modules"
"""Where a module lands in the *generated* pipeline, and therefore what `nf_include` is
prefixed with. `include { FASTQC } from './modules/nf-core/fastqc/main'`."""

ENTRY = "main"
"""The file `nf_include` names, without its `.nf`. nf-core's convention, and ours."""


def key_of(nf_include: str) -> str:
    """Derive a module key by removing optional ``modules/`` and ``/main`` affixes."""
    key = nf_include.removeprefix(f"{EMITTED_UNDER}/")
    return key.removesuffix(f"/{ENTRY}")


class Upstream(BaseModel):
    """Immutable upstream location used to verify a vendored module copy."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    repo: str
    """The clone URL. A `str` rather than a marked alias: it is not a payload field — nothing
    on this model crosses an egress door — and a URL has a shape this repository does not own,
    which is `ContainerRef`'s argument."""
    sha: str
    """The commit the copy was taken at. Forty hex characters, not a `Digest` — that alias is
    `sha256:` and sixty-four, which is a content digest and not a git object name."""
    path: NfPath
    """Where under `repo` the module sits — `modules/nf-core/star/align`."""


class Module(BaseModel):
    """One tool implementation and the metadata needed to locate and verify it."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: ModuleKey

    licence: SpdxId | None = None
    """SPDX ID for ``LICENSES/<id>.txt``; ``None`` uses the layer's own terms."""

    upstream: Upstream | None = None
    """Pinned source location, or ``None`` for code authored in the layer."""

    excluded: list[NfPath] = []
    """What was deliberately **not** copied, relative to `upstream.path`.

    Without it a drift check reports every module as differing from upstream forever: nf-core
    ships a `tests/` directory beside each module and we do not take it, so the honest
    comparison is *upstream minus what we said we would skip* rather than *upstream*.
    """

    at: Path | None = None
    """Directory containing ``module.yml``; assigned by the loader, never serialized."""

    digest: Digest | None = None
    """Optional content digest used to identify which vendored module changed."""

    @staticmethod
    def kind() -> Kind[str, "Module"]:
        """One `module.yml` declares one module. `Policy.REPLACE`, on the module key.

        No `group`: the key already *is* the group. A contract keys on `id@version` and groups
        on the module key, so it needs both; a module directory can hold exactly one copy of
        the source, so there is nothing for a second version to be.
        """

        def parse(path: Path) -> list["Module"]:
            data = dict(yaml_strict.load(path) or {})
            data.pop("declares", None)
            return [Module(**data, at=path.parent)]

        return Kind(
            DeclaredKind.MODULES,
            parse=parse,
            key=lambda module: module.id,
            policy=Policy.REPLACE,
        )

    @property
    def source(self) -> Path | None:
        """The directory upstream's tree was copied into, or `None` for a module not read
        off disk. `module/` beside the declaration, never inside it."""
        return None if self.at is None else self.at / MODULE_DIR

    @classmethod
    def load(cls, layers: Path | Sequence[Path]) -> Stacked[str, "Module"]:
        """Load modules from one or more layer roots."""
        return stack(layers_of(layers), cls.kind())

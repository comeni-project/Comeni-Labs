"""The tool's own source, declared — where a module comes from and what it may be used for.

**Why a `DeclaredKind` and not a directory somebody remembers to copy.** Until Plan 5 the
modules lived in `vendor/` in the *engine's* repository, beside the code that reads them, while
the contracts describing them lived in `registry/` — a different repository on a different
release cadence. So a contract and the thing it is a binding for were versioned apart, and
`MD0104` — the check that a contract still matches its module — compared two repositories that
nothing kept in step. `docs/design/federation.md` §6 had already put vendored modules in the
registry; the code had not caught up.

A module inside the layer makes the layer **self-sufficient**: `--registry X` is now everything
a build needs, an air-gapped site is a first-class customer (invariant 13), and a laboratory's
own process is declared the same way nf-core's is.

**What this file is not.** It is not the module. `module.yml` is a *statement about* the
directory beside it — where the code came from, at which commit, under which licence, and what
was deliberately not copied. The code itself is in `module/`, is never hand-edited, and is
checked against its pin by `comeni-vendor check`.

**`module.yml` lives beside `module/`, never inside it.** That is load-bearing rather than
tidy: everything under `module/` is upstream's, and upstream ships a `meta.yml` of its own with
no `declares:` line. A statement about the module has to sit where the loader can read it and
the vendor tool will never overwrite it — see `layered._in_module`.
"""

from collections.abc import Sequence
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from comeni_core import yaml_strict
from comeni_core.declared.layered import (
    DeclaredKind,
    Kind,
    Policy,
    Stacked,
    layers_of,
    stack,
)
from comeni_core.spell.marks import Digest, ModuleKey, NfPath, SpdxId


class Upstream(BaseModel):
    """Where this module was copied from, pinned so the copy can be checked against it.

    A `sha`, never a branch. `vendor/modules.json` recorded both and nf-core's own tooling
    reads the branch; a branch moves, so a check against it answers *does this match whatever
    upstream looks like today*, which is a different question from *is this still the code we
    reviewed*. `comeni-vendor check` asks the second one.
    """

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
    """One vendored tool implementation, declared by the layer that carries it.

    Keyed on the **module key** — `nf-core/star/align`, a `ModuleContract.id` minus its
    `@version` — which is deliberately the same key contracts group on under invariant 11.
    That is what makes A4.4 true without a new mechanism: the layer that wins the contract
    wins the module, because they displace on one key.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: ModuleKey
    licence: SpdxId
    """Points at `LICENSES/<id>.txt` at the layer root — the REUSE convention, one file per
    licence rather than one per module. At 1,600 tools a NOTICE per tool is that many
    near-identical copies of the MIT text in every diff, which nobody reads."""

    upstream: Upstream | None = None
    """Where the code came from, or `None`.

    **`None` is legal and it means a tool nobody vendored** — a laboratory's own process,
    written here rather than copied from anywhere. The absence is the honest statement that
    there is nothing to check the directory against, which is a different thing from a check
    that has not been run. `comeni-vendor check` skips it and says so.
    """

    excluded: list[NfPath] = []
    """What was deliberately **not** copied, relative to `upstream.path`.

    Without it a drift check reports every module as differing from upstream forever: nf-core
    ships a `tests/` directory beside each module and we do not take it, so the honest
    comparison is *upstream minus what we said we would skip* rather than *upstream*.
    """

    digest: Digest | None = None
    """The content digest of `module/` as vendored, if the tool recorded one.

    Optional because it is a convenience rather than the guarantee: the guarantee is the layer
    digest, which covers `module/` since Plan 5A (spec §9.1). A per-module digest lets
    `comeni-vendor check` say *which* module moved without re-fetching.
    """

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
            return [Module(**data)]

        return Kind(
            DeclaredKind.MODULES,
            parse=parse,
            key=lambda module: module.id,
            policy=Policy.REPLACE,
        )

    @classmethod
    def load(cls, layers: Path | Sequence[Path]) -> Stacked[str, "Module"]:
        """Load every module across a layer stack. **Layer roots, not `module/`.**"""
        return stack(layers_of(layers), cls.kind())

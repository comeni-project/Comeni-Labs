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
    """Which module a contract binds to, from the path it says its module is included at.

    **This is a derivation and not a new field, and that is the decision worth stating.**
    A contract already answers *which module does this describe* — `nf_include` is
    `modules/nf-core/fastqc/main`, which is exactly `modules/<key>/main`. A second field
    saying `module: nf-core/fastqc` would be a second source of truth that a lint would then
    have to check agreed with the first, and two fields that must agree are a field that
    will one day disagree.

    Until Plan 5A this question had no answer because it had no question: module source lived
    in `vendor/` in the engine's repository, and `conformance.module_path` computed a location
    under that root from `nf_include` directly. Once the source is *in the layer*, a location
    is no longer derivable — the module has to be looked up by key, and this is that key.

    Permissive on purpose. A laboratory's own process may be included from anywhere, so what
    is stripped is a leading `modules/` and a trailing `/main` if they are there, and what is
    left is the key. `local/tidy` is a key; so is `nf-core/star/align`.
    """
    key = nf_include.removeprefix(f"{EMITTED_UNDER}/")
    return key.removesuffix(f"/{ENTRY}")


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

    licence: SpdxId | None = None
    """Points at `LICENSES/<id>.txt` at the layer root — the REUSE convention, one file per
    licence rather than one per module. At 1,600 tools a NOTICE per tool is that many
    near-identical copies of the MIT text in every diff, which nobody reads.

    **`None` means the layer's own terms**, and it goes with `upstream: None`: a process a
    laboratory wrote here was not copied from anywhere, so there is nobody else's licence to
    name and inventing one would be a false statement in a legal field. `comeni-vendor add`
    always sets it, and refuses before fetching if the layer carries no text for it.
    """

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

    at: Path | None = None
    """The directory holding this `module.yml`, so `at / "module"` is the source.

    Set by `kind()`'s parse from the file it read, not declared in the file — a path written
    into a layer would name a machine, which is what invariant 15 keeps out of anything
    shareable and what issue #46 found in `digest_of_directory`. It is `None` for a `Module`
    constructed in a test or by hand, and every consumer has to cope with that rather than
    assume a module came off disk.
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
        """Load every module across a layer stack. **Layer roots, not `module/`.**"""
        return stack(layers_of(layers), cls.kind())

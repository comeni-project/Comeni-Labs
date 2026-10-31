"""Implement module fetching and pin verification independently of the CLI transport."""

import hashlib
import shutil
import subprocess
import tempfile
from collections.abc import Mapping
from pathlib import Path

import yaml
from comeni_core import yaml_strict
from comeni_core.declared.layered import MODULE_DIR
from comeni_core.declared.module import Module, Upstream
from comeni_core.diagnostics import coded

MANIFEST = "module.yml"
"""The declaration stored beside ``module/``.

``add`` replaces the module directory wholesale, so declarations inside it would be destroyed.
Everything under ``module/`` is treated as upstream source rather than declared layer data.
"""

TOOLS = "tools"
"""The curated registry's tool directory; other layers may choose a different layout."""

REPOS = {"nf-core": "https://github.com/nf-core/modules.git"}
"""Known source names and clone URLs; callers can supply a custom repository and path."""

PREFIX = {"nf-core": "modules/nf-core"}
"""Where under each known repository the modules sit."""

SOURCE_LICENCE = {"nf-core": "MIT"}
"""What a source's module code arrives under, which is not its tools' licence (`meta.yml`): a
GPL tool stays in its container, and only the source's wrapper is vendored."""

LICENCES = "LICENSES"
"""Directory containing one licence text per SPDX identifier, following REUSE conventions."""

EXCLUDED = ["tests"]
"""Paths omitted from a vendored module by default.

Exclusions are recorded in ``module.yml`` so upstream checks compare against the same subset.
"""


class VendorError(ValueError):
    """Something about the fetch or the comparison, phrased for whoever ran the command."""


def digest_of_module(path: Path) -> str:
    """Return the content digest of every regular, non-symlinked file under a module.

    Unlike a layer digest, a module digest has no allowlist: dotfiles and other upstream content
    are part of the copy being verified.
    """
    return digest_of_contents(
        {
            entry.relative_to(path).as_posix(): entry.read_bytes()
            for entry in path.rglob("*")
            if entry.is_file() and not entry.is_symlink()
        }
    )


def digest_of_contents(files: Mapping[str, bytes]) -> str:
    """Return a module-compatible digest for an in-memory path-to-content mapping.

    Relative POSIX paths, sorted, each with its content hash. The `\\0` separates a path from
    its digest so that two files whose names concatenate to a third's cannot collide.
    """
    parts = [
        f"{name}\0{hashlib.sha256(body).hexdigest()}" for name, body in sorted(files.items())
    ]
    return "sha256:" + hashlib.sha256("\n".join(parts).encode()).hexdigest()


def _fetch(repo: str, sha: str, path: str, into: Path) -> Path:
    """Clone ``repo`` at commit ``sha`` and return ``path`` inside the checkout.

    A blobless sparse checkout avoids downloading unrelated module trees. The requested revision
    is a commit rather than a moving branch so later checks reproduce the reviewed source.
    """
    run = ["git", "clone", "--filter=blob:none", "--no-checkout", "--quiet", repo, str(into)]
    _git(run, where=None)
    _git(["git", "sparse-checkout", "set", "--no-cone", path], where=into)
    _git(["git", "checkout", "--quiet", sha], where=into)
    found = into / path
    if not found.is_dir():
        raise VendorError(
            coded(
                "MV0001",
                f"{repo} at {sha} has no directory {path}.\n"
                f"  The pin is a commit, so this is a question about that commit and not "
                f"about the branch it is on.",
            )
        )
    return found


def _git(command: list[str], where: Path | None) -> None:
    done = subprocess.run(command, cwd=where, capture_output=True, text=True)
    if done.returncode != 0:
        raise VendorError(
            coded("MV0001", f"{' '.join(command)} failed:\n  {done.stderr.strip()}")
        )


def _copy(source: Path, into: Path, excluded: list[str]) -> None:
    """Replace ``into`` with ``source``, omitting the named relative paths.

    Replacement is wholesale so files removed upstream cannot survive in the vendored copy.
    """
    if into.exists():
        shutil.rmtree(into)
    skip = {Path(one) for one in excluded}
    into.mkdir(parents=True)
    for entry in sorted(source.rglob("*")):
        where = entry.relative_to(source)
        if any(where == one or one in where.parents for one in skip):
            continue
        if entry.is_dir():
            (into / where).mkdir(parents=True, exist_ok=True)
        elif entry.is_file() and not entry.is_symlink():
            (into / where).parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(entry, into / where)


def where_of(registry: Path, module_id: str) -> Path:
    """`nf-core/star/align` -> `<registry>/tools/nf-core/star/align`.

    Each subtool has its own directory because it carries an independent module copy and
    declaration.
    """
    return registry / TOOLS / Path(module_id)


def add(
    ref: str,
    *,
    sha: str,
    registry: Path,
    licence: str,
    repo: str | None = None,
    path: str | None = None,
    excluded: list[str] | None = None,
) -> Path:
    """Fetch one module into a layer and write the declaration beside it.

    ``ref`` uses ``<source>:<ident>``, for example ``nf-core:star/align``.
    """
    source, _, ident = ref.partition(":")
    if not ident:
        raise VendorError(
            f"{ref!r} is not a module reference. Expected `<source>:<ident>`, "
            f"for example `nf-core:star/align`."
        )
    repo = repo or REPOS.get(source)
    if repo is None:
        raise VendorError(
            f"no clone URL is known for source {source!r}. Pass --repo and --path.\n"
            f"  Known: {', '.join(sorted(REPOS))}"
        )
    under = path or f"{PREFIX.get(source, source)}/{ident}"
    skipped = EXCLUDED if excluded is None else excluded

    module_id = f"{source}/{ident}"
    # Refuse before fetching so a missing licence text cannot leave a partial module on disk.
    text = registry / LICENCES / f"{licence}.txt"
    if not text.exists():
        raise VendorError(
            f"{registry} has no {LICENCES}/{licence}.txt, so it cannot carry code under "
            f"{licence}.\n"
            f"  Add the licence text there first — one file per licence, which is the REUSE "
            f"convention, and never one NOTICE per module."
        )
    into = where_of(registry, module_id) / MODULE_DIR
    with tempfile.TemporaryDirectory() as scratch:
        found = _fetch(repo, sha, under, Path(scratch) / "upstream")
        _copy(found, into, skipped)

    declared = Module(
        id=module_id,
        licence=licence,
        upstream=Upstream(repo=repo, sha=sha, path=under),
        excluded=skipped,
        digest=digest_of_module(into),
    )
    _write(into.parent / MANIFEST, declared)
    return into


def _write(path: Path, module: Module) -> None:
    """The declaration, with `declares:` first because that is the line a loader reads."""
    body = module.model_dump(mode="json", exclude_none=True)
    body.pop("id")
    path.write_text(
        f"declares: module\nid: {module.id}\n"
        + yaml.safe_dump(body, sort_keys=False, default_flow_style=False)
    )


class CheckResult:
    """What `check` found, per module, so the CLI can print it and a test can assert on it."""

    def __init__(self, module_id: str, verdict: str, detail: str = "") -> None:
        self.module_id = module_id
        self.verdict = verdict
        """`ok`, `edited`, `moved`, or `unpinned`."""
        self.detail = detail

    def __repr__(self) -> str:
        return f"CheckResult({self.module_id!r}, {self.verdict!r})"


def check(registry: Path, *, upstream: bool = False) -> list[CheckResult]:
    """Check each declared module against its stored digest or pinned upstream.

    The default check is offline and detects changes to the local copy. ``upstream=True``
    re-fetches the pinned commit and compares the selected upstream content.

    A module without an upstream declaration is reported as ``unpinned`` rather than ``ok``
    because no comparison was possible.
    """
    found: list[CheckResult] = []
    for manifest in sorted(registry.rglob(MANIFEST)):
        declared = Module(**{k: v for k, v in (yaml_strict.load(manifest) or {}).items()
                             if k != "declares"})
        here = manifest.parent / MODULE_DIR
        if not here.is_dir():
            found.append(CheckResult(declared.id, "moved", f"{here} does not exist"))
            continue
        if declared.upstream is None:
            found.append(CheckResult(declared.id, "unpinned", "declares no upstream"))
            continue
        if upstream:
            found.append(_against_upstream(declared, here))
            continue
        if declared.digest is None:
            found.append(CheckResult(declared.id, "unpinned", "records no digest"))
        elif digest_of_module(here) == declared.digest:
            found.append(CheckResult(declared.id, "ok"))
        else:
            found.append(
                CheckResult(declared.id, "edited", "the directory no longer matches its digest")
            )
    return found


def _against_upstream(declared: Module, here: Path) -> CheckResult:
    assert declared.upstream is not None
    with tempfile.TemporaryDirectory() as scratch:
        found = _fetch(
            declared.upstream.repo,
            declared.upstream.sha,
            declared.upstream.path,
            Path(scratch) / "upstream",
        )
        mirror = Path(scratch) / "mirror"
        _copy(found, mirror, list(declared.excluded))
        if digest_of_module(mirror) == digest_of_module(here):
            return CheckResult(declared.id, "ok")
        return CheckResult(
            declared.id, "moved", f"differs from {declared.upstream.repo} at "
            f"{declared.upstream.sha[:12]}"
        )

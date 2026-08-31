"""The two verbs, as functions. `cli.py` is transport over this and holds no logic.

Same split the forge uses (`mendel_forge.ops`), for the same reason: a verb that can only be
reached through `argv` can only be tested through `argv`.
"""

import hashlib
import shutil
import subprocess
import tempfile
from pathlib import Path

import yaml
from comeni_core import yaml_strict
from comeni_core.declared.layered import MODULE_DIR
from comeni_core.declared.module import Module, Upstream
from comeni_core.diagnostics import coded

MANIFEST = "module.yml"
"""The declaration, which sits **beside** `module/` and never inside it.

`add` writes the directory by deleting and replacing it wholesale, so anything inside it would
be destroyed on the next re-vendor. `layered._in_module` is the other half of this: everything
under `module/` is upstream's and is not read as declared data.
"""

TOOLS = "tools"
"""Where a layer keeps its tools. A convention of the curated registry, which `mendel registry
lint` enforces there — the loader itself stays free, because invariant 11 says the layout is
the author's business and an overlay keeps that freedom."""

REPOS = {"nf-core": "https://github.com/nf-core/modules.git"}
"""The clone URL for each source this tool knows by name. A source it does not know is not an
error — pass `--repo` and `--path` — because a laboratory vendoring from its own GitLab is an
ordinary case and hard-coding the two we happen to use would make it a special one."""

PREFIX = {"nf-core": "modules/nf-core"}
"""Where under each known repository the modules sit."""

LICENCES = "LICENSES"
"""Where a layer keeps the licence texts its modules point at — the **REUSE** convention, which
tooling already understands.

**One file per licence, never one per module.** A `NOTICE` per tool was the first proposal and
at 1,600 tools it is that many near-identical copies of the MIT text, in every diff, that nobody
reads. `module.yml` carries `licence: MIT` and this directory carries `MIT.txt`.
"""

EXCLUDED = ["tests"]
"""What `add` skips by default.

nf-core ships a `tests/` directory beside every module and we do not take it. Recording that in
`module.yml` is what stops `check` reporting every module as differing from upstream forever —
the honest comparison is *upstream minus what we said we would skip*.
"""


class VendorError(ValueError):
    """Something about the fetch or the comparison, phrased for whoever ran the command."""


def digest_of_module(path: Path) -> str:
    """The content digest of a vendored directory — **everything in it, no allowlist.**

    Deliberately not `digest_of_directory`. That one digests a *layer*, and a layer has an
    allowlist because a layer repository carries `.git`, a `LICENSE` and a README that are not
    layer data. A module directory is upstream's tree and nothing else, so every byte in it
    counts — including the dotfiles, which is where a `.gitignore` or a `.nf-core.yml` would
    live.
    """
    parts: list[str] = []
    for entry in sorted(p for p in path.rglob("*") if p.is_file() and not p.is_symlink()):
        body = hashlib.sha256(entry.read_bytes()).hexdigest()
        parts.append(f"{entry.relative_to(path).as_posix()}\0{body}")
    return "sha256:" + hashlib.sha256("\n".join(parts).encode()).hexdigest()


def _fetch(repo: str, sha: str, path: str, into: Path) -> Path:
    """Clone `repo` at `sha` and hand back `path` inside it.

    A blobless partial clone with no checkout, then a sparse checkout of the one directory —
    nf-core/modules is ~1,600 tools and cloning all of it to take one is the difference between
    a few seconds and a few minutes.

    **A `sha`, never a branch.** `vendor/modules.json` recorded both and nf-core's own tooling
    reads the branch; a branch moves, so a check against it answers *does this match whatever
    upstream looks like today*, which is a different question from *is this still the code we
    reviewed*.
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
    """Replace `into` with `source`, minus what `excluded` names.

    **Wholesale, by deleting first.** A merge would leave a file upstream removed sitting in
    the layer forever, still hashed into the layer digest and still shipped to whoever installs
    it — which is the same class of defect as a stale contract nobody re-read.
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

    The tool/subtool layout of spec §8.1: nf-core ships `star/align` and `star/genomegenerate`
    as separate modules, each needing its own `module/`, so a subtool is a directory rather
    than a suffix on a filename.
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

    `ref` is `<source>:<ident>` — `nf-core:star/align` — which is `ToolRef`'s spelling in the
    forge, so a person who has run `forge draft nf-core:fastqc` types the same thing here.
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
    # **Before the fetch, not after it.** You cannot vendor code under a licence the layer does
    # not carry the text of — that is what REUSE means — and refusing now leaves nothing
    # half-written on disk for somebody to commit.
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
    """Does every `module/` still hold what it is supposed to hold?

    **Two different questions, and the default is the offline one.**

    - Without `--upstream`: recompute each module's digest and compare it to the one
      `module.yml` records. This catches a **hand-edit**, which is what A4.3 asks CI to
      enforce, and it needs no network — so it runs in the same lane as everything else.
    - With `--upstream`: re-fetch at the pin and compare. This catches a bad `add`, and it is
      the more expensive question.

    A module with `upstream: null` is a laboratory's own process. It is reported `unpinned`
    rather than `ok`: there is nothing to compare it against, and reporting a pass would be
    claiming a check that never ran — the same reason `MD0100` marks a contract `unverified`
    rather than trusting it.
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

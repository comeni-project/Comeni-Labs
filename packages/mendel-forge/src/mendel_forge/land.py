"""The invariant-2 boundary: a branch in a registry checkout, and nothing wider.

**This is the only thing in the package that writes under a registry root**, and Task 22's
guard is what holds that. Everything else produces drafts in a workspace that lives
outside every layer.

**It does not open a pull request.** Invariant 13 says self-hosted is not a degraded
tier, so a laboratory landing into a private local overlay must get the identical path to
the one the public registry gets. Making GitHub the approval mechanism would break that
for every lab that never pushes anywhere — and the branch *is* the approval queue.

**`registry` is required and never defaults.** `registry/` in Comeni-Labs is a submodule
at a detached HEAD on a pinned commit; a defaulted target means somebody eventually
commits into it by accident, and unpicking that means pushing to `comeni-registry` and
bumping the pointer — steps this verb does not do and would not announce it was skipping.
"""

import contextlib
import fcntl
import os
import subprocess
import tempfile
from collections.abc import Iterator
from pathlib import Path

from comeni_core.artifact.digest import digest_of_directory
from comeni_core.declared.contract import ModuleContract
from comeni_core.declared.layered import MODULE_DIR
from comeni_core.declared.module import key_of
from comeni_core.declared.vocabulary import Vocabulary
from comeni_core.diagnostics import coded
from pydantic import BaseModel, ConfigDict

from mendel_forge import assemble
from mendel_forge.workspace import Draft


class LandResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    branch: str
    files: list[str]
    commit: str


def _git(registry: Path, *args: str) -> str:
    done = subprocess.run(
        ["git", *args], cwd=registry, capture_output=True, text=True, check=True
    )
    return done.stdout.strip()


def _default_branch(registry: Path) -> str | None:
    """The branch a reviewer would call *the* branch, if the checkout knows one.

    `origin/HEAD` is the honest answer when a remote exists. A fresh local repository has
    no remote and no way to say, so the caller falls back to refusing the two names that
    mean this everywhere — which is a heuristic, and is why it is not the only check.
    """
    try:
        return _git(registry, "symbolic-ref", "--short", "refs/remotes/origin/HEAD").partition(
            "/"
        )[2]
    except subprocess.CalledProcessError:
        return None


class Staged(BaseModel):
    """Every file the publication would write, composed and validated, before git is touched.

    **The whole bundle or none of it** — §4.2's *one review, not two*. A contract, its module,
    the module's declaration and every vocabulary type it needs are one act: a type published
    without the contract that wanted it is a type nobody can judge, and a contract published
    without its type does not load.

    **Composed here and written by `land`, deliberately split.** Composing touches no
    filesystem, so everything that can refuse — a hole still open, a contract that will not
    load, a type the vocabulary cannot take — refuses while the checkout is untouched. That is
    the same argument `accept_drift` makes about a failed accept costing nothing, applied to
    the verb that writes four files instead of one.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    files: tuple[tuple[str, str], ...]
    """`(registry-relative path, text)`, in the order they are written and committed."""
    contract_id: str
    new_types: tuple[str, ...] = ()

    def paths(self) -> list[str]:
        return [path for path, _ in self.files]


def stage(
    draft: Draft, *, approved_by: str, approved_at: str, vocabulary: Vocabulary | None = None
) -> Staged:
    """Compose the approved bundle and prove it loads. **Writes nothing.**

    `vocabulary` is the layer's, so the contract is validated against the types that will exist
    *after* this publication — its own new ones included. Validating against the vocabulary as
    it stands now would refuse every contract that introduces a type, which is most of them;
    validating against nothing would accept a contract the registry then refuses to load, which
    is the outcome `_must_load` exists to prevent one verb over.
    """
    # First, because a draft with holes must be refused before anything else happens. `MF0004`
    # comes from `contract_from`, which is the one place that refusal is decided.
    contract_yaml = assemble.to_yaml(
        draft.scaffold, approved_by=approved_by, approved_at=approved_at
    )

    target = Path(draft.scaffold.target)
    files: list[tuple[str, str]] = [(str(target), contract_yaml)]

    if draft.module is not None:
        # In `module/` beside the contract, following the convention the public registry uses
        # for a tool's files. It is deliberately *not* `nf_include`, which says where a module
        # lands in a generated pipeline rather than where its source lives — the same
        # distinction `conformance.module_path` is built on.
        files.append((str(target.parent / MODULE_DIR / "main.nf"), draft.module))

        # FORGE-REWORK — Plan 5A added this write. A hand-drafted module has no `upstream:`
        # and names no `licence:`, and whether the forge should be authoring registry *modules*
        # at all — as opposed to contracts over modules `comeni-vendor` fetched — is a question
        # the rework has to answer rather than inherit.
        #
        # **The declaration, or the code is invisible.** A `module/` with no `module.yml`
        # beside it is not in the stack's modules, so `MD0100` would report the contract
        # unverified while the source sat right there. `upstream: null` and no `licence:` are
        # both honest: this module was written here rather than copied, so there is nothing to
        # check it against and nobody else's terms to name.
        files.append(
            (
                str(target.parent / "module.yml"),
                f"declares: module\nid: {key_of(str(draft.scaffold.filled['nf_include'].value))}\n",
            )
        )

    new_types = tuple(sorted(set(draft.scaffold.approved().values())))
    for type_id in new_types:
        # Three lines, matching what the registry already holds — see
        # `registry/types/alignment.bai.yml`. States are empty on purpose: a new type's
        # states are a separate judgement, and `add_states:` is how a layer extends them.
        #
        # In the SAME commit as the contract, which is the whole of §4.2's "one review, not
        # two": a type proposed with no consumer is a type nobody can judge.
        files.append(
            (
                str(Path("types") / f"{type_id}.yml"),
                f"declares: vocabulary\nid: {type_id}\nstates: []\n",
            )
        )

    contract_id = str(draft.scaffold.filled["id"].value)
    if vocabulary is not None:
        _must_load(
            contract_yaml,
            _with(vocabulary, new_types),
            contract_id=contract_id,
            said=f"{contract_id} would not load into this registry",
        )
    return Staged(files=tuple(files), contract_id=contract_id, new_types=new_types)


def _with(vocabulary: Vocabulary, new_types: tuple[str, ...]) -> Vocabulary:
    """The layer's vocabulary plus the types this publication introduces.

    **A copy, never the shared one mutated.** `services/registry.py` caches a `Layers` and its
    docstring says every reader takes `.vocabulary` and reads; a validation that added a type to
    it would leak a not-yet-published type into every other request in the process.
    """
    if not new_types:
        return vocabulary
    from comeni_core.declared.vocabulary import TypeDeclaration

    return vocabulary.model_copy(
        update={
            "types": {
                **vocabulary.types,
                **{
                    type_id: TypeDeclaration(id=type_id, states=[])
                    for type_id in new_types
                    if type_id not in vocabulary.types
                },
            }
        }
    )


@contextlib.contextmanager
def _only_one_publication(registry: Path) -> Iterator[None]:
    """Serialise publication into one checkout, across processes.

    **A file lock rather than a database row or an in-process mutex.** What is being protected
    is a *git checkout* — a shared working tree with one HEAD — and the things that would race
    on it are separate processes: two AI workers, a worker and somebody's terminal, a worker and
    a `forge land` in a container. An `asyncio.Lock` protects one event loop and a Postgres
    advisory lock protects callers who happen to share a database, and neither is what a working
    tree needs.

    **It lives in `.git/`, which is exactly where it must be.** A lock file in the tree would
    be an uncommitted change, and `MF0101` refuses a dirty tree — the lock would fail the check
    it exists to make safe.

    Blocking, not `LOCK_NB`. A second publication should wait for the first rather than refuse:
    the work is already approved, and a refusal here would send a curator back to press a button
    that will work in ten seconds.
    """
    git_dir = Path(_git(registry, "rev-parse", "--absolute-git-dir"))
    git_dir.mkdir(parents=True, exist_ok=True)
    handle = os.open(str(git_dir / "forge-land.lock"), os.O_CREAT | os.O_RDWR, 0o644)
    try:
        fcntl.flock(handle, fcntl.LOCK_EX)
        yield
    finally:
        with contextlib.suppress(OSError):
            fcntl.flock(handle, fcntl.LOCK_UN)
        os.close(handle)


def base_digest(registry: Path) -> str:
    """What the registry is right now, by the same definition every other reader uses.

    `digest_of_directory` over the declared entries — the function `services/registry.py`
    caches on and `pipeline.yml` pins layers by. A second definition of *the registry changed*
    is the drift `MD0104` was built to catch, one layer down.
    """
    return str(digest_of_directory(registry))


def land(
    draft: Draft,
    *,
    registry: Path,
    branch: str,
    approved_by: str,
    approved_at: str,
    vocabulary: Vocabulary | None = None,
    expect_base: str | None = None,
) -> LandResult:
    """Publish one approved bundle onto a branch in a registry checkout.

    **Staged, locked, checked, then written** — and in that order, because each step is what
    makes the next one safe:

    - `stage` composes every file and proves the contract loads, touching nothing;
    - the lock makes two publications into one working tree take turns rather than race on
      HEAD;
    - `expect_base` refuses a registry that moved since the candidate was validated, because a
      green verdict describes the layer that was read at the time;
    - and only then is a branch created and four files written.

    **A failure after the branch exists rolls the checkout back.** The plan asks for *the
    registry recoverable*, and a half-written branch is not that — the next publication would
    meet `MF0101`'s dirty tree and refuse for a reason that has nothing to do with it.
    """
    staged = stage(
        draft, approved_by=approved_by, approved_at=approved_at, vocabulary=vocabulary
    )

    default = _default_branch(registry)
    protected = {default} if default else {"main", "master"}
    if branch in protected:
        raise ValueError(
            coded("MF0100", f"{branch!r} is this registry's default branch")
            + "\n  land on a new branch — `forge/<tool>` is the convention — and merge after"
            " review"
        )

    with _only_one_publication(registry):
        # **Inside the lock, all of it.** A dirty-tree check outside it reads a tree another
        # publication is mid-way through writing, and answers about a moment that has passed.
        dirty = _git(registry, "status", "--porcelain")
        if dirty:
            raise ValueError(
                coded("MF0101", f"{registry} has uncommitted changes")
                + f"\n{dirty}\n  commit or stash them, then land again"
            )

        if expect_base is not None:
            now = base_digest(registry)
            if now != expect_base:
                raise ValueError(
                    coded("MF0108", "the registry moved since this candidate was validated")
                    + f"\n  validated against {expect_base[:12]}…"
                    + f"\n  the registry is now {now[:12]}…"
                    + "\n  re-validate before publishing — a green verdict describes the layer"
                    " that was read at the time"
                )

        was = _git(registry, "branch", "--show-current")
        _git(registry, "checkout", "-b", branch)
        try:
            for relative, text in staged.files:
                _write(registry / relative, text)
            _git(registry, "add", *staged.paths())
            _git(
                registry,
                "-c",
                f"user.email={approved_by}@forge.local",
                "-c",
                f"user.name={approved_by}",
                "commit",
                "-m",
                f"forge: {staged.contract_id}\n\nApproved by {approved_by} on {approved_at}.",
            )
        except Exception:
            _rewind(registry, to=was, branch=branch)
            raise
        return LandResult(
            branch=branch, files=staged.paths(), commit=_git(registry, "rev-parse", "HEAD")
        )


def _rewind(registry: Path, *, to: str, branch: str) -> None:
    """Put the checkout back where it was, so a failed publication costs nothing.

    **Every step suppresses its own error.** This runs while an exception is in flight and the
    caller re-raises it; a failure to clean up must not replace the reason the publication
    failed with a reason the cleanup failed, which is how a `MF0103` becomes a git error nobody
    can act on.

    `to` may be empty when the checkout was at a detached HEAD, in which case there is no branch
    to return to and the reset is the whole of what can be done.
    """
    with contextlib.suppress(Exception):
        _git(registry, "reset", "--hard")
    with contextlib.suppress(Exception):
        _git(registry, "clean", "-fd")
    if to:
        with contextlib.suppress(Exception):
            _git(registry, "checkout", to)
        with contextlib.suppress(Exception):
            _git(registry, "branch", "-D", branch)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def _patch_line(text: str, field: str, value: str) -> str:
    """Replace the one top-level line declaring `field`, and nothing else.

    Refuses anything it cannot see whole — MF0102. A registry contract's comments ARE its
    reasoning, so re-serialising through a YAML dumper is not an option; see the diagnostic's
    explanation.
    """
    unpatchable = (
        "\n  a block scalar, a repeated key or a field inside a flow mapping is not"
        " patchable — edit the file by hand"
    )
    lines = text.splitlines(keepends=True)
    at = [i for i, line in enumerate(lines) if line.startswith(f"{field}: ")]
    if len(at) != 1:
        raise ValueError(
            coded("MF0102", f"{field!r} appears on {len(at)} top-level lines, expected one")
            + unpatchable
        )
    # **Starting the line is not enough.** `container: >-` starts with `container: ` and is a
    # block scalar whose value lives on the lines below; patching it would replace the header
    # and orphan the body. Found by the test written to make the refusal non-vacuous.
    here = at[0]
    inline = lines[here][len(field) + 2 :].strip()
    spills = here + 1 < len(lines) and lines[here + 1][:1].isspace()
    if not inline or inline[0] in "|>" or spills:
        raise ValueError(
            coded("MF0102", f"{field!r} is not a single-line scalar in this contract")
            + unpatchable
        )
    keep = "\n" if lines[here].endswith("\n") else ""
    lines[here] = f"{field}: {value}{keep}"
    return "".join(lines)


def _must_load(patched: str, vocabulary: Vocabulary, *, contract_id: str, said: str) -> None:
    """The patched text must load **through the real loader** before anything is written.

    `ModuleContract.load(path, vocab)` rather than `model_validate(dict)`: it pops `declares:`,
    it reads through `yaml_strict` so a duplicate key refuses rather than silently keeping the
    last (A31), and it validates every state against the layer's vocabulary — invariant 7. A
    validator that skipped the vocabulary would accept a patch the registry then refuses to
    load, which is the one outcome this check exists to prevent.

    It takes a `Path`, so the candidate goes to a temporary file. Writing the real file and
    rolling back on failure was the alternative and is worse: a failed accept would leave a
    dirty tree, which is the state `MF0101` refuses.
    """
    with tempfile.TemporaryDirectory() as tmp:
        candidate = Path(tmp) / "candidate.contract.yml"
        candidate.write_text(patched)
        try:
            ModuleContract.load(candidate, vocabulary)
        except Exception as error:
            raise ValueError(coded("MF0103", said) + f"\n{error}") from None


def _refuse_an_unwritable_checkout(registry: Path, branch: str) -> None:
    """The three ways a checkout is not somewhere to commit. `land()` holds two of them.

    **The default-branch check reads the branch this would commit TO**, which is the branch
    being created rather than the one HEAD is on — `land()` asks the same question about the
    branch it was handed. Accepting onto a checkout sitting on `main` is fine; accepting
    *into* `main` is not.
    """
    # **First, because the three below all shell out to git and a non-repository makes every
    # one of them exit 128.** `git rev-parse`, not `(registry / ".git").exists()`: a submodule's
    # `.git` is a FILE holding `gitdir: ../../../.git/worktrees/…`, so it is present inside a
    # bind-mounted container while git resolves it to nothing. Measured, phase 8.
    try:
        _git(registry, "rev-parse", "--git-dir")
    except subprocess.CalledProcessError:
        raise ValueError(
            coded("MF0107", f"{registry} is not a git checkout")
            + "\n  accepting a drift is a commit, and a directory of files cannot carry one"
            + "\n  point MENDEL_REGISTRY_ROOT at a checkout you can write to — in a container,"
            " mount a CLONE: a submodule's `.git` is a pointer at a path on the host and it"
            " resolves to nothing inside the container"
        ) from None

    on = _git(registry, "branch", "--show-current")
    if not on:
        raise ValueError(
            coded("MF0105", f"{registry} is at a detached HEAD")
            + "\n  check out a branch, or point MENDEL_REGISTRY_ROOT at a checkout you can"
            " write to"
        )
    default = _default_branch(registry) or "main"
    if branch == default:
        raise ValueError(
            coded("MF0100", f"{branch!r} is this registry's default branch")
            + "\n  accepting commits on a branch — `forge/drift` is the convention"
        )
    dirty = _git(registry, "status", "--porcelain")
    if dirty:
        raise ValueError(coded("MF0101", f"{registry} has uncommitted changes") + f"\n{dirty}")


def accept_drift(
    *,
    registry: Path,
    path: Path,
    contract_id: str,
    field: str,
    value: str,
    vocabulary: Vocabulary,
    by: str,
    why: str,
    branch: str,
) -> tuple[str, str]:
    """Patch one line, validate it, commit it. Returns `(branch, commit)`.

    **Here rather than in `ops.py` because this writes under a registry root**, and this
    module is the one place that may — `test_only_land_and_the_workspace_write_to_disk` is
    what holds that, and it caught this code in the wrong file rather than being widened
    to accommodate it.

    **Everything that can refuse, refuses before anything is written.** A failed accept must
    cost nothing; the alternative is a checkout somebody has to reset, which is the state
    `land()` refuses a dirty tree to avoid.

    **The branch is reused when HEAD is already on it.** `land()` always creates one, because
    a draft lands once; a drift is accepted repeatedly, so branching off the previous accept
    would read as two unrelated lines of history.
    """
    patched = _patch_line(path.read_text(), field, value)
    _must_load(
        patched, vocabulary, contract_id=contract_id,
        said=f"{contract_id} would not load with {field}: {value}",
    )
    _refuse_an_unwritable_checkout(registry, branch)

    if _git(registry, "branch", "--show-current") != branch:
        _git(registry, "checkout", "-b", branch)
    _write(path, patched)
    relative = str(path.relative_to(registry))
    _git(registry, "add", relative)
    _git(
        registry,
        "-c",
        f"user.email={by}@forge.local",
        "-c",
        f"user.name={by}",
        "commit",
        "-m",
        f"forge: {contract_id} {field} -> {value}\n\n{why}\n\nAccepted by {by}.",
    )
    return branch, _git(registry, "rev-parse", "HEAD")

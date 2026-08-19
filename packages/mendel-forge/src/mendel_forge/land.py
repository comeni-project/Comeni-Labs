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

import subprocess
import tempfile
from pathlib import Path

from comeni_core.declared.contract import ModuleContract
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


def land(
    draft: Draft, *, registry: Path, branch: str, approved_by: str, approved_at: str
) -> LandResult:
    # First, because a draft with holes must be refused before anything touches git. MF0004
    # comes from `contract_from`, which is the one place that refusal is decided.
    contract_yaml = assemble.to_yaml(
        draft.scaffold, approved_by=approved_by, approved_at=approved_at
    )

    default = _default_branch(registry)
    protected = {default} if default else {"main", "master"}
    if branch in protected:
        raise ValueError(
            coded("MF0100", f"{branch!r} is this registry's default branch")
            + "\n  land on a new branch — `forge/<tool>` is the convention — and merge after"
            " review"
        )

    dirty = _git(registry, "status", "--porcelain")
    if dirty:
        raise ValueError(
            coded("MF0101", f"{registry} has uncommitted changes")
            + f"\n{dirty}\n  commit or stash them, then land again"
        )

    _git(registry, "checkout", "-b", branch)

    written: list[str] = []
    target = Path(draft.scaffold.target)
    _write(registry / target, contract_yaml)
    written.append(str(target))

    if draft.module is not None:
        # Beside the contract, following the convention the public registry uses for a
        # tool's files. It is deliberately *not* `nf_include`, which says where a module
        # lands in a generated pipeline rather than where its source lives — the same
        # distinction `conformance.module_path` is built on.
        module_path = target.parent / "main.nf"
        _write(registry / module_path, draft.module)
        written.append(str(module_path))

    for type_id in sorted(set(draft.scaffold.approved().values())):
        # Three lines, matching what the registry already holds — see
        # `registry/types/alignment.bai.yml`. States are empty on purpose: a new type's
        # states are a separate judgement, and `add_states:` is how a layer extends them.
        #
        # In the SAME commit as the contract, which is the whole of §4.2's "one review, not
        # two": a type proposed with no consumer is a type nobody can judge.
        vocabulary_path = Path("types") / f"{type_id}.yml"
        _write(
            registry / vocabulary_path,
            f"declares: vocabulary\nid: {type_id}\nstates: []\n",
        )
        written.append(str(vocabulary_path))

    _git(registry, "add", *written)
    _git(
        registry,
        "-c",
        f"user.email={approved_by}@forge.local",
        "-c",
        f"user.name={approved_by}",
        "commit",
        "-m",
        f"forge: {draft.scaffold.filled['id'].value}\n\nApproved by {approved_by}"
        f" on {approved_at}.",
    )
    return LandResult(branch=branch, files=written, commit=_git(registry, "rev-parse", "HEAD"))


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

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
from pathlib import Path

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

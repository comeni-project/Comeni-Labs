"""The publication boundary: staged, locked, checked, and recoverable.

**Publication is the door with no undo**, which is why every one of these is about what happens
*before* anything is written or what the checkout looks like when something goes wrong. A
contract in a registry it was never validated against cannot be taken back by a button.
"""

import multiprocessing
import subprocess
import time
from pathlib import Path

import pytest
from mendel_forge.land import base_digest, land, stage
from mendel_forge.workspace import Draft


def _repo(tmp_path: Path) -> Path:
    root = tmp_path / "registry"
    root.mkdir()
    subprocess.run(["git", "init", "-b", "main"], cwd=root, check=True, capture_output=True)
    (root / "registry.yml").write_text("name: test\n")
    subprocess.run(["git", "add", "-A"], cwd=root, check=True)
    subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-m", "init"],
        cwd=root,
        check=True,
        capture_output=True,
    )
    return root


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=repo, capture_output=True, text=True, check=True
    ).stdout.strip()


# ── staging ───────────────────────────────────────────────────────────────────────────


def test_the_whole_bundle_is_composed_before_git_is_touched(complete_scaffold):
    """**§4.2's *one review, not two*.** A contract, its module, the module's declaration and
    every type it needs are one act — and composing them all first is what makes the write
    either happen completely or not at all."""
    staged = stage(
        Draft(name="f", scaffold=complete_scaffold, module="process X {}\n"),
        approved_by="rafael",
        approved_at="2026-09-05",
    )
    paths = staged.paths()
    assert complete_scaffold.target in paths
    assert any(path.endswith("module/main.nf") for path in paths)
    assert any(path.endswith("module.yml") for path in paths)
    assert len(set(paths)) == len(paths), "a path composed twice would be written twice"


def test_staging_cannot_write_into_a_registry(tmp_path, complete_scaffold):
    """The claim the ordering rests on, asserted **structurally**.

    **A directory scan is the weak form and it was inert.** Reverting `stage` to write a file
    left this test green, because the scan only looked in the registry and the injected write
    went to the working directory — a guard that passes on the code it was written to reject.

    The strong form is that `stage` is *not given* a registry at all: it has no path parameter,
    so there is no root for it to write under, and a future author who needs one has to add a
    parameter — which is a diff somebody looks at. The scan stays beside it as the behavioural
    half, on a checkout that `land` would otherwise have written into.
    """
    import inspect

    taken = set(inspect.signature(stage).parameters)
    assert not (taken & {"registry", "root", "path", "out"}), (
        f"`stage` was given somewhere to write: {sorted(taken)}. Composing is what makes every "
        "refusal cost nothing, and it only holds while there is no root to write under."
    )

    repo = _repo(tmp_path)
    before = sorted(p.relative_to(repo) for p in repo.rglob("*") if ".git" not in p.parts)
    stage(
        Draft(name="f", scaffold=complete_scaffold, module="process X {}\n"),
        approved_by="rafael",
        approved_at="2026-09-05",
    )
    after = sorted(p.relative_to(repo) for p in repo.rglob("*") if ".git" not in p.parts)
    assert before == after


def test_an_incomplete_draft_is_refused_by_staging(incomplete_scaffold):
    """**Before anything else happens.** `MF0004` comes from `contract_from`, which is the one
    place that refusal is decided — and it has to fire while the checkout is untouched."""
    with pytest.raises(ValueError, match="MF0004"):
        stage(
            Draft(name="f", scaffold=incomplete_scaffold, module=None),
            approved_by="r",
            approved_at="2026-09-05",
        )


# ── the base digest ───────────────────────────────────────────────────────────────────


def test_a_registry_that_moved_since_validation_is_refused(tmp_path, complete_scaffold):
    """**`MF0108`, and it is the second time this question is asked.** `MF0301` asks it when
    somebody presses approve; publication happens in a worker, and the gap between the two is
    exactly where a colleague merges a contract or a type's states change.

    A green verdict is a statement about the layer that was read at the time.
    """
    repo = _repo(tmp_path)
    stale = base_digest(repo)

    (repo / "types").mkdir()
    (repo / "types" / "later.yml").write_text("declares: vocabulary\nid: later\nstates: []\n")
    _git(repo, "add", "-A")
    _git(repo, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-m", "somebody else")

    with pytest.raises(ValueError, match="MF0108"):
        land(
            Draft(name="f", scaffold=complete_scaffold, module=None),
            registry=repo,
            branch="forge/f",
            approved_by="r",
            approved_at="2026-09-05",
            expect_base=stale,
        )


def test_a_registry_that_has_not_moved_is_published(tmp_path, complete_scaffold):
    """The other half — the check must not refuse everything, which is how a guard gets
    disabled by whoever is trying to ship."""
    repo = _repo(tmp_path)
    result = land(
        Draft(name="f", scaffold=complete_scaffold, module=None),
        registry=repo,
        branch="forge/f",
        approved_by="r",
        approved_at="2026-09-05",
        expect_base=base_digest(repo),
    )
    assert result.commit


def test_the_refusal_leaves_the_checkout_where_it_was(tmp_path, complete_scaffold):
    """**Recoverable is the word the plan uses.** A refusal that left a branch behind would make
    the *next* publication meet `MF0101`'s dirty tree and refuse for a reason that has nothing
    to do with it."""
    repo = _repo(tmp_path)
    stale = base_digest(repo)
    (repo / "registry.yml").write_text("name: moved\n")
    _git(repo, "add", "-A")
    _git(repo, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-m", "moved")

    with pytest.raises(ValueError, match="MF0108"):
        land(
            Draft(name="f", scaffold=complete_scaffold, module=None),
            registry=repo,
            branch="forge/f",
            approved_by="r",
            approved_at="2026-09-05",
            expect_base=stale,
        )

    assert _git(repo, "branch", "--show-current") == "main"
    assert _git(repo, "status", "--porcelain") == ""
    assert "forge/f" not in _git(repo, "branch", "--list")


# ── atomicity ─────────────────────────────────────────────────────────────────────────


def test_a_failure_mid_write_leaves_no_branch_and_no_files(
    tmp_path, complete_scaffold, monkeypatch
):
    """**Atomic from the user's perspective**, which is the plan's phrasing and the honest one:
    git is not transactional, so what is guaranteed is that a failed publication is rewound
    rather than that it never began.

    The failure is injected at the commit, which is the last step and therefore the one with
    the most already written — a rollback that only worked before the first write would pass a
    test that injected earlier.
    """
    repo = _repo(tmp_path)
    from mendel_forge import land as land_module

    real = land_module._git

    def fail_on_commit(registry, *args):
        if args and args[-1].startswith("forge: "):
            raise RuntimeError("the commit hook said no")
        return real(registry, *args)

    monkeypatch.setattr(land_module, "_git", fail_on_commit)

    with pytest.raises(RuntimeError, match="commit hook"):
        land(
            Draft(name="f", scaffold=complete_scaffold, module="process X {}\n"),
            registry=repo,
            branch="forge/f",
            approved_by="r",
            approved_at="2026-09-05",
        )

    monkeypatch.undo()
    assert _git(repo, "branch", "--show-current") == "main"
    assert _git(repo, "status", "--porcelain") == "", "a half-written tree the next land refuses"
    assert not (repo / complete_scaffold.target).exists()


def test_the_original_failure_survives_the_rollback(tmp_path, complete_scaffold, monkeypatch):
    """**The cleanup must not replace the reason.** `_rewind` runs while an exception is in
    flight; a failure inside it that propagated would turn a refusal a person can act on into a
    git error nobody can."""
    repo = _repo(tmp_path)
    from mendel_forge import land as land_module

    real = land_module._git

    def fail_on_commit_and_on_cleanup(registry, *args):
        if args and args[-1].startswith("forge: "):
            raise RuntimeError("the commit hook said no")
        # **`checkout -b` is not cleanup**, and the first version of this fake broke it — so
        # the publication died before the commit and the assertion failed on the fake rather
        # than on `_rewind`. Cleanup is `reset`, `clean`, `branch -D` and a bare `checkout`.
        rewinding = args[0] in {"reset", "clean"} or args[:2] == ("branch", "-D")
        rewinding = rewinding or (args[0] == "checkout" and "-b" not in args)
        if args and rewinding:
            raise RuntimeError("cleanup broke")
        return real(registry, *args)

    monkeypatch.setattr(land_module, "_git", fail_on_commit_and_on_cleanup)

    with pytest.raises(RuntimeError, match="commit hook"):
        land(
            Draft(name="f", scaffold=complete_scaffold, module=None),
            registry=repo,
            branch="forge/f",
            approved_by="r",
            approved_at="2026-09-05",
        )


# ── the lock ──────────────────────────────────────────────────────────────────────────


def _hold(registry: str, seconds: float, started, done) -> None:
    """Take the publication lock in another process and sit on it."""
    from mendel_forge.land import _only_one_publication

    with _only_one_publication(Path(registry)):
        started.set()
        time.sleep(seconds)
    done.set()


def test_two_publications_into_one_checkout_take_turns(tmp_path):
    """**A file lock, because what is protected is a git working tree.** The things that race on
    it are separate processes — two AI workers, a worker and somebody's terminal — and an
    `asyncio.Lock` protects one event loop while a Postgres advisory lock protects callers who
    happen to share a database. Neither is what a working tree needs.

    Asserted across a real process boundary rather than with two threads, because a lock that
    only excluded threads would pass a threaded test and protect nothing.
    """
    repo = _repo(tmp_path)
    from mendel_forge.land import _only_one_publication

    context = multiprocessing.get_context("spawn")
    started, done = context.Event(), context.Event()
    holder = context.Process(target=_hold, args=(str(repo), 1.0, started, done))
    holder.start()
    try:
        assert started.wait(timeout=20), "the other process never took the lock"
        began = time.monotonic()
        with _only_one_publication(repo):
            waited = time.monotonic() - began
        assert waited > 0.4, f"the second publication did not wait; it took {waited:.2f}s"
    finally:
        holder.join(timeout=20)


def test_the_lock_lives_in_the_git_directory_and_not_in_the_tree(tmp_path):
    """**Or it would fail the check it exists to make safe.** A lock file in the working tree is
    an uncommitted change, and `MF0101` refuses a dirty tree."""
    repo = _repo(tmp_path)
    from mendel_forge.land import _only_one_publication

    with _only_one_publication(repo):
        assert _git(repo, "status", "--porcelain") == ""
    assert (repo / ".git" / "forge-land.lock").exists()


def test_a_role_no_layer_declares_is_refused_before_anything_is_written(complete_scaffold):
    """**Roles are closed (invariant 7) and staging did not check them.**

    `ModuleContract.load` validates states against the vocabulary and nothing else; roles are
    checked one level up, by `layers.load`. So a contract naming a role no layer declares passed
    every check in `stage`, landed, and then made the *whole registry* fail to load with
    `MD0302` — the exact failure staging exists to prevent, one vocabulary over.

    Found on 2026-09-05 by landing a real candidate whose model-drafted role was
    `gene_prediction`. The automated walk missed it because its fixture registry happened to
    declare the role its fixture used, which is what a fixture does.
    """
    from comeni_core.declared.roles import RoleVocabulary, UnknownRoleError

    with pytest.raises(UnknownRoleError, match="MD0302"):
        stage(
            Draft(name="f", scaffold=complete_scaffold, module=None),
            approved_by="rafael",
            approved_at="2026-09-05",
            roles=RoleVocabulary(names=frozenset({"alignment", "trimming"})),
        )


def test_a_declared_role_passes_staging(complete_scaffold):
    """The other half — a check that refuses everything is a check somebody deletes."""
    from comeni_core.declared.roles import RoleVocabulary

    staged = stage(
        Draft(name="f", scaffold=complete_scaffold, module=None),
        approved_by="rafael",
        approved_at="2026-09-05",
        roles=RoleVocabulary(names=frozenset({"qc_per_sample"})),
    )
    assert staged.contract_id


# ── the ladder ────────────────────────────────────────────────────────────────────────


def test_the_ladder_can_reach_green_against_the_real_registry(complete_scaffold):
    """**Nothing asserted that a candidate could pass.**

    `verify.verify` has had six rungs and a full test file since Phase 2, and every one of those
    tests drives a rung to a *refusal* — which is the interesting half and not the whole claim.
    The worker recorded `green = False` unconditionally, so no path in the system had ever
    produced a green verdict, and *approval through the front door was impossible* in a way no
    test would have noticed: `approval_refusals` reads `green`, and `green` was a constant.

    This runs the ladder end to end against the **shipped registry** — not a fixture layer —
    and asserts it passes. A check that can only refuse is a check that will be disabled by
    whoever is trying to ship.
    """
    from mendel_forge import verify

    # **The repository root by walking up to the marker, not by counting `parent`s.**
    # `tests/README.md` says the depth is a claim that goes false the moment a file moves, and
    # `support.paths` is not importable from this package's own test run.
    root = Path(__file__).resolve()
    while not (root / "registry" / "registry.yml").exists():
        assert root != root.parent, "no registry/ above this file"
        root = root.parent

    verdicts = verify.verify(
        complete_scaffold,
        registry_root=root / "registry",
        source_root=root / "registry",
        module=None,
    )

    assert len(verdicts) == len(verify.Rung), "a rung was skipped, so something refused early"
    assert not verify.refuses(verdicts), [
        (str(v.rung), [str(d) for d in v.diagnostics]) for v in verdicts if v.refused
    ]


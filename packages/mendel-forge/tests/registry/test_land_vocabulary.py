"""Landing a draft whose approved proposals must travel with it.

**One review, not two** — `docs/notes/specs/2026-08-17-vocabulary-proposals.md` §4.2. A reviewer
opening the branch sees the new type and its first consumer side by side, because a type
proposed with no consumer is a type nobody can judge.
"""

import subprocess

import pytest
from mendel_forge.land import land
from mendel_forge.scaffold import Decision, Proposal
from mendel_forge.workspace import Draft

FIELD = "produces[0].type_id"


def _repo(tmp_path):
    """A throwaway git repo standing in for the registry.

    **Never the real submodule**: `land` commits, and a test that commits into `registry/`
    would leave the worktree dirty. Copied from `test_land.py:8`, which is the file's idiom.
    """
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


def _carrying(scaffold, decision: Decision):
    """A complete scaffold carrying one decided proposal.

    The proposal is injected into `proposed` directly rather than through `Scaffold.propose`,
    because `complete_scaffold` has no holes left to propose against — and a draft that can
    land is by definition one with no holes. `decide` only requires the proposal to exist.
    """
    proposed = scaffold.model_copy(
        update={
            "proposed": {
                FIELD: Proposal(
                    id="qc.index_stats",
                    description="per-reference index statistics",
                    why="nothing declared covers idxstats output",
                    by="rafael",
                )
            }
        }
    )
    return proposed.decide(FIELD, decision, by="reviewer", why="judged")


@pytest.fixture
def landable_draft(complete_scaffold):
    return Draft(
        name="fastqc", scaffold=_carrying(complete_scaffold, Decision.APPROVED), module=None
    )


@pytest.fixture
def draft_with_rejection(complete_scaffold):
    return Draft(
        name="fastqc", scaffold=_carrying(complete_scaffold, Decision.REJECTED), module=None
    )


def test_an_approved_type_is_written_beside_the_contract(tmp_path, landable_draft):
    repo = _repo(tmp_path)
    result = land(
        landable_draft,
        registry=repo,
        branch="forge/test",
        approved_by="reviewer",
        approved_at="2026-08-18",
    )

    assert "types/qc.index_stats.yml" in result.files
    written = (repo / "types" / "qc.index_stats.yml").read_text()
    assert "declares: vocabulary" in written
    assert "id: qc.index_stats" in written
    assert "states: []" in written


def test_the_type_and_the_contract_are_one_commit(tmp_path, landable_draft):
    """The whole argument for writing at land time rather than approve time."""
    repo = _repo(tmp_path)
    land(
        landable_draft,
        registry=repo,
        branch="forge/test",
        approved_by="reviewer",
        approved_at="2026-08-18",
    )

    files = subprocess.run(
        ["git", "show", "--name-only", "--format=", "HEAD"],
        cwd=repo,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.split()

    assert any(f.startswith("types/") for f in files)
    assert any(f.endswith("/contract.yml") for f in files)


def test_a_rejected_proposal_is_not_written(tmp_path, draft_with_rejection):
    """`approved()` is the filter, and this is the test that it is the right one: a rejected
    type reaching the registry is an unapproved type in declared data."""
    repo = _repo(tmp_path)
    result = land(
        draft_with_rejection,
        registry=repo,
        branch="forge/test",
        approved_by="reviewer",
        approved_at="2026-08-18",
    )

    assert not any(f.startswith("types/") for f in result.files)
    assert not (repo / "types").exists()


def test_two_ports_approved_onto_one_id_write_one_file(tmp_path, complete_scaffold):
    """`approved()` is keyed by FIELD, so two ports needing the same new type produce two
    entries with one value. Writing per entry would add the same path to `written` twice and
    put a duplicate in the commit — `sorted(set(...))` is what stops it, and this is the test
    that says so. Flagged by the plan's own self-review as untested."""
    # Two ports that BOTH exist on this fixture — it has one `produces`, so
    # `produces[1].type_id` would break assembly on a missing `produces[1].name`.
    fields = ("consumes[0].type_id", "produces[0].type_id")
    both = complete_scaffold.model_copy(
        update={
            "proposed": {
                field: Proposal(id="qc.index_stats", description="d", why="w", by="rafael")
                for field in fields
            }
        }
    )
    for field in fields:
        both = both.decide(field, Decision.APPROVED, by="reviewer", why="same thing")

    result = land(
        Draft(name="fastqc", scaffold=both, module=None),
        registry=_repo(tmp_path),
        branch="forge/test",
        approved_by="reviewer",
        approved_at="2026-08-18",
    )

    assert result.files.count("types/qc.index_stats.yml") == 1

import subprocess

import pytest
from mendel_forge.land import land
from mendel_forge.workspace import Draft


def _repo(tmp_path):
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


def test_landing_writes_the_contract_on_a_new_branch(tmp_path, complete_scaffold):
    repo = _repo(tmp_path)
    result = land(
        Draft(name="fastqc", scaffold=complete_scaffold, module=None),
        registry=repo,
        branch="forge/fastqc",
        approved_by="rafael",
        approved_at="2026-08-20",
    )
    assert result.branch == "forge/fastqc"
    head = subprocess.run(
        ["git", "branch", "--show-current"], cwd=repo, capture_output=True, text=True
    ).stdout.strip()
    assert head == "forge/fastqc"
    assert (repo / complete_scaffold.target).exists()


def test_it_refuses_to_land_on_the_default_branch(tmp_path, complete_scaffold):
    repo = _repo(tmp_path)
    with pytest.raises(ValueError, match="MF0100"):
        land(
            Draft(name="f", scaffold=complete_scaffold, module=None),
            registry=repo,
            branch="main",
            approved_by="r",
            approved_at="2026-08-20",
        )


def test_it_refuses_a_dirty_tree(tmp_path, complete_scaffold):
    repo = _repo(tmp_path)
    (repo / "stray.txt").write_text("x")
    with pytest.raises(ValueError, match="MF0101"):
        land(
            Draft(name="f", scaffold=complete_scaffold, module=None),
            registry=repo,
            branch="forge/f",
            approved_by="r",
            approved_at="2026-08-20",
        )


def test_it_refuses_an_incomplete_draft(tmp_path, incomplete_scaffold):
    repo = _repo(tmp_path)
    with pytest.raises(ValueError, match="MF0004"):
        land(
            Draft(name="f", scaffold=incomplete_scaffold, module=None),
            registry=repo,
            branch="forge/f",
            approved_by="r",
            approved_at="2026-08-20",
        )


def test_it_does_not_open_a_pull_request(tmp_path, complete_scaffold):
    """Invariant 13: a lab landing into a private local overlay gets the identical path.
    Making GitHub the approval mechanism would make self-hosted a degraded tier."""
    repo = _repo(tmp_path)
    result = land(
        Draft(name="f", scaffold=complete_scaffold, module=None),
        registry=repo,
        branch="forge/f",
        approved_by="r",
        approved_at="2026-08-20",
    )
    assert not hasattr(result, "pull_request_url")


def test_a_generated_module_lands_beside_the_contract(tmp_path, complete_scaffold):
    repo = _repo(tmp_path)
    result = land(
        Draft(name="w", scaffold=complete_scaffold, module="process W {}\n"),
        registry=repo,
        branch="forge/w",
        approved_by="r",
        approved_at="2026-08-20",
    )
    assert any(f.endswith("main.nf") for f in result.files)


def test_a_new_type_lands_where_the_layer_keeps_types(tmp_path):
    from pathlib import Path

    from mendel_forge.land import _types_dir

    (tmp_path / "registry.yml").write_text(
        "name: t\nversion: 0.1.0\nrequires_format: 2\nlicence: CC-BY-4.0\ndescription: t\n"
        "layout: {vocabulary: [vocabulary/types/, tools/], tool: [tools/]}\n"
    )
    assert _types_dir(tmp_path) == Path("vocabulary/types")


def test_a_layer_with_no_layout_keeps_types_in_types(tmp_path):
    from pathlib import Path

    from mendel_forge.land import _types_dir

    assert _types_dir(tmp_path) == Path("types")


def test_landing_into_an_arranged_layer_writes_types_under_vocabulary(
    tmp_path, complete_scaffold
):
    """Review focus (#216): a type landed in `types/` is refused by the next lint."""
    from mendel_forge.scaffold import Decision, Hole, Proposal

    field = "produces[0].type_id"
    open_hole = complete_scaffold.model_copy(
        update={
            "holes": [Hole(subject=field, what="the output's type", why_open="type: file")],
            "filled": {k: v for k, v in complete_scaffold.filled.items() if k != field},
        }
    )
    scaffold = open_hole.propose(
        field, Proposal(id="qc.index_stats", description="d", why="nothing fits", by="r")
    ).decide(field, Decision.APPROVED, by="r", why="w")
    repo = _repo(tmp_path)
    (repo / "registry.yml").write_text(
        "name: t\nlayout: {vocabulary: [vocabulary/types/, tools/], tool: [tools/]}\n"
    )
    subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qam", "layout"],
        cwd=repo,
        check=True,
    )
    result = land(
        Draft(name="fastqc", scaffold=scaffold, module=None),
        registry=repo,
        branch="forge/fastqc",
        approved_by="rafael",
        approved_at="2026-08-20",
    )
    landed = [f for f in result.files if f.endswith(".yml") and "/types/" in f"/{f}"]
    assert landed, "the fixture must propose a type or this test is vacuous"
    assert all(f.startswith("vocabulary/types/") for f in landed), landed

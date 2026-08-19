"""Taking the source's value: one line, validated, then one commit.

**Every accept has a paired refusal here.** A single positive assertion cannot tell you it is
vacuous, and phase 3 found two defects in one run by adding the half that must fail.
"""

import subprocess
from pathlib import Path

import pytest
from mendel_forge import ops

ROOT = Path(__file__).resolve().parents[3]
SOURCE = ROOT / "vendor"

FASTQC = "tools/nf-core/fastqc/fastqc.contract.yml"
INDEX = "tools/nf-core/samtools/index.contract.yml"
"""Two fixtures, and the difference matters: FASTQC has no comments and `samtools/index` has
eight. Both paths were read off disk — the layout is `tools/<ns>/<tool>.contract.yml` for one
and `tools/<ns>/<tool>/<tool>.contract.yml` for the other, because a layer's layout is free."""


def _repo(root: Path) -> Path:
    subprocess.run(["git", "init", "-b", "main"], cwd=root, check=True, capture_output=True)
    subprocess.run(["git", "add", "-A"], cwd=root, check=True, capture_output=True)
    subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-m", "init"],
        cwd=root,
        check=True,
        capture_output=True,
    )
    return root


def _accept(registry, field="nf_process", contract_id="nf-core/fastqc@0.12.1", **kw):
    return ops.accept(
        ops.AcceptRequest(
            contract_id=contract_id,
            field=field,
            registry_root=registry,
            source_root=SOURCE,
            by="rafael",
            why="the module was bumped upstream and the process was renamed",
            **kw,
        )
    )


def test_accepting_writes_the_source_value_on_a_branch(broken_registry):
    registry = _repo(broken_registry(FASTQC, "nf_process: FASTQC", "nf_process: WRONG"))

    result = _accept(registry)

    assert result.was == "WRONG"
    assert result.now == "FASTQC"
    assert result.branch == "forge/drift"
    assert "nf_process: FASTQC" in (registry / FASTQC).read_text()
    on = subprocess.run(
        ["git", "branch", "--show-current"], cwd=registry, capture_output=True, text=True
    ).stdout.strip()
    assert on == "forge/drift"


def test_the_commit_records_who_and_why(broken_registry):
    registry = _repo(broken_registry(FASTQC, "nf_process: FASTQC", "nf_process: WRONG"))
    _accept(registry)

    message = subprocess.run(
        ["git", "log", "-1", "--format=%an%n%B"], cwd=registry, capture_output=True, text=True
    ).stdout
    assert "rafael" in message
    assert "the module was bumped upstream" in message
    assert "nf_process" in message


def test_the_comments_survive(broken_registry):
    """The whole reason accepting patches a line instead of re-serialising — spec §3.6.

    **Not FASTQC.** Measured: `fastqc.contract.yml` carries ZERO comments, so this test would
    pass over its own guard and prove nothing. `samtools/index.contract.yml` carries eight,
    including the note about the port name that was latent until conformance caught it — which
    is exactly the reasoning a YAML dumper would delete.
    """
    registry = _repo(broken_registry(INDEX, "nf_process: SAMTOOLS_INDEX", "nf_process: WRONG"))
    before = (registry / INDEX).read_text()
    comments = [line for line in before.splitlines() if line.lstrip().startswith("#")]
    assert len(comments) >= 8, "the fixture lost its comments — the test is now vacuous"

    _accept(registry, contract_id="nf-core/samtools/index@1.21.0")

    after = (registry / INDEX).read_text().splitlines()
    assert all(line in after for line in comments)


def test_a_second_accept_commits_onto_the_same_branch(broken_registry):
    """Two drifts on one contract. `land()` always creates a branch because a draft lands
    once; a drift is accepted repeatedly, so the second must not branch off the first."""
    # The fixture copies once and mutates in place, so two calls break two fields of one file.
    broken_registry(FASTQC, "nf_process: FASTQC", "nf_process: WRONG")
    registry = _repo(
        broken_registry(
            FASTQC,
            "container: quay.io/biocontainers/fastqc:0.12.1--hdfd78af_0",
            "container: quay.io/biocontainers/fastqc:0.0.0--stale",
        )
    )
    _accept(registry)
    _accept(registry, field="container")

    count = subprocess.run(
        ["git", "rev-list", "--count", "HEAD"], cwd=registry, capture_output=True, text=True
    ).stdout.strip()
    assert count == "3"  # init, then one commit per accept, on one branch


def test_it_refuses_a_field_that_is_not_drifted(broken_registry):
    registry = _repo(broken_registry(FASTQC, "nf_process: FASTQC", "nf_process: WRONG"))
    with pytest.raises(ValueError, match="MF0104"):
        _accept(registry, field="container")


def test_it_refuses_a_structural_disagreement(broken_registry):
    registry = _repo(broken_registry(FASTQC, "name: zip", "name: nonesuch"))
    with pytest.raises(ValueError, match="MF0104"):
        _accept(registry, field="produces")


def test_it_refuses_a_detached_head(broken_registry):
    registry = _repo(broken_registry(FASTQC, "nf_process: FASTQC", "nf_process: WRONG"))
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=registry, capture_output=True, text=True
    ).stdout.strip()
    subprocess.run(["git", "checkout", head], cwd=registry, check=True, capture_output=True)
    with pytest.raises(ValueError, match="MF0105"):
        _accept(registry)


def test_it_refuses_a_dirty_tree(broken_registry):
    registry = _repo(broken_registry(FASTQC, "nf_process: FASTQC", "nf_process: WRONG"))
    (registry / "stray.txt").write_text("x")
    with pytest.raises(ValueError, match="MF0101"):
        _accept(registry)


def test_it_refuses_landing_on_the_default_branch(broken_registry):
    """`land()` refuses the branch it is ASKED for; accepting creates its own, so the check
    is on the branch it would commit to. Overriding it back to `main` must still refuse."""
    registry = _repo(broken_registry(FASTQC, "nf_process: FASTQC", "nf_process: WRONG"))
    with pytest.raises(ValueError, match="MF0100"):
        _accept(registry, branch="main")


def test_it_refuses_an_unknown_contract(broken_registry):
    registry = _repo(broken_registry(FASTQC, "nf_process: FASTQC", "nf_process: WRONG"))
    with pytest.raises(ValueError, match="MF0106"):
        _accept(registry, contract_id="nf-core/fastqc")  # no @version


def test_nothing_is_written_when_the_patch_would_not_load(broken_registry, monkeypatch):
    """MF0103 — the value came from the source, which is not the same as valid."""
    registry = _repo(broken_registry(FASTQC, "nf_process: FASTQC", "nf_process: WRONG"))
    before = (registry / FASTQC).read_text()

    # A process name with a space is not an `NfIdentifier`, so the patched text cannot load.
    monkeypatch.setattr(ops, "_source_value", lambda *a, **k: "NOT AN IDENTIFIER")
    with pytest.raises(ValueError, match="MF0103"):
        _accept(registry)
    assert (registry / FASTQC).read_text() == before


def test_a_field_that_is_not_one_top_level_line_is_refused():
    """MF0102, exercised directly.

    No shipped contract spells a value field over several lines, so this is a unit test of the
    guard rather than an end-to-end one — and it is here because the guard is what makes the
    one-line patch safe. Without it the failure mode is a silent no-op or a mangled file.
    """
    absent = "id: x\nnf_process: FASTQC\n"
    with pytest.raises(ValueError, match="MF0102"):
        ops._patch_line(absent, "container", "anything")

    block = "id: x\ncontainer: >-\n  quay.io/thing:1\n"
    with pytest.raises(ValueError, match="MF0102"):
        ops._patch_line(block, "container", "anything")

    # And the half that must pass, so the refusal is not passing for the wrong reason.
    assert "nf_process: OTHER\n" in ops._patch_line(absent, "nf_process", "OTHER")

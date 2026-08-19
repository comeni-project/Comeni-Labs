from pathlib import Path

from mendel_forge import ops

ROOT = Path(__file__).resolve().parents[3]
FASTQC = "tools/nf-core/fastqc/fastqc.contract.yml"


def test_the_shipped_registry_has_no_drift_against_the_vendored_modules():
    """If this fails on a clean checkout, a shipped contract disagrees with its module and
    the finding is real — do not weaken the test."""
    result = ops.check(
        ops.CheckRequest(registry_root=ROOT / "registry", source_root=ROOT / "vendor")
    )
    assert result.drift == [], f"{len(result.drift)} disagreements: {result.drift}"


def test_drift_is_found_when_a_contract_is_edited(broken_registry):
    registry = broken_registry(FASTQC, "nf_process: FASTQC", "nf_process: WRONG")
    result = ops.check(ops.CheckRequest(registry_root=registry, source_root=ROOT / "vendor"))
    assert len(result.drift) == 1
    drift = result.drift[0]
    assert drift.field == "nf_process"
    assert drift.registry_says == "WRONG"
    assert drift.source_says == "FASTQC"
    assert drift.contract_id.startswith("nf-core/fastqc")


def test_update_turns_a_drift_into_a_draft(broken_registry, tmp_path):
    from mendel_forge.workspace import Workspace

    registry = broken_registry(FASTQC, "nf_process: FASTQC", "nf_process: WRONG")
    result = ops.update(
        ops.UpdateRequest(
            contract_id="nf-core/fastqc@0.12.1",
            name="fastqc",
            registry_root=registry,
            source_root=ROOT / "vendor",
            workspace_root=tmp_path / "workspace",
        )
    )
    draft = Workspace(root=tmp_path / "workspace").load(result.name)
    assert draft.scaffold.filled["nf_process"].value == "FASTQC"


def test_update_does_not_touch_the_registry(broken_registry, tmp_path):
    """`update` produces a draft. Only `land` writes, and Task 22 is the guard for it."""
    registry = broken_registry(FASTQC, "nf_process: FASTQC", "nf_process: WRONG")
    path = registry / FASTQC
    before = path.read_text()
    ops.update(
        ops.UpdateRequest(
            contract_id="nf-core/fastqc@0.12.1",
            name="fastqc",
            registry_root=registry,
            source_root=ROOT / "vendor",
            workspace_root=tmp_path / "workspace",
        )
    )
    assert path.read_text() == before

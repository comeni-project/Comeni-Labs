"""Saved-pipeline gate verdicts: observable CLI and artifact behavior."""

import yaml
from mendel_compiler.cli import main
from support.paths import ROOT
from support.pipeline import (
    _answer,
    _build,
    _declared,
    _emit,
)


# Regression evidence: A47
# --- A47: emit carries the gate verdict rather than erasing it ---
def test_emit_preserves_the_gate_verdict(tmp_path, capsys, monkeypatch):
    """A re-emit that changes nothing must not drop the certification. `gate:` is load-bearing —
    the evidence and the pipeline are one document, and the archive workflow regenerates later.

    `publish` stamps the verdict and the digests together, so the file is not stale; a no-op
    `emit` afterwards must carry it through. The gate itself is stubbed so this runs in CI's
    Nextflow-free lane — the property under test is the verdict round trip, not `nextflow lint`."""
    from mendel_compiler.cli import artifact_verbs
    from mendel_compiler.gates import GateResult

    monkeypatch.setattr(
        artifact_verbs, "run_gate", lambda gate, out: GateResult(gate=gate, passed=True)
    )
    out = _build(tmp_path)
    assert main(["publish", str(out / "pipeline.yml"), "--gate", "lint", "--root", str(ROOT)]) == 0
    assert yaml.safe_load((out / "pipeline.yml").read_text())["gate"] == "lint"
    code, err = _emit(out, capsys)
    assert code == 0 and "MD0213" not in err, err  # not stale — a genuine no-op re-emit
    assert yaml.safe_load((out / "pipeline.yml").read_text())["gate"] == "lint"


# Regression evidence: A47
def test_emit_clears_the_gate_verdict_when_the_file_was_edited(tmp_path, capsys):
    """A stale file has changed since it was gated, so its verdict no longer describes this
    pipeline. Preserving it would certify content that never passed the gate."""
    out = _build(tmp_path)
    doc = yaml.safe_load((out / "pipeline.yml").read_text())
    doc["gate"] = "lint"
    (out / "pipeline.yml").write_text(
        _declared(out / "pipeline.yml", yaml.safe_dump(doc, sort_keys=False))
    )
    _emit(out, capsys)  # settle emitted digests against the gate stamp
    _answer(out, "seq_platform", "nanopore")  # now edit — the pipeline changed
    code, err = _emit(out, capsys)
    assert code == 0 and "MD0213" in err
    assert yaml.safe_load((out / "pipeline.yml").read_text())["gate"] is None

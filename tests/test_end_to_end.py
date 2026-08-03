import json
import pathlib

from mendel_compiler.cli import main

ROOT = pathlib.Path(__file__).parent.parent


def test_builds_a_pipeline_from_the_example_goal(tmp_path):
    exit_code = main([
        "build",
        "--goal", str(ROOT / "examples" / "rnaseq-goal.yml"),
        "--out", str(tmp_path / "pipeline"),
        "--root", str(ROOT),
    ])
    assert exit_code == 0
    source = (tmp_path / "pipeline" / "main.nf").read_text()
    assert "STAR_ALIGN" in source
    assert "FEATURECOUNTS" in source
    assert (tmp_path / "pipeline" / "pipeline.ir.json").exists()


def test_strandedness_resolves_at_tier_3_from_the_profile(tmp_path):
    main([
        "build",
        "--goal", str(ROOT / "examples" / "rnaseq-goal.yml"),
        "--out", str(tmp_path / "pipeline"),
        "--root", str(ROOT),
    ])
    ir = json.loads((tmp_path / "pipeline" / "pipeline.ir.json").read_text())
    node = next(n for n in ir["nodes"] if n["id"] == "subread_featurecounts")
    strandedness = next(b["value"] for b in node["params"] if b["name"] == "strandedness")
    assert strandedness["value"] == 2
    assert strandedness["tier"] == 3
    assert strandedness["review_level"] == "advisory"


def test_an_overlay_shadows_and_says_so(tmp_path, capsys):
    """--registry stacks layers, and a build on a modified registry announces it."""
    # A layer is a directory holding contracts/, rules/ and vocabularies/ — the lab ships
    # only contracts here, and inherits the base layer's types and rules.
    overlay = tmp_path / "lab"
    (overlay / "contracts").mkdir(parents=True)
    (overlay / "rules").mkdir()
    (overlay / "vocabularies").mkdir()
    base = ROOT / "examples" / "contracts" / "nf-core" / "samtools-sort.yml"
    (overlay / "contracts" / "sort.yml").write_text(
        base.read_text().replace("@1.21.0", "@1.99.0")
    )

    exit_code = main([
        "build",
        "--goal", str(ROOT / "examples" / "rnaseq-goal.yml"),
        "--out", str(tmp_path / "pipeline"),
        "--root", str(ROOT),
        "--registry", str(ROOT / "examples"),
        "--registry", str(overlay),
    ])
    assert exit_code == 0
    assert "SHADOW  nf-core/samtools/sort" in capsys.readouterr().err
    ir = json.loads((tmp_path / "pipeline" / "pipeline.ir.json").read_text())
    assert "nf-core/samtools/sort@1.99.0" in [n["contract_id"] for n in ir["nodes"]]


def test_two_builds_produce_identical_output(tmp_path):
    for name in ["a", "b"]:
        main([
            "build",
            "--goal", str(ROOT / "examples" / "rnaseq-goal.yml"),
            "--out", str(tmp_path / name),
            "--root", str(ROOT),
        ])
    assert (tmp_path / "a" / "main.nf").read_text() == (tmp_path / "b" / "main.nf").read_text()


def test_output_is_identical_across_hash_seeds(tmp_path):
    """Determinism, actually proven rather than assumed.

    `test_two_builds_produce_identical_output` runs both builds in one process, so it
    cannot detect hash-seed dependence — a `set` iteration order leaking into output
    would keep it green. The 2026-08-03 audit confirmed the property by hand under four
    seeds; this automates it.

    On its own this is a weak guard today: every state set the spine produces has one
    element, and a one-element set has no order to vary. Removing the `IREdge.states`
    serialiser leaves it green. `test_multi_state_serialisation_is_seed_independent`
    below is the one that actually bites; this one guards the whole pipeline as the
    registry grows states worth reordering.
    """
    import os
    import subprocess
    import sys

    digests = []
    for seed in ("1", "99999"):
        out = tmp_path / f"seed{seed}"
        env = {**os.environ, "PYTHONHASHSEED": seed}
        result = subprocess.run(
            [sys.executable, "-m", "mendel_compiler.cli", "build",
             "--goal", str(ROOT / "examples" / "rnaseq-goal.yml"),
             "--out", str(out), "--root", str(ROOT)],
            env=env, capture_output=True, text=True, check=False,
        )
        assert result.returncode == 0, result.stderr
        digests.append(
            ((out / "main.nf").read_text(), (out / "pipeline.ir.json").read_text())
        )

    assert digests[0][0] == digests[1][0], "main.nf differs across PYTHONHASHSEED"
    assert digests[0][1] == digests[1][1], "pipeline.ir.json differs across PYTHONHASHSEED"


def test_multi_state_serialisation_is_seed_independent(tmp_path):
    """The guard that actually catches a hash-order leak.

    `frozenset` iterates in hash order, which varies with PYTHONHASHSEED, so anything
    serialising one without sorting produces different bytes on different runs. Written
    after the CLI-level test above passed with the `IREdge.states` serialiser deleted —
    it could not fail, because no state set in the spine has more than one member.
    """
    import os
    import subprocess
    import sys

    script = (
        "from comeni_core.ir import IREdge;"
        "print(IREdge(from_node='a', from_port='p', to_node='b', to_port='q',"
        " type_id='alignment.bam',"
        " states=frozenset({'coordinate_sorted','indexed','deduplicated','filtered'})"
        ").model_dump_json())"
    )
    outputs = set()
    for seed in ("1", "7", "99999"):
        result = subprocess.run(
            [sys.executable, "-c", script],
            env={**os.environ, "PYTHONHASHSEED": seed},
            capture_output=True, text=True, check=True,
        )
        outputs.add(result.stdout)
    assert len(outputs) == 1, f"serialisation varies with PYTHONHASHSEED: {outputs}"

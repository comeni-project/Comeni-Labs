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

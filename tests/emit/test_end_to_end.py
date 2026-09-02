import pathlib

import yaml
from mendel_compiler.cli import main
from support.paths import ROOT

_KIND_OF_DIR = {
    "contracts": "contract",
    "vocabularies": "vocabulary",
    "measurements": "measurement",
    "roles": "role",
    "rules": "rule",
}


def _declared(path, body: str) -> str:
    """Prepend what a fixture's file declares, derived from the directory it is written into.

    Since comeni-registry#1 a declared file says what it is and the loader no longer reads the
    directory. These fixtures still *write* into kind-named directories, which is now only a
    habit — and the habit is what tells this helper which line to add, so the fixtures keep
    their shape and their subject stays readable.

    Idempotent, because several fixtures write a file twice to check that something changed.
    """
    path = pathlib.Path(path)
    # Walk *ancestors*, not just the immediate parent: real layers nest, and
    # `tools/nf-core/fastqc/contract.yml` sits two levels down from the directory that
    # names it.
    kind = next(
        (_KIND_OF_DIR[p.name] for p in path.parents if p.name in _KIND_OF_DIR), None
    )
    if kind is None or body.lstrip().startswith("declares:"):
        return body
    header = f"declares: {kind}\n"
    if kind in ("vocabulary", "measurement"):
        header += f"id: {path.name.removesuffix('.yml').removesuffix('.yaml')}\n"
    return header + body



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
    assert (tmp_path / "pipeline" / "pipeline.yml").exists()


def test_the_measured_strandedness_reaches_the_tool(tmp_path):
    """This asserted a tier-3 param resolving to 2. That param reached no tool.

    `params.subread_featurecounts_strandedness = 2` was emitted and read by nothing —
    nf-core modules take configuration through `task.ext.args` and `meta`. featureCounts
    contains the translation itself (`meta.strandedness == 'reverse'` -> `-s 2`), so the
    rule was a translation wearing a tier-3 badge and is deleted. The guarantee is the
    same and now lives where it can actually take effect. See Plan 1.5.
    """
    main([
        "build",
        "--goal", str(ROOT / "examples" / "rnaseq-goal.yml"),
        "--out", str(tmp_path / "pipeline"),
        "--root", str(ROOT),
    ])
    source = (tmp_path / "pipeline" / "main.nf").read_text()
    reads = next(ln for ln in source.splitlines() if "ch_reads =" in ln)
    assert "strandedness: 'reverse'" in reads, reads
    assert "single_end: false" in reads, reads


def test_an_overlay_displaces_and_says_so(tmp_path, capsys):
    """--registry stacks layers, and a build on a modified registry announces it.

    One `OVERLAY` block for all four kinds since A23-A25. It was `SHADOW`, printed off
    the registry and covering contracts alone, so an overlay measurement or vocabulary had
    nowhere to be announced at all.
    """
    # A layer is a directory holding contracts/, rules/ and vocabularies/ — the lab ships
    # only contracts here, and inherits the base layer's types and rules.
    overlay = tmp_path / "lab"
    (overlay / "contracts").mkdir(parents=True)
    (overlay / "rules").mkdir()
    (overlay / "vocabularies").mkdir()
    base = ROOT / "registry" / "tools" / "nf-core" / "samtools" / "sort/contract.yml"
    (overlay / "contracts" / "sort.yml").write_text(
        _declared(
            overlay / "contracts" / "sort.yml",
            base.read_text().replace("@1.21.0", "@1.99.0"))
    )

    exit_code = main([
        "build",
        "--goal", str(ROOT / "examples" / "rnaseq-goal.yml"),
        "--out", str(tmp_path / "pipeline"),
        "--root", str(ROOT),
        "--registry", str(ROOT / "registry"),
        "--registry", str(overlay),
    ])
    assert exit_code == 0
    assert "OVERLAY  contracts: nf-core/samtools/sort@1.99.0" in capsys.readouterr().err
    pipeline = yaml.safe_load((tmp_path / "pipeline" / "pipeline.yml").read_text())
    pinned = [step["module"]["contract_id"] for step in pipeline["steps"]]
    assert "nf-core/samtools/sort@1.99.0" in pinned


def test_a_goal_file_cannot_smuggle_a_measurement_nobody_declared(tmp_path, capsys):
    """Invariant 15 at the door a goal file actually enters through.

    `DataProfile` accepts a mapping because that is how a person writes one, and since
    measurements became declared data the model cannot know which keys are real. So the
    check moved to `MeasurementRegistry.profile()` and `mendel build` routes every goal
    through it. Without that call `profile: {sample_name: SILVA_biopsy_01}` validates,
    resolves and reaches `pipeline.yml` — the shape of the hole the 2026-08-03 audit
    found in `constraints`, re-opened one field over.
    """
    goal = tmp_path / "goal.yml"
    goal.write_text(
        _declared(goal, "have: [{type_id: fastq.reads}]\nwant: [qc.report]\n"
        "profile: {read_length: 150, sample_name: SILVA_biopsy_01}\n")
    )
    exit_code = main([
        "build", "--goal", str(goal), "--out", str(tmp_path / "p"), "--root", str(ROOT),
    ])
    assert exit_code == 2
    assert "sample_name" in capsys.readouterr().err


def test_a_goal_file_cannot_carry_an_out_of_range_measurement(tmp_path, capsys):
    goal = tmp_path / "goal.yml"
    goal.write_text(
        _declared(
            goal,
            "have: [{type_id: fastq.reads}]\nwant: [qc.report]\nprofile: {read_length: 0}\n")
    )
    assert main([
        "build", "--goal", str(goal), "--out", str(tmp_path / "p"), "--root", str(ROOT),
    ]) == 2
    assert "minimum" in capsys.readouterr().err


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
            ((out / "main.nf").read_text(), (out / "pipeline.yml").read_text())
        )

    assert digests[0][0] == digests[1][0], "main.nf differs across PYTHONHASHSEED"
    assert digests[0][1] == digests[1][1], "pipeline.yml differs across PYTHONHASHSEED"


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
        "from comeni_core.plan.ir import IREdge;"
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

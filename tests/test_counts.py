"""The spine produces a counts matrix, and the matrix is right.

`gate stub: PASS` proves the DAG executes. This proves the analysis ran with the
parameters that were decided — a different claim, and the one a biologist reads.

Marked `slow`: it needs Docker, Nextflow and about ten minutes. CI runs it nightly.
"""

import pathlib
import subprocess

import pytest
from mendel_resolver import layers

ROOT = pathlib.Path(__file__).parent.parent


def test_the_registry_has_one_tier_three_rule_and_it_is_the_aligner():
    """The strandedness block was a translation the module already performs. What remains
    is a genuine decision between two defensible aligners, with a real citation."""
    table = layers.load(ROOT / "registry").rules
    assert [d.decides.key() for d in table.decisions] == ["producer_of:alignment.bam"]


def test_featurecounts_declares_no_strandedness_parameter():
    """Strandedness arrives through meta, and a `Param` for it would resolve to a value that
    reaches nothing — the defect this whole plan is about removing.

    This asserted `params == []` until Plan 1.10 Task 7, which is a stronger claim than the
    argument supports and it blocked the one thing that argument needs: a declared setting
    whose flag is watched arriving at a real tool. The claim is now about strandedness, which
    is what was ever true, plus the rule that every param carries a route.
    """
    contract = layers.load(ROOT / "registry").registry.get("nf-core/subread/featurecounts@2.0.6")
    assert "strandedness" not in [param.name for param in contract.params]
    assert all(param.via for param in contract.params), "a setting with no route is the defect"


@pytest.fixture(scope="module")
def run(tmp_path_factory):
    """One real run, shared. Ten minutes is too long to pay twice."""
    out = tmp_path_factory.mktemp("spine") / "build"
    result = subprocess.run(
        ["uv", "run", "mendel", "build", "--goal", str(ROOT / "examples/rnaseq-goal.yml"),
         "--out", str(out), "--root", str(ROOT), "--gate", "test"],
        cwd=ROOT, capture_output=True, text=True, check=False,
    )
    return out, result


@pytest.mark.slow
def test_the_spine_produces_a_counts_matrix(run):
    out, result = run
    assert result.returncode == 0, result.stderr[-4000:]

    matrices = list(out.rglob("*.featureCounts.txt")) + list(out.rglob("*.featureCounts.tsv"))
    assert matrices, "no counts matrix was produced"
    rows = [ln for ln in matrices[0].read_text().splitlines() if not ln.startswith("#")]
    assert len(rows) > 1, "the counts matrix has a header and no genes"


@pytest.mark.slow
def test_featurecounts_ran_with_the_strandedness_that_was_measured(run):
    """The point of the whole plan. `examples/rnaseq-goal.yml` declares reverse, so
    featureCounts must have run with `-s 2`. Before this plan it ran with `-s 0` and
    produced a matrix full of wrong numbers, silently, passing every gate."""
    out, _ = run
    scripts = [
        c.read_text()
        for c in (out / "work").rglob(".command.sh")
        if "featureCounts" in c.read_text()
    ]
    assert scripts, "featureCounts never ran"
    assert "-s 2" in scripts[0], scripts[0]
    assert "-p" in scripts[0], "paired-end reads must be counted as fragments"


@pytest.mark.slow
def test_a_resolved_setting_reaches_the_tool(run):
    """The only check that a value Mendel resolved changed what a tool was asked to do.

    `MD0204` catches a template that ignores `{value}`. **Nothing catches a template whose
    flag is wrong** — the flag goes to the tool, not to the module, so conformance cannot see
    it and `-stub-run` cannot either: an nf-core stub never reads its inputs and never runs
    the tool. This is the same blind spot that let two modules ship with hollow inputs, and
    `--gate test` is the only thing that sees through it.

    `-Q 0` is featureCounts' own default, so this asserts the *route* without moving a single
    number in the matrix the test above checks. A wrong flag still fails here, because what is
    read is the command line rather than the result.
    """
    out, _ = run
    scripts = [
        c.read_text()
        for c in (out / "work").rglob(".command.sh")
        if "featureCounts" in c.read_text()
    ]
    assert scripts, "featureCounts never ran"
    assert "-Q 0" in scripts[0], scripts[0]

"""The build path, callable without argparse.

**This is the prerequisite three plans named and none built.** `resolve_verbs.run` takes a
`Namespace` and writes files, so `mendel-api` could not call it — which is why 3C came last.

The test that matters is not that the function exists. It is that **it produces byte-identical
output to the CLI**, because a seam that quietly changes the artifact is worse than no seam.
Moving orchestration is exactly the change `make check` waves through: nothing outside
`test_counts.py` runs a tool, so a lost flag is invisible to every other test here.
"""

import subprocess
import sys
from pathlib import Path

from comeni_core import yaml_strict
from mendel_compiler import orchestrate, pipeline_file
from mendel_compiler.emit import emit, emit_config
from mendel_resolver.goal import Goal

ROOT = Path(__file__).resolve().parents[3]
GOAL = ROOT / "examples" / "rnaseq-goal.yml"


def _goal() -> Goal:
    return Goal.model_validate(yaml_strict.load(GOAL))


def test_the_seam_builds_the_spine_without_touching_disk(tmp_path):
    built = orchestrate.build(
        _goal(), registry_root=ROOT / "registry", vendor_root=ROOT / "vendor"
    )
    assert built.pipeline.steps, "the spine has steps"
    assert list(tmp_path.iterdir()) == [], "the seam wrote nothing"


def test_the_seam_and_the_cli_agree_byte_for_byte(tmp_path):
    """**The only assertion that makes the extraction safe.**

    It compares the serialised artifact, which is what `mendel emit` reads and what a person
    reviews — not the object graph, which can agree while the bytes differ.
    """
    out = tmp_path / "cli"
    subprocess.run(
        [sys.executable, "-m", "mendel_compiler.cli", "build",
         "--goal", str(GOAL), "--out", str(out)],
        check=True,
        cwd=ROOT,
    )
    from_cli = (out / pipeline_file.FILENAME).read_text()

    built = orchestrate.build(
        _goal(), registry_root=ROOT / "registry", vendor_root=ROOT / "vendor"
    )
    seam = tmp_path / "seam"
    seam.mkdir()

    # **The same three writes the CLI does, in the same order**, because `emitted:` is the
    # digest of files on disk — `pipeline_file.stamp` reads them back. Comparing an unstamped
    # pipeline against a stamped one differs in exactly that block and nothing else, which was
    # the first run of this test and is a fact worth knowing rather than a failure: 540 lines
    # agreed and only the record of what had been emitted did not.
    #
    # Stamping stays in the CLI on purpose. It is a filesystem operation, and a seam that
    # writes is a seam an API cannot call — which is the whole reason this phase exists.
    written = pipeline_file.write(seam, built.pipeline)
    (seam / "main.nf").write_text(emit(written))
    (seam / "nextflow.config").write_text(emit_config(written))
    pipeline_file.stamp(seam, written)

    assert (seam / pipeline_file.FILENAME).read_text() == from_cli
    assert (seam / "main.nf").read_text() == (out / "main.nf").read_text()

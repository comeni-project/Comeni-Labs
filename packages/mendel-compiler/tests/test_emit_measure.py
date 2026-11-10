"""A pipeline measurer emitted as a step: its process, its runner and its pieces (#465)."""

import stat
import subprocess
import sys
from pathlib import Path

from comeni_core.artifact.digest import digest_of_bytes
from mendel_compiler import conformance, measure_module, orchestrate, pipeline_file, staging
from mendel_compiler.emit import emit, emit_config
from mendel_compiler.modulespec import ModuleSpec
from mendel_resolver import layers
from mendel_resolver.goal import Goal, GoalInput
from mendel_resolver.measure_steps import RUNNER_IMAGE, steps_for

ROOT = Path(__file__).resolve().parents[3]
LOADED = layers.load(ROOT / "registry")
FASTQ = next(s for s in steps_for(LOADED.inspection, LOADED.registry) if s.name == "fastq")
FIXTURES = ROOT / "registry/measurers/formats/fastq/piece/fixtures"


def _built():
    goal = Goal(have=[GoalInput(type_id="fastq.reads")], want=["measurement.read_length"])
    return orchestrate.build(goal, registry_root=ROOT / "registry")


def test_the_generated_module_conforms_to_its_contract():
    text = measure_module.files(FASTQ)["main.nf"].decode()
    spec = ModuleSpec.of(text, where="MEASURE_FASTQ")
    assert conformance.against(FASTQ.contract, spec, Path("main.nf")) == []


def test_the_process_runs_the_pinned_image():
    text = measure_module.files(FASTQ)["main.nf"].decode()
    assert "process MEASURE_FASTQ" in text and f"container '{RUNNER_IMAGE}'" in text
    # The launcher's mode bit does not survive a zip (Task 5 review): it is run by python3.
    assert 'python3 -I "\\$(command -v comeni-measure-fastq)" ${data}' in text


def test_a_build_wanting_a_measurement_emits_the_step():
    built = _built()
    (step,) = built.pipeline.steps
    assert step.process == "MEASURE_FASTQ" and step.module.container == RUNNER_IMAGE
    assert "MEASURE_FASTQ" in emit(built.pipeline)
    assert "nextflow.enable.moduleBinaries = true" in emit_config(built.pipeline)


def test_staging_writes_the_runner_and_pieces_and_stamp_digests_them(tmp_path):
    built = _built()
    steps = steps_for(built.layers.inspection, built.layers.registry)
    written = staging.stage(built.pipeline, built.layers.modules, tmp_path, measuring=steps)
    assert written == ["comeni/measure/fastq"]
    folder = tmp_path / "modules/comeni/measure/fastq"
    launcher = folder / "resources/usr/bin/comeni-measure-fastq"
    assert launcher.stat().st_mode & stat.S_IXUSR
    assert (folder / "resources/usr/bin/comeni_measure/comeni_inspect/core.py").is_file()
    (tmp_path / "main.nf").write_text(emit(built.pipeline))
    (tmp_path / "nextflow.config").write_text(emit_config(built.pipeline))
    stamped = pipeline_file.stamp(tmp_path, built.pipeline)
    names = {f.name: f.digest for f in stamped.emitted.files}
    assert names["modules/comeni/measure/fastq/resources/usr/bin/comeni-measure-fastq"] == \
        digest_of_bytes(launcher.read_bytes())


def test_staging_twice_is_byte_identical(tmp_path):
    built = _built()
    steps = steps_for(built.layers.inspection, built.layers.registry)
    for out in (tmp_path / "a", tmp_path / "b"):
        staging.stage(built.pipeline, built.layers.modules, out, measuring=steps)
    first = {p.relative_to(tmp_path / "a"): p.read_bytes()
             for p in (tmp_path / "a").rglob("*") if p.is_file()}
    second = {p.relative_to(tmp_path / "b"): p.read_bytes()
              for p in (tmp_path / "b").rglob("*") if p.is_file()}
    assert first and first == second


def test_the_staged_launcher_measures_a_gzipped_pair_on_a_bare_python(tmp_path):
    """What the step runs: the launcher, `python3 -I -S`, no installed package (#465)."""
    files = measure_module.files(FASTQ)
    for name, data in files.items():
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    pair = sorted((FIXTURES / "pair_150").glob("*.gz"))
    done = subprocess.run(
        [sys.executable, "-I", "-S", str(tmp_path / "resources/usr/bin/comeni-measure-fastq"),
         *map(str, pair)],
        capture_output=True, text=True, env={},
    )
    import json

    report = json.loads(done.stdout)
    assert report["facts"]["paired"]["value"] is True, done.stderr
    assert report["facts"]["paired"]["coverage"] == "all"


def test_a_restage_leaves_no_file_an_earlier_piece_left(tmp_path):
    """Task 5 review: the folder is exactly the step's files, whatever was there before."""
    built = _built()
    steps = steps_for(built.layers.inspection, built.layers.registry)
    stale = tmp_path / "modules/comeni/measure/fastq/resources/usr/bin/comeni_measure/old.py"
    stale.parent.mkdir(parents=True)
    stale.write_text("x = 1\n")
    staging.stage(built.pipeline, built.layers.modules, tmp_path, measuring=steps)
    assert not stale.exists()


def test_the_step_runs_without_the_launcher_s_mode_bit(tmp_path):
    """What a zip does to it: 0644. The process runs the launcher through python3 anyway."""
    files = measure_module.files(FASTQ)
    for name, data in files.items():
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        path.chmod(0o644)
    pair = sorted((FIXTURES / "pair_150").glob("*.gz"))
    launcher = tmp_path / "resources/usr/bin/comeni-measure-fastq"
    done = subprocess.run([sys.executable, "-I", str(launcher), *map(str, pair)],
                          capture_output=True, text=True,
                          env={})
    import json

    assert json.loads(done.stdout)["facts"]["read_length"]["coverage"] == "all", done.stderr

"""A run input may be a table of several items, and a step reading one sample and one item runs on
every pair (#466, stage 6 part B).

A profiler reads each sample against each database of a table: the table has a `name` column,
one column per file and one per item fact a port selects on.
"""

import shutil
import subprocess

import pytest
from comeni_core.artifact.pipeline import Pipeline
from mendel_compiler import orchestrate
from mendel_compiler.emit import emit, emit_config
from mendel_resolver.goal import Goal
from support.paths import ROOT

from emit.fixtures.tables import SHORT_ONLY, layer, modules

GOAL = {"have": [{"type_id": "fastq.reads"}, {"type_id": "database.index"}],
        "want": ["profile.tsv"]}


def _built(tmp_path, constraints=None, extra=None, goal=None) -> Pipeline:
    goal = Goal.model_validate({**(goal or GOAL),
                                "constraints": {"tables": ["database.index"],
                                                **(constraints or {})}})
    return orchestrate.build(goal, registry_roots=[ROOT / "registry", layer(tmp_path, extra)]
                             ).pipeline


def _call(text: str, process: str) -> str:
    return next(line.strip() for line in text.splitlines()
                if line.strip().startswith(f"{process}("))


@pytest.mark.parametrize("bad, code", [
    ({"have": [{"type_id": "fastq.reads"}], "want": ["qc.report"]}, "MD0347"),
    ({**GOAL, "constraints": {"tables": ["fastq.reads"]}}, "MD0347"),
    ({**GOAL, "constraints": {"tables": ["database.index"], "units": ["database.index"]}},
     "MD0340"),
])
def test_only_a_study_input_the_goal_has_may_be_a_table(tmp_path, bad, code):
    constraints = {"tables": ["database.index"], **bad.get("constraints", {})}
    goal = Goal.model_validate({**bad, "constraints": constraints})
    with pytest.raises(ValueError, match=code):
        orchestrate.build(goal, registry_roots=[ROOT / "registry", layer(tmp_path)])


def test_the_saved_pipeline_records_the_table(tmp_path):
    pipeline = _built(tmp_path, extra={"profile.contract.yml": SHORT_ONLY})
    (db,) = [c for c in pipeline.channels if c.type_id == "database.index"]
    assert db.table.columns == db.columns and db.table.facts == ["db_type"]
    assert db.table.name == "database"
    assert db.grain.value == "study"
    assert Pipeline.model_validate(pipeline.model_dump(mode="json")) == pipeline


def test_the_table_is_read_with_its_checks(tmp_path):
    text = emit(_built(tmp_path, extra={"profile.contract.yml": SHORT_ONLY}))
    assert ".splitCsv(header: true)" in text
    assert "has no name" in text and "is named twice" in text
    assert "db_type: row.db_type" in text
    assert "checkIfExists: true" in text


def test_without_tables_the_pipeline_is_as_before(tmp_path):
    goal = Goal.model_validate(GOAL)
    text = emit(orchestrate.build(goal, registry_roots=[ROOT / "registry", layer(tmp_path)]
                                  ).pipeline)
    assert "splitCsv" not in text and "combine" not in text.split("PROFILE(")[1]


def test_every_sample_meets_every_row(tmp_path):
    text = emit(_built(tmp_path))
    assert "ch_cross_profile = " in text
    assert ".combine(" in text and ".multiMap {" in text
    assert "database: t[0]" in text
    assert _call(text, "PROFILE") == "PROFILE(ch_cross_profile.sample, ch_cross_profile.table)"


def test_a_port_selects_rows_by_their_facts(tmp_path):
    cross = next(line for line in emit(_built(tmp_path, extra={
        "profile.contract.yml": SHORT_ONLY})).splitlines() if "ch_cross_profile = " in line)
    assert ".filter {" in cross and "meta.db_type" in cross


def test_each_pair_publishes_under_its_own_name(tmp_path):
    config = emit_config(_built(tmp_path))
    assert 'withName: PROFILE { ext.prefix = { "${meta.id}_${meta.database.id}" } }' in config


def test_a_sample_meeting_no_row_stops_the_run(tmp_path):
    text = emit(_built(tmp_path))
    assert "meets no row of database" in text


def test_a_by_sample_join_after_the_cross_is_refused(tmp_path):
    """MD0348: it would pair each sample with one row's result."""
    from emit.fixtures.tables import LAYER

    joiner = """declares: contract
id: lab/compare@1.0.0
nf_process: COMPARE
nf_include: modules/lab/compare/main
roles: [comparing]
consumes:
  - {name: profile, type_id: profile.tsv}
  - {name: reads, type_id: fastq.reads}
produces: [{name: report, type_id: report.txt, format: [txt]}]
nf_inputs: [{ports: [profile, reads], join: by_sample}]
""" + LAYER["profile.contract.yml"].split("produces:")[1].split("\n", 2)[2]
    extra = {"compare.contract.yml": joiner,
             "report.family.yml": "declares: family\nid: report\ndescription: Reports\n",
             "report.txt.yml": "declares: vocabulary\nid: report.txt\nstates: []\n",
             "comparing.role.yml": "declares: role\nroles:\n  - {id: comparing, explain: x.}\n"}
    with pytest.raises(ValueError, match="MD0348"):
        _built(tmp_path, extra=extra, goal={**GOAL, "want": ["report.txt"]})


def _run(tmp_path, rows, extra=None, missing=False):
    from support.pipeline import _starter

    goal = {**GOAL, "constraints": {"tables": ["database.index"]}}
    starter = _starter(tmp_path / "starter.yml", goal)
    out = tmp_path / "built"
    done = subprocess.run(
        ["uv", "run", "mendel", "build", str(starter), "--registry", "registry",
         "--registry", str(layer(tmp_path, extra)), "--out", str(out)],
        cwd=ROOT, capture_output=True, text=True)
    assert done.returncode == 0, done.stdout + done.stderr
    modules(out)
    data = tmp_path / "data"
    data.mkdir(exist_ok=True)
    for sample in ("S1", "S2"):
        for mate in (1, 2):
            (data / f"{sample}_R{mate}.fq.gz").write_text("stub\n")
    from comeni_core import yaml_strict

    saved = Pipeline.model_validate(yaml_strict.load(out / "pipeline.yml"))
    table = next(c for c in saved.channels if c.type_id == "database.index")
    (column,) = table.table.columns
    lines = ["name," + column + (",db_type" if extra else "")]
    for name, kind in rows:
        path = data / f"{name or 'blank'}.db"
        if missing:
            path = data / "gone.db"
        else:
            path.write_text("db\n")
        lines.append(f"{name},{path}" + (f",{kind}" if extra else ""))
    (data / "dbs.csv").write_text("\n".join(lines) + "\n")
    results = tmp_path / "results"
    param = table.param
    done = subprocess.run(
        ["nextflow", "-q", "run", "main.nf", "-stub-run", "-profile", "stub_data,docker",
         "--input", str(data / "*_R{1,2}.fq.gz"), f"--{param}", str(data / "dbs.csv"),
         "--outdir", str(results)],
        cwd=out, capture_output=True, text=True, timeout=900)
    return done, results


def _needs_tools():
    if shutil.which("nextflow") is None or shutil.which("docker") is None:
        pytest.skip("needs Nextflow and Docker")


@pytest.mark.slow
def test_two_samples_by_two_databases_give_four_profiles(tmp_path):
    """Review Focus 4: every pair, each published under its own name."""
    _needs_tools()
    done, results = _run(tmp_path, [("k2", ""), ("mp", "")])
    assert done.returncode == 0, done.stdout + done.stderr
    published = sorted(p.name for p in (results / "profile").iterdir())
    assert published == ["S1_k2.tsv", "S1_mp.tsv", "S2_k2.tsv", "S2_mp.tsv"]
    assert (results / "profile/S2_mp.tsv").read_text().split() == ["S2", "mp", "mp"]


@pytest.mark.slow
def test_a_selection_leaves_only_its_rows(tmp_path):
    _needs_tools()
    done, results = _run(tmp_path, [("k2", "short"), ("lr", "long")],
                         extra={"profile.contract.yml": SHORT_ONLY})
    assert done.returncode == 0, done.stdout + done.stderr
    assert sorted(p.name for p in (results / "profile").iterdir()) == ["S1_k2.tsv", "S2_k2.tsv"]


@pytest.mark.slow
@pytest.mark.parametrize("rows, says", [
    ([("", "")], "has no name"),
    ([("k2", ""), ("k2", "")], "is named twice"),
])
def test_a_bad_row_stops_the_run_naming_it(tmp_path, rows, says):
    """Review Focus 5."""
    _needs_tools()
    done, _ = _run(tmp_path, rows)
    assert done.returncode != 0 and says in done.stdout + done.stderr


@pytest.mark.slow
def test_a_missing_file_stops_the_run(tmp_path):
    _needs_tools()
    done, _ = _run(tmp_path, [("k2", "")], missing=True)
    assert done.returncode != 0 and "gone.db" in done.stdout + done.stderr


@pytest.mark.slow
def test_a_sample_left_with_no_row_stops_the_run(tmp_path):
    _needs_tools()
    done, _ = _run(tmp_path, [("lr", "long")], extra={"profile.contract.yml": SHORT_ONLY})
    assert done.returncode != 0
    assert "meets no row of database" in done.stdout + done.stderr


def test_a_crossed_step_taking_only_some_samples_is_refused(tmp_path):
    """Filtering only the sample side after the pairs are made would mis-pair them."""
    from emit.test_branches import _built as branched

    guard = next(s.guard for s in branched(["read_length"]).steps if s.guard is not None)
    pipeline = _built(tmp_path)
    steps = [s.model_copy(update={"guard": guard}) if s.id == "profile" else s
             for s in pipeline.steps]
    with pytest.raises(ValueError, match="MD0348"):
        emit(pipeline.model_copy(update={"steps": steps}))


def test_a_rows_fact_is_no_samplesheet_column(tmp_path):
    pipeline = _built(tmp_path, extra={"profile.contract.yml": SHORT_ONLY})
    assert pipeline.sheet_facts == []

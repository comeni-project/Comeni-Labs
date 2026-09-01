"""Two sample-scoped channels make `params.input` a table, and a row ties them together.

Plan 5B phases 5.1 and 5.4.

**Why a table and not two globs.** Two `fromFilePairs` calls zip by *position*, so nothing ties
a sample's reads to its own annotation — the pipeline runs, pairs sample 1's reads with sample
3's GTF, and produces a counts matrix nobody can tell is wrong. A row is what makes *reads with
their respective annotations* expressible at all.

**Mendel never reads one** (invariant 15, spec §2.3). It emits a pipeline that *references*
`params.input`; it never receives a samplesheet, never parses one, and never learns a sample
identifier. *"Handle batch inputs"* could be read as *"let me upload a samplesheet"*, and that
reading is the one thing this must never become.
"""

import pathlib
import shutil
import subprocess

import pytest
from comeni_core.artifact.pipeline import Pipeline
from comeni_core.plan.draft import DraftChannel, DraftEdge, DraftGraph, DraftNode
from comeni_core.plan.tiers import InputForm
from mendel_compiler import staging
from mendel_compiler.emit import emit
from mendel_resolver import layers
from mendel_resolver.materialise import goal_of, ir_of

ROOT = pathlib.Path(__file__).parent.parent

STAR = "nf-core/star/align@1.11.0"
COUNTS = "nf-core/subread/featurecounts@2.0.6"


@pytest.fixture(scope="module")
def stack():
    return layers.load(ROOT / "registry")


def _two_sample_channels() -> DraftGraph:
    """STAR's GTF moved to per-sample, so the pipeline takes reads *and* annotations per
    sample — which is exactly the operator's *"a list of reads with their respective
    annotations"*."""
    return DraftGraph(
        nodes=[
            DraftNode(id="align", contract_id=STAR),
            DraftNode(id="counts", contract_id=COUNTS),
        ],
        edges=[DraftEdge(from_node="align", from_port="bam", to_node="counts", to_port="bam")],
        channels=[
            DraftChannel(
                ports=("align.gtf",),
                scope="sample",
                why="each biopsy has its own liver-specific annotation",
            )
        ],
    )


def _built(graph: DraftGraph, stack) -> Pipeline:
    return Pipeline.of(
        ir_of(graph, stack), stack.registry, stack.vocabulary, stack.measurements, stack.paths,
        goal=goal_of(graph, stack),
    )


@pytest.fixture(scope="module")
def table(stack) -> str:
    return emit(_built(_two_sample_channels(), stack))


def test_two_sample_scoped_channels_make_it_a_samplesheet(stack):
    assert _built(_two_sample_channels(), stack).input_form is InputForm.SAMPLESHEET


def test_the_table_is_parsed_once_and_projected(table):
    """**One `splitCsv`, and every sample-scoped channel is a projection of it.**

    That is what keeps a row's values together: they emit in row order from a single source, so
    a process consuming several of them sees one row at a time. Two independent parses would
    reintroduce exactly the alignment problem the table exists to solve.
    """
    assert table.count("splitCsv") == 1
    assert "ch_gtf = ch_samplesheet.map" in table
    assert "ch_reads = ch_samplesheet.map" in table


def test_a_paired_type_reads_two_columns(table):
    """`fastq.reads` declares `sample_columns: 2` — nf-core's `_1`/`_2`, with an empty second
    meaning single-end. **Not derivable**: nothing about the type id says a FASTQ arrives in
    pairs, and `fromFilePairs` says it only about the glob form."""
    assert "file(row.reads_1), file(row.reads_2)" in table
    assert "file(row.gtf)" in table


def test_the_sample_id_comes_from_the_row_and_nowhere_else(table):
    """Invariant 15. Mendel writes `row.sample` into Groovy and never learns what is in it."""
    assert "[id: row.sample]" in table
    for step in ("SRR", "sample_1", "/data/"):
        assert step not in table


def test_a_run_scoped_channel_keeps_its_own_parameter(table):
    """A reference is one file for the whole analysis: it has no column, it keeps its
    `params.<name>`, and phase 4.2's `.first()` still makes it a value channel."""
    line = next(one for one in table.splitlines() if one.strip().startswith("ch_star ="))
    assert "params.star" in line and line.rstrip().endswith(".first()")
    assert "row.star" not in table


def test_the_emitted_groovy_parses(table, tmp_path, stack):
    """**A samplesheet is the most Groovy this emitter has ever written**, and a closure that
    does not parse fails at launch with a message about Nextflow rather than about Mendel."""
    if shutil.which("nextflow") is None:
        pytest.skip("needs Nextflow")
    (tmp_path / "main.nf").write_text(table)
    staging.stage(_built(_two_sample_channels(), stack), stack.modules, tmp_path)
    done = subprocess.run(
        ["nextflow", "lint", "main.nf"], cwd=tmp_path, capture_output=True, text=True
    )
    assert done.returncode == 0, done.stdout + done.stderr


def test_a_duplicate_sample_id_is_refused_by_the_pipeline(table):
    """Plan 5B §5.4. A sample split across lanes is several rows with one id, and every
    per-sample output would overwrite the last.

    **Refusing is honest and cheap; merging is not.** nf-core's answer is `cat_fastq`, a
    grouping step before anything else — and a step that changes cardinality on its way through
    is exactly what §10.5 says the contract model cannot express. So the pipeline says so and
    names the ids rather than guessing.

    Emitted into the pipeline because that is where the table is: Mendel never reads one, so the
    only place this check can run is the run itself.
    """
    assert "duplicate sample ids" in table
    assert "twice.join" in table
    # The words are split across emitted lines, so the static check names a fragment and
    # `test_the_refusal_actually_fires_and_names_the_id` reads the whole sentence at runtime.
    assert "needs" in table and "Mendel does not emit" in table


@pytest.mark.skipif(shutil.which("nextflow") is None, reason="needs Nextflow")
def test_the_refusal_actually_fires_and_names_the_id(tmp_path):
    """**Running it is what found the bug in it.**

    The first version put the `+` at the *start* of each continuation line. Groovy continues a
    statement when a line **ends** with an operator; a line beginning with `+` is a new
    statement applying unary plus to a string. So the message truncated to *"samplesheet has
    duplicate sample ids: "* — the words before the first break, with **no ids at all**.

    `nextflow lint` passed it, because it is valid Groovy that means something else. Only a run
    could tell, which is the same lesson `-stub-run` teaches about hollow inputs: syntax is not
    behaviour.
    """
    from mendel_compiler.emit import _no_duplicate_ids

    (tmp_path / "main.nf").write_text(
        "nextflow.enable.dsl = 2\n\nworkflow {\n"
        "    ch = Channel.fromPath(params.input, checkIfExists: true)"
        f".splitCsv(header: true){_no_duplicate_ids()}\n"
        "    ch.map { row -> row.sample }.view()\n}\n"
    )
    (tmp_path / "dup.csv").write_text("sample,x\nA,1\nA,2\n")
    (tmp_path / "ok.csv").write_text("sample,x\nA,1\nB,2\n")

    refused = subprocess.run(
        ["nextflow", "run", "main.nf", "--input", "dup.csv"],
        cwd=tmp_path, capture_output=True, text=True,
    )
    said = refused.stdout + refused.stderr
    assert "duplicate sample ids: A." in said, (
        f"the refusal did not name the id — the message truncated:\n{said}"
    )
    assert "needs merging" in said, "the continuation was dropped"

    fine = subprocess.run(
        ["nextflow", "run", "main.nf", "--input", "ok.csv"],
        cwd=tmp_path, capture_output=True, text=True,
    )
    assert "duplicate" not in fine.stdout + fine.stderr
    assert "A" in fine.stdout and "B" in fine.stdout, "a clean table did not get through"


def test_the_spine_is_still_a_glob(stack, tmp_path):
    """**5.1's first bullet, and the regression that would matter most.** One sample-scoped
    channel emits what it always emitted, and `tests/test_counts.py` — the only check
    exercising the v1 criterion — runs that shape."""
    subprocess.run(
        ["uv", "run", "mendel", "build", "--goal", "examples/rnaseq-goal.yml",
         "--registry", "registry", "--out", str(tmp_path / "b")],
        check=True, cwd=ROOT, capture_output=True,
    )
    workflow = (tmp_path / "b" / "main.nf").read_text()
    assert "splitCsv" not in workflow
    assert "fromFilePairs" in workflow


# ── 5.5, the checkpoint ──────────────────────────────────────────────────────────────

GENOME = "nf-core/star/genomegenerate@1.11.0"


def _runnable() -> DraftGraph:
    """A samplesheet pipeline whose every input declares a public example.

    The index is *built* rather than supplied, because `genome.index.star` declares no
    `test_data` — so a graph taking a prebuilt one gets no `test` profile at all, correctly and
    by the emitter's own all-or-nothing rule. That refusal is right, and it is not what this
    checkpoint is about; the first attempt at this test hit it and read as a samplesheet failure.
    """
    return DraftGraph(
        nodes=[
            DraftNode(id="index", contract_id=GENOME),
            DraftNode(id="align", contract_id=STAR),
        ],
        edges=[DraftEdge(from_node="index", from_port="index", to_node="align", to_port="index")],
        channels=[
            DraftChannel(
                ports=("align.gtf",),
                scope="sample",
                why="each biopsy carries its own annotation",
            )
        ],
    )


def test_a_samplesheet_pipeline_gets_a_test_profile(stack):
    """**`--gate test` is the real checkpoint, and `-stub-run` cannot be.** A stub never reads
    its inputs, so a samplesheet column wired to nothing is exactly as green as one wired
    correctly — which is how two modules shipped with hollow references (`NfInput.empty`).

    A config block cannot write a file, so the profile points at `test-samplesheet.csv` and the
    gate materialises it — the same split `stub-data/` already makes, and for the same reason:
    the pipeline stays free of data and of paths to data (invariant 15).
    """
    from mendel_compiler.emit import emit_config

    pipeline = _built(_runnable(), stack)
    assert pipeline.input_form is InputForm.SAMPLESHEET
    config = emit_config(pipeline)
    assert "test {" in config, "every input has test data and the profile was still refused"
    assert 'params.input = "${projectDir}/test-samplesheet.csv"' in config


def test_the_generated_samplesheet_is_one_row_of_pinned_urls(stack):
    """**One row, and two would be a claim this repository cannot back.** A second row needs a
    second sample's URLs and the vocabulary declares one per type; reusing the first would give
    the run two samples with identical data and identical results, which looks like a fan-out
    test and is not one. `test_fan_out.py` runs two *stub* pairs, where a fixture costs nothing.
    """
    from mendel_compiler.emit import test_samplesheet

    rows = test_samplesheet(_built(_runnable(), stack)).splitlines()
    assert len(rows) == 2, f"expected a header and one row, got {rows}"
    assert rows[0].split(",")[0] == "sample"
    assert rows[1].count("https://") == len(rows[0].split(",")) - 1, (
        "a column has no pinned example behind it"
    )
    assert "72a702d346833d5523bc40d032323ea548603b00" in rows[1], "the dataset is not pinned"


@pytest.mark.slow
@pytest.mark.skipif(shutil.which("nextflow") is None, reason="the test gate needs Nextflow")
@pytest.mark.skipif(shutil.which("docker") is None, reason="the test gate runs real tools")
def test_a_samplesheet_pipeline_runs_end_to_end(stack, tmp_path):
    """**The checkpoint.** Real containers, real data, a real BAM — and `STAR_ALIGN` reading its
    FASTQ *and its GTF from the same row*, which is the whole claim of a samplesheet.

    Slow by nature: it downloads a public dataset and builds a STAR index.
    """
    from mendel_compiler import pipeline_file
    from mendel_compiler.emit import emit_config
    from mendel_compiler.gates import materialise_test_samplesheet

    pipeline = _built(_runnable(), stack)
    pipeline_file.write(tmp_path, pipeline)
    (tmp_path / "main.nf").write_text(emit(pipeline))
    (tmp_path / "nextflow.config").write_text(emit_config(pipeline))
    staging.stage(pipeline, stack.modules, tmp_path)
    materialise_test_samplesheet(tmp_path, pipeline)

    done = subprocess.run(
        ["nextflow", "run", "main.nf", "-profile", "test,docker", "--outdir", "results"],
        cwd=tmp_path, capture_output=True, text=True, timeout=1800,
    )
    assert done.returncode == 0, done.stdout[-3000:] + done.stderr[-3000:]

    published = sorted(one.name for one in (tmp_path / "results").rglob("*.bam"))
    assert published, f"the run produced no alignment:\n{done.stdout[-2000:]}"
    # Named for the row's `sample`, which is the only place that name could have come from.
    assert any(name.startswith("test.") for name in published), published

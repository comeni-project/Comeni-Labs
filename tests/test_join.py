"""A92 — two ports in one channel are matched by a declared rule, not by a guess.

The design audit built a `PAIRUP` process with the exact `SUBREAD_FEATURECOUNTS` shape, gave it
two per-sample channels, and got **four** processes for two samples — two of them pairing one
sample's data with another's. Nextflow exited 0. Every static gate passed: conformance has no
check on this, `nextflow lint` saw valid Groovy, `-preview` built the DAG.

`--gate test` is structurally blind to the whole class, because the nf-core RNA-seq test dataset
has one sample and `1 x 1 == 1`. That is why the run at the bottom of this file exists: it is the
only thing in the repository that puts two samples through a two-port process.
"""

import pathlib
import subprocess

import pytest
from comeni_core.artifact.pipeline import CallArg, Pipeline
from comeni_core.spell.routes import Join
from mendel_compiler.emit import _argument
from mendel_resolver import layers
from mendel_resolver.goal import Goal, GoalInput
from mendel_resolver.resolve import resolve

ROOT = pathlib.Path(__file__).parent.parent


@pytest.fixture
def spine() -> Pipeline:
    """The shipped spine, resolved. Its last step is featureCounts, the one two-port call."""
    loaded = layers.load(ROOT / "registry")
    goal = Goal(
        have=[
            GoalInput(type_id="fastq.reads"),
            GoalInput(type_id="annotation.gtf"),
            GoalInput(type_id="genome.fasta"),
        ],
        want=["counts.matrix"],
        constraints={"required_states": {"counts.matrix": ["gene_level"]}},
        profile=loaded.measurements.profile({"read_length": 150, "strandedness": "reverse"}),
    )
    ir = resolve(
        goal,
        loaded.registry,
        loaded.rules,
        loaded.measurements,
        vocabulary=loaded.vocabulary,
    )
    return Pipeline.of(
        ir,
        loaded.registry,
        loaded.vocabulary,
        loaded.measurements,
        loaded.paths,
        goal=goal,
    )


def _featurecounts(spine: Pipeline):
    return next(step for step in spine.steps if "featurecounts" in step.id)


def test_by_sample_emits_join(spine):
    """Per-sample ports match on the meta map rather than multiplying."""
    step = _featurecounts(spine)
    rendered = _argument(spine, step, CallArg(ports=["bam", "annotation"], join=Join.BY_SAMPLE))
    assert ".join(" in rendered
    assert ".combine(" not in rendered


def test_broadcast_emits_combine(spine):
    """One shared reference against every sample is still a cross product, and correctly so."""
    step = _featurecounts(spine)
    rendered = _argument(spine, step, CallArg(ports=["bam", "annotation"], join=Join.BROADCAST))
    assert ".combine(" in rendered
    assert ".join(" not in rendered


def test_the_shipped_spine_declares_broadcast(spine):
    """featureCounts' annotation is one GTF for every sample, and the artifact says so.

    Without this the two tests above pass while the spine carries `join: null` and reaches the
    same `.combine()` by falling through the else branch — green for the wrong reason.
    """
    arg = next(a for a in _featurecounts(spine).call if len(a.ports) > 1)
    assert arg.join is Join.BROADCAST


MODULE = """process PAIRUP {
    input:
    tuple val(meta), path(a), path(b)

    output:
    path "*.paired.txt", emit: paired

    script:
    \"\"\"
    echo "A=${a} B=${b}" > ${a.baseName}__${b.baseName}.paired.txt
    \"\"\"
}
"""

WORKFLOW = """nextflow.enable.dsl = 2
include {{ PAIRUP }} from './pairup.nf'
workflow {{
    ch_a = Channel.fromPath(params.a).map {{ f -> [ [id: f.baseName.split('\\\\.')[0]], f ] }}
    ch_b = Channel.fromPath(params.b).map {{ f -> [ [id: f.baseName.split('\\\\.')[0]], f ] }}
    PAIRUP({expression})
}}
"""


@pytest.mark.slow
@pytest.mark.parametrize(
    "expression,expected",
    [("ch_a.join(ch_b)", 2), ("ch_a.combine(ch_b.map { it[1] })", 4)],
)
def test_two_samples_join_pairwise_and_combine_cross_products(tmp_path, expression, expected):
    """Two samples in. `join` gives two analyses; `combine` gives four, and two are wrong.

    The `combine` half is not a bug being asserted. It is the evidence that the two branches
    genuinely differ, so a future change collapsing them back into one fails here rather than
    in a laboratory. Audit A92.
    """
    for name in ("s1.a", "s1.b", "s2.a", "s2.b"):
        (tmp_path / f"{name}.tsv").write_text(f"{name}\n")
    (tmp_path / "pairup.nf").write_text(MODULE)
    (tmp_path / "main.nf").write_text(WORKFLOW.format(expression=expression))

    subprocess.run(
        [
            "nextflow",
            "run",
            "main.nf",
            "--a",
            str(tmp_path / "*.a.tsv"),
            "--b",
            str(tmp_path / "*.b.tsv"),
        ],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        text=True,
    )

    produced = sorted(p.name for p in tmp_path.glob("work/*/*/*.paired.txt"))
    assert len(produced) == expected, produced
    if expected == 2:
        assert produced == ["s1.a__s1.b.paired.txt", "s2.a__s2.b.paired.txt"]
    else:
        assert "s1.a__s2.b.paired.txt" in produced

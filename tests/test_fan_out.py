"""Every sample reaches every step, and one reference does not cap the run.

Plan 5B phase 4.2. **This was a live bug in what this repository emitted**, and the reason it
survived is worth more than the fix.

A Nextflow process with several **queue** inputs runs as many times as the *shortest* one. Every
entry channel was a queue, so a reference genome — one item — capped a whole run: with
twenty-four samples `STAR_ALIGN` ran **once** and twenty-three were silently dropped. No error,
no warning, a green gate, and a counts matrix for one sample.

**Nobody saw it because the stub fixture globbed one sample pair.** With N = 1 the shortest
channel is every channel, so the defect is invisible to the only end-to-end test that runs a
tool. `materialise_stub_data` writes two pairs now, which is the smallest fixture that can tell
a value channel from a queue of one.

**A determinism test over the spine passes either way**, which is why this is a run and not an
assertion about emitted text: that shape — a guard green on the code it was written to reject —
is one this repository has already paid for twice (`docs/notes/audits/guard-ledger.md`).
"""

import pathlib
import re
import shutil
import subprocess

import pytest

ROOT = pathlib.Path(__file__).parent.parent

pytestmark = [
    pytest.mark.slow,
    pytest.mark.skipif(shutil.which("nextflow") is None, reason="the stub gate needs Nextflow"),
    pytest.mark.skipif(shutil.which("docker") is None, reason="nf-core 4.x stubs still eval()"),
]

SAMPLES = ("sampleA", "sampleB")


def _ran(log: pathlib.Path, process: str) -> set[str]:
    """Which samples a process actually ran on, read out of Nextflow's own log.

    Nextflow tags each task with the `meta.id` its inputs carried, so the log says *which*
    samples were processed rather than only how many tasks there were — and which is the
    question: dropping sampleA and running sampleB twice would satisfy a count.
    """
    found = re.findall(rf"{process} \(([^)]+)\)", log.read_text())
    return set(found)


@pytest.fixture(scope="module")
def spine(tmp_path_factory):
    out = tmp_path_factory.mktemp("fan-out")
    subprocess.run(
        ["uv", "run", "mendel", "build", "--goal", "examples/rnaseq-goal.yml",
         "--registry", "registry", "--out", str(out), "--gate", "stub"],
        check=True, cwd=ROOT, capture_output=True,
    )
    return out


def test_the_fixture_really_has_two_samples(spine):
    """The guard-of-the-guard. Every assertion below is vacuous with one sample — which is
    exactly the state this test was written to end."""
    pairs = sorted((spine / "stub-data").glob("*_R1.fastq.gz"))
    assert len(pairs) == 2, f"expected two sample pairs, found {[p.name for p in pairs]}"


def test_a_per_sample_step_runs_on_every_sample(spine):
    """TRIMGALORE takes one queue input and was never affected — the control."""
    assert _ran(spine / ".nextflow.log", "TRIMGALORE") == set(SAMPLES)


def test_a_step_behind_a_reference_runs_on_every_sample_too(spine):
    """**The bug.** `STAR_ALIGN` takes reads, an index and an annotation. Two of those are one
    file for the whole run, and as queues they capped the process at one invocation.

    Watched failing against today's emitter — `_as_value` returning the expression unchanged —
    which produced `STAR_ALIGN (sampleB)` and nothing for sampleA, with `gate stub: PASS`.
    """
    ran = _ran(spine / ".nextflow.log", "STAR_ALIGN")
    assert ran == set(SAMPLES), (
        f"STAR_ALIGN ran on {sorted(ran)} of {list(SAMPLES)}. A process with several queue "
        f"inputs runs as many times as the shortest, so a one-item reference channel caps the "
        f"run — and every sample after the first is dropped with no error at all."
    )


def test_every_declared_step_reached_every_sample(spine):
    """The general form, so a step added later is covered without a new test.

    Any process the emitted workflow calls with a per-sample input has to see both samples;
    `STAR_GENOMEGENERATE` legitimately runs once, so the assertion is over the steps that
    consume `TRIMGALORE.out.reads` downstream rather than over all of them.
    """
    log = (spine / ".nextflow.log").read_text()
    per_sample = {
        process
        for process in re.findall(r"\b([A-Z][A-Z0-9_]+) \(sample[AB]\)", log)
    }
    assert per_sample, "no per-sample process ran at all — the run did not do what it says"
    for process in sorted(per_sample):
        assert _ran(spine / ".nextflow.log", process) == set(SAMPLES), (
            f"{process} ran on some samples and not others"
        )


def test_a_run_scoped_channel_is_emitted_as_a_value_channel(spine):
    """The mechanism, so a failure above points at a line rather than at a symptom.

    `.first()` rather than `.collect()`: `first()` takes the one item and makes it a *value*
    channel, consumable any number of times. `collect()` gathers a whole channel into a single
    list item, which is fan-in — a different question, and `InputPort.cardinality`'s.
    """
    workflow = (spine / "main.nf").read_text()
    for name in ("ch_gtf", "ch_fasta"):
        line = next(one for one in workflow.splitlines() if one.strip().startswith(f"{name} ="))
        assert line.rstrip().endswith(".first()"), f"{name} is still a queue: {line.strip()}"

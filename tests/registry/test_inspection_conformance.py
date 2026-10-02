"""Every fixture case reproduces its golden report byte for byte (spec §4).

The goldens are the contract a faster implementation must meet: run the same cases against its
command with `harness.run_case(case, command=[...])`.
"""

import gzip
import random
import time

import pytest
from comeni_inspect import harness, run, wire
from support.paths import ROOT

CASES = harness.cases(ROOT / "registry")


def test_there_are_cases():
    assert CASES, "no fixture cases: the parametrised tests below would assert nothing"


@pytest.mark.parametrize("case", CASES, ids=lambda c: c.name)
def test_a_case_matches_its_golden_report(case):
    assert harness.run_case(case) == (case.folder / "expected.json").read_text().strip()


@pytest.mark.parametrize("case", CASES, ids=lambda c: c.name)
def test_a_case_never_raises(case):
    assert wire.Report.model_validate_json(harness.run_case(case))


def test_the_process_gives_the_same_report_as_in_process():
    """The command path of the harness, against the shipped runner: what another language's
    implementation will be held to."""
    case = next(c for c in CASES if c.name == "fastq/pair_150")
    assert harness.run_case(case, command=["uv", "run", "comeni-inspect"]) == harness.run_case(
        case
    )


def test_the_speed_budget():
    """A 4 MB gzipped FASTQ head in under a second (spec §4): says when Python stops being
    enough."""
    rng = random.Random(134)
    lines = []
    for n in range(40_000):
        seq = "".join(rng.choice("ACGT") for _ in range(150))
        lines.append(f"@r{n}/1\n{seq}\n+\n{'I' * 150}\n")
    raw = gzip.compress("".join(lines).encode())[: 4 * 2**20]
    request, payloads = harness.request_for_bytes(ROOT / "registry", "x_R1.fq.gz", raw)
    start = time.perf_counter()
    report = run.inspect(request, payloads)
    elapsed = time.perf_counter() - start
    assert report.unreadable is None
    assert elapsed < 1.0, f"{elapsed:.2f}s for a 4 MB head"

"""Require every inspection fixture to reproduce its golden report byte for byte.

An alternative implementation can run the same cases through
``harness.run_case(case, command=[...])`` and must produce identical reports.
"""

import gzip
import random
import time
import zlib

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


def test_truncated_gzip_reports_every_complete_record_in_the_available_bytes():
    case = next(c for c in CASES if c.name == "fastq/truncated_gzip")
    raw = (case.folder / "t.fq.gz").read_bytes()
    decoded = zlib.decompressobj(16 + zlib.MAX_WBITS).decompress(raw)
    lines = decoded.splitlines(keepends=True)
    complete = [
        lines[i : i + 4] for i in range(0, len(lines) - 3, 4) if lines[i + 3].endswith(b"\n")
    ]
    assert len(complete) == 998
    assert all(
        head.startswith(b"@")
        and plus.startswith(b"+")
        and len(sequence.rstrip(b"\r\n")) == len(quality.rstrip(b"\r\n"))
        for head, sequence, plus, quality in complete
    )
    report = wire.Report.model_validate_json(harness.run_case(case))
    assert report.unreadable is None and report.facts
    assert all(fact.evidence["rows"] == len(complete) for fact in report.facts.values())


def test_the_process_gives_the_same_report_as_in_process():
    """The command path of the harness, against the shipped runner: what another language's
    implementation will be held to."""
    case = next(c for c in CASES if c.name == "fastq/pair_150")
    assert harness.run_case(case, command=["uv", "run", "comeni-inspect"]) == harness.run_case(case)


def test_the_speed_budget():
    """Process a genuinely truncated 4 MB compressed head within the performance budget."""
    rng = random.Random(134)
    bases = bytes.maketrans(bytes(range(256)), b"ACGT" * 64)
    quals = bytes.maketrans(bytes(range(256)), bytes(range(35, 75)) * 6 + bytes(range(35, 51)))
    reads = b"".join(
        b"@r%d/1\n%s\n+\n%s\n"
        % (n, rng.randbytes(150).translate(bases), rng.randbytes(150).translate(quals))
        for n in range(30_000)
    )
    whole = gzip.compress(reads)
    assert len(whole) > 4 * 2**20, "the head must be cut, or this measures less than a head"
    raw = whole[: 4 * 2**20]
    request, payloads = harness.request_for_bytes(ROOT / "registry", "x_R1.fq.gz", raw)
    start = time.perf_counter()
    report = run.inspect(request, payloads)
    elapsed = time.perf_counter() - start
    assert report.unreadable is None
    assert report.facts["read_length"].value == 150
    assert elapsed < 1.0, f"{elapsed:.2f}s for a 4 MB head"

"""Inspecting a sample: the right pieces, hard limits, and every failure an answer (spec §7-§8)."""

import gzip
import subprocess
import sys
from pathlib import Path

from mendel_api.services import inspect, registry

ROOT = Path(__file__).resolve().parents[3]

FIX = ROOT / "registry/inspectors/formats/fastq/piece/fixtures"


def _files(case):
    return [
        (p.name, p.read_bytes())
        for p in sorted((FIX / case).iterdir())
        if p.name != "expected.json"
    ]


def test_a_gzipped_pair_is_measured():
    got = inspect.inspect_sample(_files("pair_150"), registry.stack())
    assert got.outcome == "measured" and got.type_id == "fastq.reads"
    facts = {f.measurement: f for f in got.facts}
    assert facts["paired"].value is True and facts["read_length"].value == 150
    assert facts["read_length"].pieces == ["fastq@1.1.0", "read_length@1.0.0"]
    assert facts["read_length"].evidence["records"] == 4000


def test_an_undetermined_fact_is_returned_with_its_reason():
    got = inspect.inspect_sample(_files("trimmed"), registry.stack())
    fact = next(f for f in got.facts if f.measurement == "read_length")
    assert fact.value is None and fact.undetermined.startswith("lengths vary")


def test_an_unknown_extension_has_no_inspector():
    got = inspect.inspect_sample([("reads.bam", b"BAM\x01")], registry.stack())
    assert got.outcome == "no_inspector" and "nothing reads" in got.reason


def test_files_of_two_kinds_have_no_inspector():
    got = inspect.inspect_sample([("a.fq", b"@r\nA\n+\nI\n"), ("b.bam", b"BAM")], registry.stack())
    assert got.outcome == "no_inspector"


def test_more_files_than_the_format_reads_are_unreadable_and_never_launched(monkeypatch):
    """Issue 224: a format's `files: 1..2` was never enforced, and `paired` read three-file rows
    as single files. Refused before a process is started."""
    launched = []
    monkeypatch.setattr(inspect, "launch", lambda *a: launched.append(a))
    three = [(f"s_{n}.fq", b"@r\nACGT\n+\nIIII\n") for n in (1, 2, 3)]
    got = inspect.inspect_sample(three, registry.stack())
    assert got.outcome == "unreadable" and "1 to 2 files" in got.reason
    assert launched == []


def test_fasta_named_fastq_is_unreadable_with_why():
    got = inspect.inspect_sample(_files("fasta_named_fastq"), registry.stack())
    assert got.outcome == "unreadable" and "does not start like" in got.reason


MARKER = "comeni-inspect-hang-test-7c1f"


def test_a_hang_is_unreadable_and_the_process_is_gone(monkeypatch):
    """Review focus 5: the runner left behind after a timeout is killed, never orphaned."""
    monkeypatch.setattr(inspect, "TIMEOUT_S", 0.5)
    monkeypatch.setattr(
        inspect, "_command",
        lambda: [sys.executable, "-c", f"import time; time.sleep(30)  # {MARKER}"],
    )
    got = inspect.inspect_sample(_files("few"), registry.stack())
    assert got.outcome == "unreadable" and got.reason == "took too long"
    left = subprocess.run(["pgrep", "-f", MARKER], capture_output=True, text=True).stdout
    assert left.strip() == "", f"the runner was left behind: {left}"


def test_a_crash_is_unreadable(monkeypatch):
    monkeypatch.setattr(inspect, "_command", lambda: [sys.executable, "-c", "raise SystemExit(3)"])
    got = inspect.inspect_sample(_files("few"), registry.stack())
    assert got.outcome == "unreadable" and "stopped" in got.reason


def test_a_report_nobody_can_read_is_unreadable(monkeypatch):
    monkeypatch.setattr(inspect, "_command", lambda: [sys.executable, "-c", "print('{not json')"])
    got = inspect.inspect_sample(_files("few"), registry.stack())
    assert got.outcome == "unreadable" and "could not be read" in got.reason


def test_a_bomb_is_unreadable():
    bomb = gzip.compress(b"@r\n" + b"A" * (64 * 2**20))
    got = inspect.inspect_sample([("b.fq.gz", bomb[: inspect.HEAD_BYTES])], registry.stack())
    assert got.outcome == "unreadable" and got.reason == "too large unpacked"


def test_a_piece_from_an_untrusted_layer_never_runs(monkeypatch):
    from mendel_api.settings import settings

    monkeypatch.setattr(settings, "trusted_layers", [])
    got = inspect.inspect_sample(_files("few"), registry.stack())
    assert got.outcome == "no_inspector"


def test_the_steps_taken_are_returned():
    got = inspect.inspect_sample(_files("pair_150"), registry.stack())
    assert got.steps[0] == "read the first 4 MB of 2 file(s)"
    assert "unpacked gzip" in got.steps and "confirmed FASTQ" in got.steps
    assert got.steps[-1].startswith("measured ")


def test_the_child_gets_no_secrets_and_no_preexec(monkeypatch):
    """Review of #134: the child ran with the API's whole environment (database URL, model keys,
    WIENER_API_TOKEN), and `preexec_fn` is unsafe from the thread pool the route calls it from."""
    seen = {}
    real = inspect.subprocess.run

    def spy(command, **kwargs):
        seen.update(kwargs, command=command)
        return real(command, **kwargs)

    monkeypatch.setenv("WIENER_API_TOKEN", "secret-token")
    monkeypatch.setattr(inspect.subprocess, "run", spy)
    got = inspect.inspect_sample(_files("few"), registry.stack())
    assert got.outcome == "measured"
    assert "preexec_fn" not in seen
    assert "WIENER_API_TOKEN" not in seen["env"] and set(seen["env"]) <= {"PATH", "LANG", "LC_ALL"}
    assert "--memory-bytes" in seen["command"]

"""The pipeline runner: whole files, no cap, the same pieces as the server (#465)."""

import json
import subprocess
import sys
import textwrap
from pathlib import Path

from comeni_inspect import run
from comeni_inspect_tests import COUNT, FORMAT, _request

PARSER = textwrap.dedent("""
    from comeni_inspect.outcome import Undetermined, Value

    def parse(stream, decided):
        total = 0
        for line in stream:
            total += int(line.split(b"\\t")[1])
        if total == 0:
            return Undetermined(reason="no sequences", evidence={})
        return Value(value=total, evidence={"sequences": 1})
""")


def _cli(*args) -> tuple[dict, int]:
    done = subprocess.run([sys.executable, "-m", "comeni_inspect.measure_cli", *args],
                          capture_output=True, text=True)
    return json.loads(done.stdout), done.returncode


def test_cli_matches_server(tmp_path):
    request, payloads = _request(tmp_path, size=3000, cap=2**20)
    server = run.inspect(request, payloads).facts["count"]
    data = tmp_path / "a.fa"
    data.write_bytes(payloads[0])
    report, status = _cli(
        "--format", f"toy@1.0.0={tmp_path / 'fmt.py'}",
        "--measure", f"count@1.0.0={tmp_path / 'count.py'}", "--decided", "count={}",
        str(data),
    )
    assert status == 0
    fact = report["facts"]["count"]
    assert fact["value"] == server.value
    assert fact["evidence"] == server.evidence
    assert fact["coverage"] == "all"
    assert fact["by"] == ["toy@1.0.0", "count@1.0.0"]


def test_cli_reads_past_any_cap(tmp_path):
    """Far more than the server's head: nothing caps the pipeline's read."""
    (tmp_path / "fmt.py").write_text(FORMAT)
    (tmp_path / "count.py").write_text(COUNT)
    data = tmp_path / "big.fa"
    with data.open("wb") as out:
        for i in range(2_000_000):
            out.write(b">r%d\n" % i)
    report, _ = _cli("--format", f"toy@1.0.0={tmp_path / 'fmt.py'}",
                     "--measure", f"count@1.0.0={tmp_path / 'count.py'}", str(data))
    assert report["facts"]["count"]["value"] == 2_000_000
    assert "capped" not in report["facts"]["count"]["evidence"]


def test_parser_mode(tmp_path):
    (tmp_path / "fai.py").write_text(PARSER)
    fai = tmp_path / "genome.fa.fai"
    fai.write_bytes(b"MN908947.3\t29903\t12\t70\t71\n")
    report, status = _cli("--parser", f"genome_length_fai@1.0.0={tmp_path / 'fai.py'}",
                          str(fai))
    assert status == 0
    fact = report["facts"]["genome_length_fai"]
    assert fact["value"] == 29903
    assert fact["coverage"] == "all"
    assert fact["by"] == ["genome_length_fai@1.0.0"]


def test_parser_undetermined(tmp_path):
    (tmp_path / "fai.py").write_text(PARSER)
    fai = tmp_path / "empty.fai"
    fai.write_bytes(b"")
    report, _ = _cli("--parser", f"g@1.0.0={tmp_path / 'fai.py'}", str(fai))
    assert report["facts"]["g"]["undetermined"] == "no sequences"


def test_parser_that_raises_is_unreadable(tmp_path):
    (tmp_path / "bad.py").write_text("def parse(stream, decided):\n    raise RuntimeError('x')\n")
    fai = tmp_path / "x.fai"
    fai.write_bytes(b"x\n")
    report, status = _cli("--parser", f"bad@1.0.0={tmp_path / 'bad.py'}", str(fai))
    assert status == 0
    assert report["unreadable"] == "bad failed: RuntimeError"


def test_broken_arguments_are_a_report(tmp_path):
    report, status = _cli("--parser", "no-equals-sign", str(tmp_path / "x"))
    assert status == 0
    assert report["unreadable"].startswith("broken request")


def test_runs_as_a_staged_script_in_isolated_mode(tmp_path):
    """How a pipeline step runs it: the stdlib modules copied beside each other, `python3 -I`,
    so no installed package and no PYTHONPATH is involved. `-S` keeps site-packages off the
    path here too, so the test cannot pass on the installed copy."""
    import shutil

    import comeni_inspect

    package = tmp_path / "runner" / "comeni_inspect"
    package.mkdir(parents=True)
    source = Path(comeni_inspect.__file__).parent
    for name in ("__init__.py", "core.py", "outcome.py", "records.py", "stream.py",
                 "measure_cli.py"):
        shutil.copy(source / name, package / name)
    (tmp_path / "fai.py").write_text(PARSER)
    fai = tmp_path / "g.fai"
    fai.write_bytes(b"a\t10\nb\t5\n")
    done = subprocess.run(
        [sys.executable, "-I", "-S", str(package / "measure_cli.py"),
         "--parser", f"g@1.0.0={tmp_path / 'fai.py'}", str(fai)],
        capture_output=True, text=True, cwd=tmp_path, env={},
    )
    assert json.loads(done.stdout)["facts"]["g"]["value"] == 15, done.stderr


def test_a_fact_is_keyed_by_the_measurement_it_is(tmp_path):
    """What a pipeline reads: `facts.genome_length`, whoever measured it (#217)."""
    (tmp_path / "fai.py").write_text(PARSER)
    fai = tmp_path / "g.fai"
    fai.write_bytes(b"a\t10\n")
    report, _ = _cli("--parser", f"genome_length_fai@1.0.0={tmp_path / 'fai.py'}",
                     "--as", "genome_length_fai=genome_length", str(fai))
    assert list(report["facts"]) == ["genome_length"]
    assert report["facts"]["genome_length"]["by"] == ["genome_length_fai@1.0.0"]

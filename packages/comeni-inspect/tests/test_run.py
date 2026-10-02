# packages/comeni-inspect/tests/test_run.py
"""The runner over toy pieces: composition, one pass, every outcome a report."""

import gzip
import textwrap

from comeni_inspect import run, wire

FORMAT = textwrap.dedent("""
    from comeni_inspect.records import SequenceRecord

    def confirms(first):
        return first.startswith(b">")

    def records(stream):
        for line in stream:
            line = line.rstrip(b"\\r\\n")
            if line.startswith(b">"):
                yield SequenceRecord(name=line[1:].decode(), sequence=b"", quality=None)
""")
COUNT = textwrap.dedent("""
    from comeni_inspect.outcome import Undetermined, Value

    class Accumulator:
        def __init__(self, decided, files):
            self.n, self.need = 0, decided["min_records"]
        def add(self, row):
            self.n += len(row)
        def result(self):
            if self.n < self.need:
                return Undetermined(reason=f"only {self.n} records", evidence={"records": self.n})
            return Value(value=self.n, evidence={"records": self.n})
""")
GZIP = "import gzip, io\n\ndef open(raw):\n    return gzip.GzipFile(fileobj=io.BytesIO(raw))\n"


def _request(tmp_path, n=2, codec=False, cap=2**20):
    (tmp_path / "fmt.py").write_text(FORMAT)
    (tmp_path / "count.py").write_text(COUNT)
    (tmp_path / "gz.py").write_text(GZIP)
    return wire.Request(
        format=wire.PieceRef(id="toy", version="1.0.0", path=str(tmp_path / "fmt.py")),
        codec=wire.PieceRef(id="gzip", version="1.0.0", path=str(tmp_path / "gz.py"))
        if codec
        else None,
        measures=[
            wire.PieceRef(
                id="count",
                version="1.0.0",
                path=str(tmp_path / "count.py"),
                decided={"min_records": n},
            )
        ],
        files=[],
        cap_bytes=cap,
    )


def _with(request, *payloads):
    files = [wire.FileHead(name=f"f{i}", length=len(p)) for i, p in enumerate(payloads)]
    return request.model_copy(update={"files": files}), list(payloads)


def test_every_record_reaches_the_measure(tmp_path):
    report = run.inspect(*_with(_request(tmp_path), b">a\n>b\n>c\n"))
    fact = report.facts["count"]
    assert fact.value == 3 and fact.by == ["toy@1.0.0", "count@1.0.0"]


def test_below_the_threshold_is_undetermined(tmp_path):
    report = run.inspect(*_with(_request(tmp_path, n=10), b">a\n"))
    assert report.facts["count"].undetermined == "only 1 records"


def test_content_that_does_not_confirm_is_unreadable(tmp_path):
    report = run.inspect(*_with(_request(tmp_path), b"@a\nACGT\n"))
    assert report.unreadable and "does not start like" in report.unreadable


def test_a_gzip_cut_mid_stream_yields_what_it_can(tmp_path):
    # Varied names, as real reads are: 5,000 identical records compress to 55 bytes, and the
    # first half of that decodes to nothing at all.
    whole = gzip.compress(b"".join(b">r%d\n" % n for n in range(5000)))
    report = run.inspect(*_with(_request(tmp_path, codec=True), whole[: len(whole) // 2]))
    assert report.unreadable is None and report.facts["count"].value > 0


def test_a_bomb_is_unreadable_not_a_crash(tmp_path):
    bomb = gzip.compress(b">" + b"A" * (8 * 2**20))
    report = run.inspect(*_with(_request(tmp_path, codec=True, cap=2**20), bomb))
    assert report.unreadable == "too large unpacked"


def test_a_piece_that_raises_is_unreadable(tmp_path):
    request = _request(tmp_path)
    (tmp_path / "count.py").write_text(
        "class Accumulator:\n    def __init__(self, d, f): raise RuntimeError('boom')\n"
    )
    report = run.inspect(*_with(request, b">a\n"))
    assert report.unreadable and "count" in report.unreadable


def test_a_short_second_file_stops_at_the_shorter_and_says_how_many_rows(tmp_path):
    """Review focus 1: an R2 cut short by the head is read side by side up to its end."""
    report = run.inspect(*_with(_request(tmp_path), b">a\n>b\n>c\n", b">a\n"))
    fact = report.facts["count"]
    assert fact.value == 2 and fact.evidence["rows"] == 1
    assert fact.evidence["shorter_file"] == "f1"


def test_files_of_equal_length_name_no_shorter_file(tmp_path):
    report = run.inspect(*_with(_request(tmp_path), b">a\n", b">a\n"))
    assert "shorter_file" not in report.facts["count"].evidence


def test_the_process_answers_a_broken_request_with_a_report():
    """Through the real entry point: exit 0 and a report, whatever came in on stdin."""
    import subprocess
    import sys

    done = subprocess.run(
        [sys.executable, "-m", "comeni_inspect.run"], input=b"not json\n", capture_output=True
    )
    assert done.returncode == 0
    assert wire.Report.model_validate_json(done.stdout).unreadable.startswith("broken request")


def test_an_inspection_writes_no_bytecode_beside_the_pieces(tmp_path):
    """The pieces live in a registry layer whose digest a pipeline pins."""
    run.inspect(*_with(_request(tmp_path), b">a\n"))
    assert not list(tmp_path.rglob("__pycache__"))


def _measure_returning(tmp_path, body: str):
    request = _request(tmp_path)
    (tmp_path / "count.py").write_text(
        "from comeni_inspect.outcome import Value\n"
        "class Accumulator:\n"
        "    def __init__(self, d, f): pass\n"
        "    def add(self, row): pass\n"
        f"    def result(self): {body}\n"
    )
    return run.inspect(*_with(request, b">a\n"))


import pytest  # noqa: E402


@pytest.mark.parametrize(
    "body",
    [
        "return None",
        "return Value(value=[1], evidence={})",
        "return Value(value=1, evidence={'raw': b'x'})",
        "return Value(value=float('nan'), evidence={})",
        "raise SystemExit(3)",
    ],
)
def test_a_measure_answering_badly_is_unreadable_not_a_crash(tmp_path, body):
    """Review of #134: what `result()` returns was used outside the guard."""
    report = _measure_returning(tmp_path, body)
    assert report.unreadable and "count" in report.unreadable
    report.to_json()


def test_a_codec_that_returns_no_stream_is_unreadable(tmp_path):
    request = _request(tmp_path, codec=True)
    (tmp_path / "gz.py").write_text("def open(raw):\n    return raw\n")
    report = run.inspect(*_with(request, b">a\n"))
    assert report.unreadable and "gzip" in report.unreadable


def test_more_payloads_than_files_is_unreadable(tmp_path):
    request, payloads = _with(_request(tmp_path), b">a\n")
    report = run.inspect(request, [*payloads, b">b\n"])
    assert report.unreadable


def test_the_format_is_shown_a_full_window_even_through_a_codec(tmp_path):
    """`peek` is one raw read and may return less than asked; the window is read whole."""
    request = _request(tmp_path, codec=True)
    (tmp_path / "fmt.py").write_text(
        "def confirms(first):\n    return len(first) == 4096\n"
        "def records(stream):\n    return iter(())\n"
    )
    (tmp_path / "gz.py").write_text(
        "import io\nclass Slow(io.RawIOBase):\n"
        "    def __init__(self, raw): self.raw = io.BytesIO(raw)\n"
        "    def readable(self): return True\n"
        "    def readinto(self, b):\n"
        "        data = self.raw.read(min(len(b), 100)); b[:len(data)] = data; return len(data)\n"
        "def open(raw):\n    return Slow(raw)\n"
    )
    report = run.inspect(*_with(request, b">" * 10_000))
    assert report.unreadable is None


def test_a_head_that_unpacks_past_the_cap_is_measured_up_to_it(tmp_path):
    """Issue 221: an ordinary gzipped head unpacks 4-6x, past the cap. Reaching the cap is the
    end of the head, said in the evidence, not a refusal."""
    import random

    rng = random.Random(221)
    raw = gzip.compress(
        b"".join(
            b">r%d %s\n" % (n, bytes(rng.choice(b"ACGT") for _ in range(40))) for n in range(40_000)
        )
    )
    report = run.inspect(*_with(_request(tmp_path, codec=True, cap=2**20), raw))
    assert report.unreadable is None
    fact = report.facts["count"]
    assert fact.value > 0 and fact.evidence["capped"] is True


def test_a_head_inside_the_cap_is_not_marked_capped(tmp_path):
    report = run.inspect(*_with(_request(tmp_path), b">a\n>b\n"))
    assert "capped" not in report.facts["count"].evidence

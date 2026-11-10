"""The inspection core runs on the standard library alone, so a pipeline step can run it on a
plain Python image; and every fact says how much of the data it read (#465)."""

import subprocess
import sys
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
    from comeni_inspect.outcome import Value

    class Accumulator:
        def __init__(self, decided, files):
            self.n = 0
        def add(self, row):
            self.n += len(row)
        def result(self):
            return Value(value=self.n, evidence={"records": self.n})
""")


def _request(tmp_path, size: int, cap: int, whole: bool = True) -> tuple[wire.Request, list[bytes]]:
    (tmp_path / "fmt.py").write_text(FORMAT)
    (tmp_path / "count.py").write_text(COUNT)
    payload = b"".join(b">r%d\n" % i for i in range(size))
    request = wire.Request(
        format=wire.PieceRef(id="toy", version="1.0.0", path=str(tmp_path / "fmt.py")),
        codec=None,
        measures=[wire.PieceRef(id="count", version="1.0.0", path=str(tmp_path / "count.py"))],
        files=[wire.FileHead(name="a.fa", length=len(payload), whole=whole)],
        cap_bytes=cap,
    )
    return request, [payload]


def test_core_imports_only_stdlib():
    probe = (
        "import sys; import comeni_inspect.core, comeni_inspect.measure_cli; "
        "print(sorted(m for m in sys.modules if m.split('.')[0] in {'pydantic', 'yaml'}))"
    )
    done = subprocess.run([sys.executable, "-c", probe], capture_output=True, text=True,
                          check=True)
    assert done.stdout.strip() == "[]"


def test_coverage_all_when_uncapped(tmp_path):
    report = run.inspect(*_request(tmp_path, size=50, cap=2**20))
    assert report.facts["count"].value == 50
    assert report.facts["count"].coverage == "all"


def test_coverage_head_when_capped(tmp_path):
    report = run.inspect(*_request(tmp_path, size=5000, cap=8192))
    assert report.facts["count"].coverage == "head"
    assert report.facts["count"].evidence["capped"] is True


def test_a_head_is_not_all_of_the_file(tmp_path):
    """The browser sends the first 4 MB; reaching its end is not reaching the file's."""
    report = run.inspect(*_request(tmp_path, size=50, cap=2**20, whole=False))
    assert report.facts["count"].coverage == "head"
    assert "capped" not in report.facts["count"].evidence

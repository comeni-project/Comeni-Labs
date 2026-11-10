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
    """Every module it loads is the standard library's or one of the runner's own: nothing from
    site-packages, and none of this package's pydantic modules."""
    probe = (
        "import sys, sysconfig; before = set(sys.modules); "
        "import comeni_inspect.core, comeni_inspect.measure_cli; "
        "site = sysconfig.get_paths()['purelib']; "
        "ours = sorted(m for m in sys.modules if m.startswith('comeni_inspect')); "
        "third = sorted(m for m, mod in list(sys.modules.items()) if m not in before "
        "    if (getattr(mod, '__file__', None) or '').startswith(site) "
        "    and not m.startswith('comeni_inspect')); "
        "print(ours); print(third)"
    )
    done = subprocess.run([sys.executable, "-c", probe], capture_output=True, text=True,
                          check=True)
    ours, third = done.stdout.strip().splitlines()
    allowed = {"comeni_inspect", "comeni_inspect.core", "comeni_inspect.measure_cli",
               "comeni_inspect.outcome", "comeni_inspect.records", "comeni_inspect.stream"}
    assert set(eval(ours)) <= allowed  # noqa: S307 — our own subprocess's repr of a list
    assert eval(third) == []  # noqa: S307


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


def _whole(tmp_path, payload: bytes, codec: bool = False) -> wire.Report:
    (tmp_path / "fmt.py").write_text(FORMAT)
    (tmp_path / "count.py").write_text(COUNT)
    (tmp_path / "gz.py").write_text(
        "import gzip\n\ndef open(stream):\n    return gzip.GzipFile(fileobj=stream)\n")
    request = wire.Request(
        format=wire.PieceRef(id="toy", version="1.0.0", path=str(tmp_path / "fmt.py")),
        codec=wire.PieceRef(id="gzip", version="1.0.0", path=str(tmp_path / "gz.py"))
        if codec else None,
        measures=[wire.PieceRef(id="count", version="1.0.0", path=str(tmp_path / "count.py"))],
        files=[wire.FileHead(name="a.fa.gz", length=len(payload), whole=True)],
        cap_bytes=2**20,
    )
    return run.inspect(request, [payload])


def test_a_whole_gzip_cut_short_is_not_all_of_it(tmp_path):
    """An interrupted copy: the gzip stream ends early. Its facts read part of the data."""
    import gzip

    packed = gzip.compress(b"".join(b">r%d\n" % i for i in range(5000)))
    fact = _whole(tmp_path, packed[: len(packed) // 2], codec=True).facts["count"]
    assert fact.coverage == "head"
    assert fact.evidence["truncated"] is True


def test_a_complete_gzip_is_all_of_it(tmp_path):
    import gzip

    packed = gzip.compress(b"".join(b">r%d\n" % i for i in range(5000)))
    fact = _whole(tmp_path, packed, codec=True).facts["count"]
    assert fact.coverage == "all" and "truncated" not in fact.evidence


def test_a_stop_at_a_malformed_record_is_not_all_of_it(tmp_path):
    (tmp_path / "fmt.py").write_text(textwrap.dedent("""
        from comeni_inspect.records import Malformed, SequenceRecord

        def confirms(first):
            return first.startswith(b">")

        def records(stream):
            for line in stream:
                if line.startswith(b"BAD"):
                    raise Malformed("record 3: bad")
                yield SequenceRecord(name=line[1:].decode(), sequence=b"", quality=None)
    """))
    (tmp_path / "count.py").write_text(COUNT)
    payload = b">a\n>b\nBAD\n>c\n"
    request = wire.Request(
        format=wire.PieceRef(id="toy", version="1.0.0", path=str(tmp_path / "fmt.py")),
        codec=None,
        measures=[wire.PieceRef(id="count", version="1.0.0", path=str(tmp_path / "count.py"))],
        files=[wire.FileHead(name="a.fa", length=len(payload), whole=True)],
        cap_bytes=2**20,
    )
    fact = run.inspect(request, [payload]).facts["count"]
    assert fact.evidence["stopped"].startswith("malformed")
    assert fact.coverage == "head"


def test_a_pair_with_a_shorter_file_is_not_all_of_it(tmp_path):
    """The longer file's tail is never read."""
    (tmp_path / "fmt.py").write_text(FORMAT)
    (tmp_path / "count.py").write_text(COUNT)
    one, two = b">a\n>b\n>c\n", b">a\n"
    request = wire.Request(
        format=wire.PieceRef(id="toy", version="1.0.0", path=str(tmp_path / "fmt.py")),
        codec=None,
        measures=[wire.PieceRef(id="count", version="1.0.0", path=str(tmp_path / "count.py"))],
        files=[wire.FileHead(name="1.fa", length=len(one), whole=True),
               wire.FileHead(name="2.fa", length=len(two), whole=True)],
        cap_bytes=2**20,
    )
    fact = run.inspect(request, [one, two]).facts["count"]
    assert fact.evidence["shorter_file"] == "2.fa" and fact.coverage == "head"

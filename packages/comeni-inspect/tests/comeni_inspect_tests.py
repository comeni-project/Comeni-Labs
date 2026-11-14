"""Toy pieces shared by the runner's tests: a format reading `>name` lines and a measure that
counts them, so the core is exercised without the registry's pieces."""

import textwrap

from comeni_inspect import wire

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

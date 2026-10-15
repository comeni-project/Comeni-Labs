"""The wire protocol: a request in, its bytes after it, one report out (spec §6)."""

import io

from comeni_inspect import wire


def test_a_request_round_trips_with_its_bytes():
    request = wire.Request(
        format=wire.PieceRef(id="fastq", version="1.0.0", path="/x/fastq.py"),
        codec=None,
        measures=[
            wire.PieceRef(
                id="read_length", version="1.0.0", path="/x/rl.py", decided={"min_records": 2}
            )
        ],
        files=[wire.FileHead(name="a_R1.fq", length=3), wire.FileHead(name="a_R2.fq", length=2)],
        cap_bytes=16 * 2**20,
    )
    stream = io.BytesIO()
    wire.write_request(stream, request, [b"abc", b"de"])
    stream.seek(0)
    back, payloads = wire.read_request(stream)
    assert back == request and payloads == [b"abc", b"de"]


def test_a_report_serialises_in_a_stable_order():
    report = wire.Report(
        type_id="fastq.reads",
        facts={
            "read_length": wire.Fact(
                by=["fastq@1.0.0", "read_length@1.0.0"],
                value=151,
                evidence={"records": 9, "share": 1.0},
            ),
            "paired": wire.Fact(
                by=["fastq@1.0.0", "paired@1.0.0"], undetermined="only one file", evidence={}
            ),
        },
    )
    text = report.to_json()
    assert text.index('"paired"') < text.index('"read_length"')
    assert wire.Report.model_validate_json(text) == report


def test_a_payload_shorter_than_declared_is_refused():
    """A request whose bytes stop early is a broken request, never a silently short file."""
    request = wire.Request(
        format=wire.PieceRef(id="fastq", version="1.0.0", path="/x/fastq.py"),
        codec=None,
        measures=[],
        files=[wire.FileHead(name="a.fq", length=10)],
        cap_bytes=1,
    )
    stream = io.BytesIO()
    wire.write_request(stream, request, [b"abc"])
    stream.seek(0)
    try:
        wire.read_request(stream)
    except ValueError as error:
        assert "a.fq" in str(error)
    else:
        raise AssertionError("a short payload was accepted")

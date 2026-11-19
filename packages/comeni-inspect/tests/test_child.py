"""The child's stdlib wire is `wire`'s, byte for byte (#572)."""

import json
import subprocess
import sys

import pytest
from comeni_inspect import child, wire
from pydantic import ValidationError

REF = {"id": "fastq", "version": "1.0.0", "path": "/p/fastq.py"}
REPORTS = [
    {},
    {"type_id": "fastq.reads", "facts": {}},
    {"type_id": None, "unreadable": "too large unpacked", "facts": {}},
    {"facts": {"read_length": {"by": ["fastq@1.0.0", "read_length@1.0.0"], "value": 150,
                               "evidence": {"min": 150, "none": None}, "coverage": "head"}}},
    {"facts": {"paired": {"by": ["a"], "value": True}, "ratio": {"by": ["a"], "value": 0.5}}},
    {"facts": {"q": {"by": ["a"], "undetermined": "no quality line", "value": None}}},
    {"facts": {"bad": {"by": "a"}}},
    {"facts": {"bad": {"by": ["a"], "coverage": "some"}}},
    {"facts": {"bad": {"by": ["a"], "extra": 1}}},
    {"facts": {"bad": {"by": ["a"], "value": [1]}}},
    {"surprise": 1},
]


@pytest.mark.parametrize("report", REPORTS)
def test_the_child_writes_the_report_wire_writes(report):
    try:
        expected = wire.Report.model_validate(report).to_json()
    except ValidationError:
        expected = wire.Report(unreadable="inspection failed: ValidationError").to_json()
    assert child.report_json(report) == expected


REQUESTS = [
    {"format": REF, "codec": None, "measures": [REF], "files": [{"name": "a", "length": 3}],
     "cap_bytes": 10},
    {"format": {**REF, "decided": {"x": 1, "y": 0.5}}, "codec": REF, "measures": [],
     "files": [{"name": "a", "length": 0, "whole": True}], "cap_bytes": 1},
    {"format": REF, "codec": None, "measures": [], "files": [], "cap_bytes": 0},
    {"format": REF, "codec": None, "measures": [], "files": [{"name": "a", "length": -1}],
     "cap_bytes": 5},
    {"format": REF, "codec": None, "measures": [], "files": [], "cap_bytes": 5, "more": 1},
]


def test_the_child_is_stricter_only_where_the_parent_never_writes():
    """Pydantic's lax mode reads `"1"` in `decided` as a number; the child refuses it. The parent
    writes every request through `wire`'s own models (`write_request`), which emit numbers, so
    no request the parent sends reads differently."""
    line = json.dumps({"format": {**REF, "decided": {"x": "1"}}, "codec": None, "measures": [],
                       "files": [], "cap_bytes": 5}).encode()
    wire.Request.model_validate_json(line)
    with pytest.raises(child.ValidationError):
        child.parse_request(line)


@pytest.mark.parametrize("request_", REQUESTS)
def test_the_child_accepts_and_refuses_the_requests_wire_does(request_):
    line = json.dumps(request_).encode()
    try:
        wanted = wire.Request.model_validate_json(line)
    except ValidationError:
        with pytest.raises(child.ValidationError):
            child.parse_request(line)
        return
    got = child.parse_request(line)
    assert (got.cap_bytes, [f.length for f in got.files], got.format.decided) == (
        wanted.cap_bytes, [f.length for f in wanted.files], dict(wanted.format.decided))


def test_the_child_starts_without_pydantic():
    """Most of a child's start-up was importing pydantic for the wire models."""
    loaded = subprocess.run(
        [sys.executable, "-c", "import sys, comeni_inspect.run; print('pydantic' in sys.modules)"],
        capture_output=True, text=True, check=True).stdout.strip()
    assert loaded == "False"


def test_a_broken_request_is_answered_as_before():
    done = subprocess.run([sys.executable, "-m", "comeni_inspect.run"], input=b"not json\n",
                          capture_output=True, check=True)
    assert done.stdout.decode() == wire.Report(
        unreadable="broken request: ValidationError").to_json()

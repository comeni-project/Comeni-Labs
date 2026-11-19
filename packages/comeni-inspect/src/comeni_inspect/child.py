"""The inspection child's side of the wire, in the standard library only (#572).

One child starts per sample per candidate format, and importing pydantic for `wire`'s models was
most of its start-up: about 127 ms of 190, against 34 ms of inspection on a small file. The
parent keeps the pydantic models (`wire`) and validates what it sends and what comes back; the
child reads the request and writes the report with the same strictness and **the same bytes**,
which `test_child.py` holds against `wire` itself.
"""

import json
from typing import BinaryIO, NamedTuple


class ValidationError(ValueError):
    """A request or report that does not have the wire's shape. Named as pydantic's is, because
    the child reports it by name (`broken request: ValidationError`) and those bytes are kept."""


class Ref(NamedTuple):
    id: str
    version: str
    path: str
    decided: dict


class Head(NamedTuple):
    name: str
    length: int
    whole: bool


class Request(NamedTuple):
    format: Ref
    codec: Ref | None
    measures: list[Ref]
    files: list[Head]
    cap_bytes: int


def _fields(data, required: set[str], optional: set[str]) -> dict:
    if not isinstance(data, dict):
        raise ValidationError("not an object")
    keys = set(data)
    if not required <= keys or not keys <= required | optional:
        raise ValidationError(f"fields {sorted(keys)}")
    return data


def _str(value) -> str:
    if not isinstance(value, str):
        raise ValidationError("not a string")
    return value


def _int(value) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValidationError("not an integer")
    return value


def _ref(data) -> Ref:
    data = _fields(data, {"id", "version", "path"}, {"decided"})
    decided = data.get("decided", {})
    if not isinstance(decided, dict) or not all(
            isinstance(k, str) and isinstance(v, int | float) and not isinstance(v, bool)
            for k, v in decided.items()):
        raise ValidationError("decided")
    return Ref(_str(data["id"]), _str(data["version"]), _str(data["path"]), dict(decided))


def _head(data) -> Head:
    data = _fields(data, {"name", "length"}, {"whole"})
    length, whole = _int(data["length"]), data.get("whole", False)
    if length < 0 or not isinstance(whole, bool):
        raise ValidationError("file head")
    return Head(_str(data["name"]), length, whole)


def parse_request(line: bytes) -> Request:
    """The request line, as strictly as `wire.Request` reads it."""
    try:
        data = json.loads(line)
    except ValueError as error:
        raise ValidationError("not JSON") from error
    data = _fields(data, {"format", "codec", "measures", "files", "cap_bytes"}, set())
    if not isinstance(data["measures"], list) or not isinstance(data["files"], list):
        raise ValidationError("lists")
    cap = _int(data["cap_bytes"])
    if cap <= 0:
        raise ValidationError("cap_bytes")
    return Request(_ref(data["format"]), None if data["codec"] is None else _ref(data["codec"]),
                   [_ref(m) for m in data["measures"]], [_head(f) for f in data["files"]], cap)


def read_request(stream: BinaryIO) -> tuple[Request, list[bytes]]:
    """Read a request and reject any payload shorter than its declared length."""
    request = parse_request(stream.readline())
    payloads = []
    for head in request.files:
        payload = stream.read(head.length)
        if len(payload) != head.length:
            raise ValueError(f"{head.name}: {len(payload)} of {head.length} bytes arrived")
        payloads.append(payload)
    return request, payloads


_FACT = {"by", "value", "undetermined", "evidence", "coverage"}


def _fact(data) -> dict:
    data = _fields(data, {"by"}, _FACT - {"by"})
    if not isinstance(data["by"], list) or not all(isinstance(b, str) for b in data["by"]):
        raise ValidationError("by")
    value = data.get("value")
    if value is not None and not isinstance(value, int | float | str):
        raise ValidationError("value")
    if data.get("undetermined") is not None:
        _str(data["undetermined"])
    if not isinstance(data.get("evidence", {}), dict):
        raise ValidationError("evidence")
    if data.get("coverage") not in (None, "head", "all"):
        raise ValidationError("coverage")
    fact = {"by": list(data["by"]), "evidence": data.get("evidence", {})}
    for name in ("value", "undetermined", "coverage"):
        if data.get(name) is not None:
            fact[name] = data[name]
    return fact


def report_json(report: dict) -> str:
    """`wire.Report.model_validate(report).to_json()`, byte for byte, without pydantic: keys
    sorted, a `None` field left out (not a `None` inside `evidence`), and a report that does not
    have the wire's shape answered as `inspection failed: ValidationError`."""
    try:
        data = _fields(report, set(), {"type_id", "facts", "unreadable"})
        out: dict = {"facts": {}}
        facts = data.get("facts", {})
        if not isinstance(facts, dict):
            raise ValidationError("facts")
        for name, fact in facts.items():
            out["facts"][_str(name)] = _fact(fact)
        for name in ("type_id", "unreadable"):
            if data.get(name) is not None:
                out[name] = _str(data[name])
    except ValidationError:
        out = {"facts": {}, "unreadable": "inspection failed: ValidationError"}
    return json.dumps(out, sort_keys=True)


def broken(error: Exception) -> str:
    return json.dumps({"facts": {}, "unreadable": f"broken request: {type(error).__name__}"},
                      sort_keys=True)

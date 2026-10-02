"""The runner: one inspection, one streamed pass, every measure fed, every outcome a report.

**One pass, the whole head** (spec §4, decided B). The format yields each file's records once;
rows are read side by side across the files and handed to every measure; nothing stops early,
so every fact is measured on the same reads and its evidence says how many.

`type_id` is left `None` here: which type a confirmed format means is the caller's to say from
the format's declared `reads` (part 4), not something a piece reports about itself.
"""

import gzip
import importlib.util
import io
import sys
import zlib
from collections.abc import Callable, Iterator

from pydantic import ValidationError

from comeni_inspect import wire
from comeni_inspect.outcome import Value
from comeni_inspect.stream import Capped, TooLarge

_CONFIRM_BYTES = 4096


class _PieceFailed(Exception):
    """A piece raised. Its failure is this inspection's answer, never the caller's crash."""


def _load(ref: wire.PieceRef):
    spec = importlib.util.spec_from_file_location(f"piece_{ref.id}", ref.path)
    if spec is None or spec.loader is None:
        raise ImportError(f"no piece at {ref.path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _guarded(ref: wire.PieceRef | str, call: Callable):
    """Run one piece's code, turning anything it raises into `_PieceFailed`.

    **The only `except Exception` in this package**, and deliberately: at this call site a
    piece is code this runner did not write, and one piece failing is one inspection's answer
    (spec §8). The exceptions that mean the *bytes* are wrong — too large, corrupt — are let
    through, so the report says what is wrong with the file rather than blaming a piece.
    """
    name = ref.id if isinstance(ref, wire.PieceRef) else ref
    try:
        return call(ref)
    except (TooLarge, zlib.error, gzip.BadGzipFile):
        raise
    except Exception as error:  # noqa: BLE001 — see the docstring
        raise _PieceFailed(f"{name} failed: {type(error).__name__}") from error


def _unreadable(reason: str) -> wire.Report:
    return wire.Report(type_id=None, facts={}, unreadable=reason)


def inspect(request: wire.Request, payloads: list[bytes]) -> wire.Report:
    """One inspection. **Never raises**: every way it can go wrong is a report (spec §6)."""
    try:
        return _inspect(request, payloads)
    except TooLarge:
        return _unreadable("too large unpacked")
    except (zlib.error, gzip.BadGzipFile, OSError) as error:
        return _unreadable(f"could not be unpacked: {error}")
    except _PieceFailed as failed:
        return _unreadable(str(failed))


def _rows(fmt, ref: wire.PieceRef, streams: list) -> Iterator[tuple]:
    """Side by side; stops at the shorter file. A format's own failure is guarded here, since
    its generator runs only as it is read."""
    iterators = [_guarded(ref, lambda _, s=s: iter(fmt.records(s))) for s in streams]
    while True:
        row = []
        for iterator in iterators:
            record = _guarded(ref, lambda _, it=iterator: next(it, None))
            if record is None:
                return
            row.append(record)
        yield tuple(row)


def _inspect(request: wire.Request, payloads: list[bytes]) -> wire.Report:
    fmt = _guarded(request.format, _load)
    codec = _guarded(request.codec, _load) if request.codec else None
    streams = []
    for head, raw in zip(request.files, payloads, strict=True):
        if codec is None:
            opened = io.BytesIO(raw)
        else:
            opened = _guarded(request.codec, lambda _, r=raw: codec.open(r))
        stream = io.BufferedReader(Capped(opened, request.cap_bytes))
        first = stream.peek(_CONFIRM_BYTES)[:_CONFIRM_BYTES]
        if not first:
            return _unreadable(f"{head.name} is empty")
        if not _guarded(request.format, lambda _, f=first: fmt.confirms(f)):
            return _unreadable(
                f"{head.name} is named like {request.format.id}, but does not start like one"
            )
        streams.append(stream)
    names = [f.name for f in request.files]
    accumulators = {
        m.id: _guarded(m, lambda r: _load(r).Accumulator(dict(r.decided), names))
        for m in request.measures
    }
    rows = 0
    for row in _rows(fmt, request.format, streams):
        rows += 1
        for ref in request.measures:
            _guarded(ref, lambda _, a=accumulators[ref.id], r=row: a.add(r))
    by_format = f"{request.format.id}@{request.format.version}"
    facts = {}
    for ref in request.measures:
        outcome = _guarded(ref, lambda _, a=accumulators[ref.id]: a.result())
        by = [by_format, f"{ref.id}@{ref.version}"]
        # **`rows` on every fact** (review focus 1): a pair whose R2 the head cut short is read
        # up to the shorter file, and the report must show how far that was.
        evidence = {**outcome.evidence, "rows": rows}
        if isinstance(outcome, Value):
            facts[ref.id] = wire.Fact(by=by, value=outcome.value, evidence=evidence)
        else:
            facts[ref.id] = wire.Fact(by=by, undetermined=outcome.reason, evidence=evidence)
    return wire.Report(type_id=None, facts=facts, unreadable=None)


def main() -> int:
    """stdin → one report on stdout, exit 0. A broken request is a report too."""
    try:
        request, payloads = wire.read_request(sys.stdin.buffer)
    except (ValueError, ValidationError) as error:
        report = _unreadable(f"broken request: {type(error).__name__}")
    else:
        report = inspect(request, payloads)
    sys.stdout.write(report.to_json())
    return 0


if __name__ == "__main__":
    sys.exit(main())

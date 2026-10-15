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
import json
import math
import sys
import zlib
from collections.abc import Callable, Iterator

from pydantic import ValidationError

from comeni_inspect import wire
from comeni_inspect.outcome import Undetermined, Value
from comeni_inspect.records import Malformed
from comeni_inspect.stream import Capped, Prefixed, SourceFailed, TooLarge

_CONFIRM_BYTES = 4096


class _PieceFailed(Exception):
    """A piece raised. Its failure is this inspection's answer, never the caller's crash."""


def _load(ref: wire.PieceRef):
    """Import a piece by path, **writing no bytecode**: the piece lives in a registry layer, and
    a `__pycache__` beside it is a file nobody wrote in a tree a pipeline pins."""
    spec = importlib.util.spec_from_file_location(f"piece_{ref.id}", ref.path)
    if spec is None or spec.loader is None:
        raise ImportError(f"no piece at {ref.path}")
    module = importlib.util.module_from_spec(spec)
    before, sys.dont_write_bytecode = sys.dont_write_bytecode, True
    try:
        spec.loader.exec_module(module)
    finally:
        sys.dont_write_bytecode = before
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
    except (TooLarge, SourceFailed, zlib.error, gzip.BadGzipFile, Malformed):
        raise
    # `SystemExit` too: a piece can raise it without importing anything, and it must not end
    # the process before it has answered.
    except (Exception, SystemExit) as error:  # noqa: BLE001 — see the docstring
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
    except (_PieceFailed, SourceFailed) as failed:
        return _unreadable(str(failed))
    # **The last resort**, and the promise in this function's docstring rests on it: whatever
    # the runner itself got wrong is still one inspection's answer, never a crashed process.
    except Exception as error:  # noqa: BLE001
        return _unreadable(f"inspection failed: {type(error).__name__}")


def _rows(fmt, ref: wire.PieceRef, streams: list, ended: dict) -> Iterator[tuple]:
    """Side by side; stops at the shorter file. A format's own failure is guarded here, since
    its generator runs only as it is read.

    **Says which file was shorter** (review focus 1): when one file ends while another still
    has a record, `ended["shorter"]` is its index, so the report shows a cut R2 as a cut R2.
    """
    iterators = [_guarded(ref, lambda _, s=s: iter(fmt.records(s))) for s in streams]
    try:
        yield from _side_by_side(ref, iterators, ended)
    except Malformed as malformed:
        # The rows before it stand; every fact says where the format stopped (issue 224).
        ended["stopped"] = f"malformed {malformed}"


def _side_by_side(ref: wire.PieceRef, iterators: list, ended: dict) -> Iterator[tuple]:
    while True:
        row = []
        for index, iterator in enumerate(iterators):
            record = _guarded(ref, lambda _, it=iterator: next(it, None))
            if record is None:
                rest = iterators[index + 1 :]
                if row or any(
                    _guarded(ref, lambda _, it=it: next(it, None)) is not None for it in rest
                ):
                    ended["shorter"] = index
                return
            row.append(record)
        yield tuple(row)


def _fact(
    outcome, by: list[str], rows: int, shorter: str | None, capped: bool, stopped: str | None
) -> wire.Fact:
    """What a measure answered, held to the report's shape. **Inside the guard**: a measure
    returning `None`, a list, bytes in its evidence or `nan` is that measure's failure."""
    if not isinstance(outcome, Value | Undetermined):
        raise TypeError(f"result() gave {type(outcome).__name__}")
    # **`rows` on every fact** (review focus 1): a pair whose R2 the head cut short is read up
    # to the shorter file, and the report must show how far that was.
    evidence = {**outcome.evidence, "rows": rows}
    if shorter is not None:
        evidence["shorter_file"] = shorter
    if capped:
        # The head ended at the unpacked cap rather than at its own end (issue 221).
        evidence["capped"] = True
    if stopped is not None:
        evidence["stopped"] = stopped
    json.dumps(evidence, allow_nan=False)
    if isinstance(outcome, Undetermined):
        return wire.Fact(by=by, undetermined=str(outcome.reason), evidence=evidence)
    if isinstance(outcome.value, float) and not math.isfinite(outcome.value):
        raise ValueError("a value that is not a finite number")
    return wire.Fact(by=by, value=outcome.value, evidence=evidence)


def _inspect(request: wire.Request, payloads: list[bytes]) -> wire.Report:
    if len(request.files) != len(payloads):
        return _unreadable(f"broken request: {len(request.files)} files, {len(payloads)} payloads")
    fmt = _guarded(request.format, _load)
    codec = _guarded(request.codec, _load) if request.codec else None
    streams = []
    limits: list[Capped] = []
    for head, raw in zip(request.files, payloads, strict=True):
        if codec is None:
            opened = io.BytesIO(raw)
        else:
            opened = _guarded(request.codec, lambda _, r=raw: codec.open(r))
        source = request.codec.id if request.codec else "the file"
        limit = Capped(opened, request.cap_bytes, source, given=len(raw))
        limits.append(limit)
        capped = io.BufferedReader(limit)
        # `read`, not `peek`: a peek is one raw read and may show less than the window.
        first = capped.read(_CONFIRM_BYTES)
        stream = io.BufferedReader(Prefixed(first, capped))
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
    ended: dict[str, int | str] = {}
    for row in _rows(fmt, request.format, streams, ended):
        rows += 1
        for ref in request.measures:
            _guarded(ref, lambda _, a=accumulators[ref.id], r=row: a.add(r))
    by_format = f"{request.format.id}@{request.format.version}"
    facts = {}
    shorter = names[int(ended["shorter"])] if "shorter" in ended else None
    capped = any(limit.capped for limit in limits)
    stopped = ended.get("stopped")
    for ref in request.measures:
        by = [by_format, f"{ref.id}@{ref.version}"]
        facts[ref.id] = _guarded(
            ref,
            lambda _, a=accumulators[ref.id], b=by: _fact(
                a.result(), b, rows, shorter, capped, stopped
            ),
        )
    return wire.Report(type_id=None, facts=facts, unreadable=None)


def _limit_memory(limit: int) -> None:
    """Cap this process's address space: a parser that allocates past it dies, alone (spec §8).

    **Set by the child itself**, from `--memory-bytes`, rather than by the parent's
    `preexec_fn`, which is unsafe in a process with threads (the API calls from a thread pool).
    """
    import resource

    resource.setrlimit(resource.RLIMIT_AS, (limit, limit))


def main() -> int:
    """stdin → one report on stdout, exit 0. A broken request is a report too."""
    if "--memory-bytes" in sys.argv:
        _limit_memory(int(sys.argv[sys.argv.index("--memory-bytes") + 1]))
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

"""Run one inspection as a single streamed pass over the supplied file heads.

The format yields each file's records once. Records are read side by side and every row is sent
to every measure, so all facts describe the same input. The caller assigns ``type_id`` from the
confirmed format's declaration; pieces do not assign types to themselves.
"""

import gzip
import importlib.util
import io
import json
import math
import sys
import zlib
from collections.abc import Callable, Iterator
from dataclasses import dataclass

from pydantic import ValidationError

from comeni_inspect import wire
from comeni_inspect.outcome import Undetermined, Value
from comeni_inspect.records import Malformed
from comeni_inspect.stream import Capped, Prefixed, SourceFailed, TooLarge

_CONFIRM_BYTES = 4096


class _PieceFailed(Exception):
    """Report that dynamically loaded piece code failed during an inspection."""


@dataclass
class _ReadState:
    shorter_index: int | None = None
    stopped: str | None = None


def _load(ref: wire.PieceRef):
    """Import a registry piece by path without writing bytecode beside it."""
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

    Piece code is external to the runner, so its failures become inspection results. Exceptions
    that describe invalid input bytes pass through and retain their more specific report reason.
    """
    name = ref.id if isinstance(ref, wire.PieceRef) else ref
    try:
        return call(ref)
    except (TooLarge, SourceFailed, zlib.error, gzip.BadGzipFile, Malformed):
        raise
    # A piece may raise SystemExit; it must not terminate the runner before it reports.
    except (Exception, SystemExit) as error:  # noqa: BLE001 — see the docstring
        raise _PieceFailed(f"{name} failed: {type(error).__name__}") from error


def _unreadable(reason: str) -> wire.Report:
    return wire.Report(type_id=None, facts={}, unreadable=reason)


def inspect(request: wire.Request, payloads: list[bytes]) -> wire.Report:
    """Inspect the payloads, returning failures as unreadable reports instead of raising."""
    try:
        return _inspect(request, payloads)
    except TooLarge:
        return _unreadable("too large unpacked")
    except (zlib.error, gzip.BadGzipFile, OSError) as error:
        return _unreadable(f"could not be unpacked: {error}")
    except (_PieceFailed, SourceFailed) as failed:
        return _unreadable(str(failed))
    # Preserve the process contract even when the runner itself encounters an unexpected error.
    except Exception as error:  # noqa: BLE001
        return _unreadable(f"inspection failed: {type(error).__name__}")


def _rows(fmt, ref: wire.PieceRef, streams: list, state: _ReadState) -> Iterator[tuple]:
    """Yield records side by side and record why iteration ended.

    Iteration stops at the shorter file. Format failures are guarded here because a generator's
    body runs only when it is advanced.
    """
    iterators = [_guarded(ref, lambda _, s=s: iter(fmt.records(s))) for s in streams]
    try:
        yield from _side_by_side(ref, iterators, state)
    except Malformed as malformed:
        # Measurements retain complete rows that preceded the malformed record.
        state.stopped = f"malformed {malformed}"


def _side_by_side(ref: wire.PieceRef, iterators: list, state: _ReadState) -> Iterator[tuple]:
    while True:
        row = []
        for index, iterator in enumerate(iterators):
            record = _guarded(ref, lambda _, it=iterator: next(it, None))
            if record is None:
                rest = iterators[index + 1 :]
                if row or any(
                    _guarded(ref, lambda _, it=it: next(it, None)) is not None for it in rest
                ):
                    state.shorter_index = index
                return
            row.append(record)
        yield tuple(row)


def _fact(
    outcome, by: list[str], rows: int, shorter: str | None, capped: bool, stopped: str | None
) -> wire.Fact:
    """Validate a measure's outcome and convert it to the public fact shape."""
    if not isinstance(outcome, Value | Undetermined):
        raise TypeError(f"result() gave {type(outcome).__name__}")
    evidence = {**outcome.evidence, "rows": rows}
    if shorter is not None:
        evidence["shorter_file"] = shorter
    if capped:
        # Distinguish a bounded head from the input's natural end.
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
    state = _ReadState()
    for row in _rows(fmt, request.format, streams, state):
        rows += 1
        for ref in request.measures:
            _guarded(ref, lambda _, a=accumulators[ref.id], r=row: a.add(r))
    by_format = f"{request.format.id}@{request.format.version}"
    facts = {}
    shorter = names[state.shorter_index] if state.shorter_index is not None else None
    capped = any(limit.capped for limit in limits)
    for ref in request.measures:
        by = [by_format, f"{ref.id}@{ref.version}"]
        facts[ref.id] = _guarded(
            ref,
            lambda _, a=accumulators[ref.id], b=by: _fact(
                a.result(), b, rows, shorter, capped, state.stopped
            ),
        )
    return wire.Report(type_id=None, facts=facts, unreadable=None)


def _limit_memory(limit: int) -> None:
    """Cap this process's address space so an excessive allocation kills only the child.

    The child applies the limit from ``--memory-bytes``. The threaded API parent therefore does
    not need the unsafe ``preexec_fn`` hook.
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

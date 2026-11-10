"""Run one inspection as a single streamed pass, on the standard library alone.

The same core serves both runners (#465): the server's sandboxed process, which reads the head of
an upload under a cap, and the pipeline's step, which reads whole files with none. Because a
pipeline step runs on a plain Python image, nothing here imports beyond the standard library and
this package's own stdlib modules; `wire.py` adds pydantic at the server's process boundary only.

The format yields each file's records once. Records are read side by side and every row is sent
to every measure, so all facts describe the same input. A report is a plain dict in the shape of
`wire.Report`, with `None` left out.
"""

import gzip
import importlib.util
import io
import json
import math
import sys
import zlib
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from typing import BinaryIO

from comeni_inspect.outcome import Undetermined, Value
from comeni_inspect.records import Malformed
from comeni_inspect.stream import Capped, Prefixed, SourceFailed, TooLarge

_CONFIRM_BYTES = 4096


@dataclass(frozen=True)
class Ref:
    """A piece to load: its id and version, its entry file (absolute) and its thresholds."""

    id: str
    version: str
    path: str
    decided: dict = field(default_factory=dict)

    @property
    def pinned(self) -> str:
        return f"{self.id}@{self.version}"


@dataclass(frozen=True)
class Source:
    """One file to read: its name (for evidence and reasons, never for deciding), its opened
    bytes, and its size on the wire when known (what the expansion-ratio check compares)."""

    name: str
    stream: BinaryIO
    given: int | None = None
    whole: bool = True
    """These bytes are the whole file. False for an upload's head: reaching its end then says
    nothing about the rest, so its facts cover only the `head`."""


class PieceFailed(Exception):
    """Report that dynamically loaded piece code failed during an inspection."""


@dataclass
class _ReadState:
    shorter_index: int | None = None
    stopped: str | None = None


def load(ref: Ref):
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


def guarded(ref: Ref | str, call: Callable):
    """Run one piece's code, turning anything it raises into `PieceFailed`.

    Piece code is external to the runner, so its failures become inspection results. Exceptions
    that describe invalid input bytes pass through and retain their more specific report reason.
    """
    name = ref.id if isinstance(ref, Ref) else ref
    try:
        return call(ref)
    except (TooLarge, SourceFailed, zlib.error, gzip.BadGzipFile, Malformed):
        raise
    # A piece may raise SystemExit; it must not terminate the runner before it reports.
    except (Exception, SystemExit) as error:  # noqa: BLE001 — see the docstring
        raise PieceFailed(f"{name} failed: {type(error).__name__}") from error


def unreadable(reason: str) -> dict:
    return {"facts": {}, "unreadable": reason}


def _reported(body: Callable[[], dict]) -> dict:
    """Every failure is a report, never an exception: the process contract of both runners."""
    try:
        return body()
    except TooLarge:
        return unreadable("too large unpacked")
    except (zlib.error, gzip.BadGzipFile, OSError) as error:
        return unreadable(f"could not be unpacked: {error}")
    except (PieceFailed, SourceFailed) as failed:
        return unreadable(str(failed))
    # Preserve the process contract even when the runner itself meets an unexpected error.
    except Exception as error:  # noqa: BLE001
        return unreadable(f"inspection failed: {type(error).__name__}")


def inspect_streams(
    fmt: Ref, codec: Ref | None, measures: list[Ref], files: list[Source], cap: int | None
) -> dict:
    """Inspect these files. `cap` bounds what each may unpack to; `None` reads all of it."""
    return _reported(lambda: _inspect(fmt, codec, measures, files, cap))


def parse_output(parser: Ref, source: Source) -> dict:
    """One parser over one tool output, whole: a `by: tool` measurer's half of a pipeline step."""
    return _reported(lambda: _parse(parser, source))


def _rows(fmt, ref: Ref, streams: list, state: _ReadState) -> Iterator[tuple]:
    """Yield records side by side and record why iteration ended.

    Iteration stops at the shorter file. Format failures are guarded here because a generator's
    body runs only when it is advanced.
    """
    iterators = [guarded(ref, lambda _, s=s: iter(fmt.records(s))) for s in streams]
    try:
        yield from _side_by_side(ref, iterators, state)
    except Malformed as malformed:
        # Measurements retain complete rows that preceded the malformed record.
        state.stopped = f"malformed {malformed}"


def _side_by_side(ref: Ref, iterators: list, state: _ReadState) -> Iterator[tuple]:
    while True:
        row = []
        for index, iterator in enumerate(iterators):
            record = guarded(ref, lambda _, it=iterator: next(it, None))
            if record is None:
                rest = iterators[index + 1 :]
                if row or any(
                    guarded(ref, lambda _, it=it: next(it, None)) is not None for it in rest
                ):
                    state.shorter_index = index
                return
            row.append(record)
        yield tuple(row)


def _fact(outcome, by: list[str], evidence_extra: dict, capped: bool, partial: bool) -> dict:
    """Check a piece's outcome and give it the public fact shape."""
    if not isinstance(outcome, Value | Undetermined):
        raise TypeError(f"result() gave {type(outcome).__name__}")
    evidence = {**outcome.evidence, **evidence_extra}
    if capped:
        # Distinguish a bounded head from the input's natural end.
        evidence["capped"] = True
    json.dumps(evidence, allow_nan=False)
    coverage = "head" if partial else "all"
    if isinstance(outcome, Undetermined):
        return {"by": by, "undetermined": str(outcome.reason), "evidence": evidence,
                "coverage": coverage}
    value = outcome.value
    if not isinstance(value, bool | int | float | str):
        raise TypeError(f"a value of type {type(value).__name__}")
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError("a value that is not a finite number")
    return {"by": by, "value": value, "evidence": evidence, "coverage": coverage}


def _inspect(
    fmt_ref: Ref, codec_ref: Ref | None, measures: list[Ref], files: list[Source], cap: int | None
) -> dict:
    fmt = guarded(fmt_ref, load)
    codec = guarded(codec_ref, load) if codec_ref else None
    streams = []
    limits: list[Capped] = []
    for source in files:
        if codec is None:
            opened = source.stream
        else:
            opened = guarded(codec_ref, lambda _, s=source.stream: codec.open(s))
        name = codec_ref.id if codec_ref else "the file"
        # With no cap, `Capped` still turns a codec's end-of-stream into a quiet end.
        limit = Capped(opened, cap if cap is not None else sys.maxsize, name, given=source.given)
        limits.append(limit)
        bounded = io.BufferedReader(limit)
        # `read`, not `peek`: a peek is one raw read and may show less than the window.
        first = bounded.read(_CONFIRM_BYTES)
        stream = io.BufferedReader(Prefixed(first, bounded))
        if not first:
            return unreadable(f"{source.name} is empty")
        if not guarded(fmt_ref, lambda _, f=first: fmt.confirms(f)):
            return unreadable(
                f"{source.name} is named like {fmt_ref.id}, but does not start like one"
            )
        streams.append(stream)
    names = [source.name for source in files]
    accumulators = {
        m.id: guarded(m, lambda r: load(r).Accumulator(dict(r.decided), names)) for m in measures
    }
    rows = 0
    state = _ReadState()
    for row in _rows(fmt, fmt_ref, streams, state):
        rows += 1
        for ref in measures:
            guarded(ref, lambda _, a=accumulators[ref.id], r=row: a.add(r))
    extra: dict = {"rows": rows}
    if state.shorter_index is not None:
        extra["shorter_file"] = names[state.shorter_index]
    if state.stopped is not None:
        extra["stopped"] = state.stopped
    capped = any(limit.capped for limit in limits)
    partial = capped or not all(source.whole for source in files)
    facts = {}
    for ref in measures:
        by = [fmt_ref.pinned, ref.pinned]
        facts[ref.id] = guarded(
            ref,
            lambda _, a=accumulators[ref.id], b=by: _fact(a.result(), b, extra, capped, partial),
        )
    return {"facts": facts}


def _parse(parser: Ref, source: Source) -> dict:
    module = guarded(parser, load)
    outcome = guarded(parser, lambda r: module.parse(source.stream, dict(r.decided)))
    fact = guarded(
        parser,
        lambda _: _fact(outcome, [parser.pinned], {}, capped=False, partial=not source.whole),
    )
    return {"facts": {parser.id: fact}}

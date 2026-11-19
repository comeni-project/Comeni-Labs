"""The server's runner: one inspection of an upload's head, in a sandboxed process.

The request arrives on stdin in the wire protocol (`wire.py`) and the report leaves on stdout.
The inspection itself is `core`, which the pipeline runner (`measure_cli`) shares, so a measure
written once runs in both places (#465). The caller assigns ``type_id`` from the confirmed
format's declaration; pieces do not assign types to themselves.
"""

import io
import sys

from comeni_inspect import child, core

# **No pydantic on the child's path** (#572): importing it was most of a child's start-up, and
# one child starts per sample per candidate format. `inspect` below, for in-process callers,
# imports the `wire` models when it is called; `main` reads and writes through `child`.


def _ref(piece) -> core.Ref:
    return core.Ref(id=piece.id, version=piece.version, path=piece.path,
                    decided=dict(piece.decided))


def _inspected(request, payloads: list[bytes]) -> dict:
    return core.inspect_streams(
        _ref(request.format),
        _ref(request.codec) if request.codec else None,
        [_ref(m) for m in request.measures],
        [core.Source(name=head.name, stream=io.BytesIO(raw), given=len(raw), whole=head.whole)
         for head, raw in zip(request.files, payloads, strict=True)],
        cap=request.cap_bytes,
    )


def inspect(request, payloads: list[bytes]):
    """Inspect the payloads, returning failures as unreadable reports instead of raising. A
    `wire.Request` in, a `wire.Report` out: for callers in this process (the harness, tests)."""
    from pydantic import ValidationError

    from comeni_inspect import wire

    if len(request.files) != len(payloads):
        return wire.Report(
            unreadable=f"broken request: {len(request.files)} files, {len(payloads)} payloads"
        )
    report = _inspected(request, payloads)
    try:
        return wire.Report.model_validate(report)
    except ValidationError as error:
        return wire.Report(unreadable=f"inspection failed: {type(error).__name__}")


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
        request, payloads = child.read_request(sys.stdin.buffer)
    except ValueError as error:
        sys.stdout.write(child.broken(error))
    else:
        sys.stdout.write(child.report_json(_inspected(request, payloads)))
    return 0


if __name__ == "__main__":
    sys.exit(main())

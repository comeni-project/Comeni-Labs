"""The server's runner: one inspection of an upload's head, in a sandboxed process.

The request arrives on stdin in the wire protocol (`wire.py`) and the report leaves on stdout.
The inspection itself is `core`, which the pipeline runner (`measure_cli`) shares, so a measure
written once runs in both places (#465). The caller assigns ``type_id`` from the confirmed
format's declaration; pieces do not assign types to themselves.
"""

import io
import sys

from pydantic import ValidationError

from comeni_inspect import core, wire


def _ref(piece: wire.PieceRef) -> core.Ref:
    return core.Ref(id=piece.id, version=piece.version, path=piece.path,
                    decided=dict(piece.decided))


def inspect(request: wire.Request, payloads: list[bytes]) -> wire.Report:
    """Inspect the payloads, returning failures as unreadable reports instead of raising."""
    if len(request.files) != len(payloads):
        return wire.Report(
            unreadable=f"broken request: {len(request.files)} files, {len(payloads)} payloads"
        )
    report = core.inspect_streams(
        _ref(request.format),
        _ref(request.codec) if request.codec else None,
        [_ref(m) for m in request.measures],
        [core.Source(name=head.name, stream=io.BytesIO(raw), given=len(raw), whole=head.whole)
         for head, raw in zip(request.files, payloads, strict=True)],
        cap=request.cap_bytes,
    )
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
        request, payloads = wire.read_request(sys.stdin.buffer)
    except (ValueError, ValidationError) as error:
        report = wire.Report(unreadable=f"broken request: {type(error).__name__}")
    else:
        report = inspect(request, payloads)
    sys.stdout.write(report.to_json())
    return 0


if __name__ == "__main__":
    sys.exit(main())

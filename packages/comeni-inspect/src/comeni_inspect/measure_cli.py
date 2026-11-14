"""The pipeline's runner: whole files, no cap, the same pieces the server runs (#465).

A pipeline step runs this on a plain Python image, so it imports the standard library and this
package's stdlib modules only. Everything it needs arrives on the command line, written by the
emitter; it reads no YAML and no registry:

    measure_cli.py --format fastq@1.1.0=PATH [--codec gzip@1.0.0=PATH]
                   --measure read_length@1.0.0=PATH [--decided read_length={"min_records":1000}]
                   FILE [FILE]
    measure_cli.py --parser genome_length_fai@1.0.0=PATH [--decided genome_length_fai={}] FILE

One report goes to stdout, in the shape of the server's (`PROTOCOL.md`), and the exit status is
0 whatever happened: a failure is that report's `unreadable`.
"""

import argparse
import json
import sys
from pathlib import Path

if __package__ in (None, ""):
    # Run as a staged script (`python3 -I runner/comeni_inspect/measure_cli.py`): `-I` leaves the
    # script's folder off the path, so the package is put on it by where this file is.
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from comeni_inspect import core  # noqa: E402


class _Broken(Exception):
    pass


class _Parser(argparse.ArgumentParser):
    def error(self, message):  # an argparse failure is a report, never exit 2
        raise _Broken(message)


def _ref(spelled: str, decided: dict[str, dict]) -> core.Ref:
    pinned, sep, path = spelled.partition("=")
    piece, at, version = pinned.partition("@")
    if not (sep and at and piece and version and path):
        raise _Broken(f"{spelled!r} is not id@version=path")
    return core.Ref(id=piece, version=version, path=str(Path(path).resolve()),
                    decided=decided.get(piece, {}))


def _decided(spelled: list[str]) -> dict[str, dict]:
    found = {}
    for entry in spelled:
        piece, sep, value = entry.partition("=")
        if not sep:
            raise _Broken(f"--decided {entry!r} is not id=JSON")
        try:
            found[piece] = json.loads(value)
        except json.JSONDecodeError as error:
            raise _Broken(f"--decided {piece}: {error.msg}") from error
        if not isinstance(found[piece], dict):
            raise _Broken(f"--decided {piece} is not an object")
    return found


def _renamed(report: dict, named: list[str]) -> dict:
    """`--as id=measurement`: each fact keyed by the measurement it is, which is what a
    pipeline reads (`facts.genome_length`), whatever the measurer is called. A pair the report
    lacks renames nothing; the default key is the piece's id, as on the server."""
    names = dict(pair.partition("=")[::2] for pair in named)
    facts = {names.get(key, key): fact for key, fact in report.get("facts", {}).items()}
    return {**report, "facts": dict(sorted(facts.items()))}


def _run(argv: list[str]) -> dict:
    parser = _Parser(prog="measure_cli", add_help=False)
    parser.add_argument("--format")
    parser.add_argument("--codec")
    parser.add_argument("--measure", action="append", default=[])
    parser.add_argument("--parser")
    parser.add_argument("--decided", action="append", default=[])
    parser.add_argument("--as", dest="named", action="append", default=[])
    parser.add_argument("files", nargs="+")
    try:
        args = parser.parse_args(argv)
        decided = _decided(args.decided)
        if bool(args.parser) == bool(args.format):
            raise _Broken("give --format with --measure, or --parser, and not both")
        if args.parser:
            if len(args.files) != 1:
                raise _Broken("a parser reads one file")
            parser_ref = _ref(args.parser, decided)
        else:
            if not args.measure:
                raise _Broken("--format needs at least one --measure")
            fmt = _ref(args.format, decided)
            codec = _ref(args.codec, decided) if args.codec else None
            measures = [_ref(m, decided) for m in args.measure]
    except _Broken as broken:
        return core.unreadable(f"broken request: {broken}")
    opened = []
    try:
        for name in args.files:
            opened.append(open(name, "rb"))  # noqa: SIM115 — closed below, after the read
        sources = [core.Source(name=Path(n).name, stream=s)
                   for n, s in zip(args.files, opened, strict=True)]
        if args.parser:
            report = core.parse_output(parser_ref, sources[0])
        else:
            report = core.inspect_streams(fmt, codec, measures, sources, cap=None)
        return _renamed(report, args.named)
    except OSError as error:
        return core.unreadable(f"could not be read: {error.strerror}")
    finally:
        for stream in opened:
            stream.close()


def main(argv: list[str] | None = None) -> int:
    report = _run(sys.argv[1:] if argv is None else argv)
    sys.stdout.write(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""The conformance harness: every fixture case, and its report from any implementation.

**The goldens are the contract** (spec §4). A faster implementation of a piece, in any
language, is valid when `run_case(case, command=[...])` reproduces every `expected.json` byte
for byte. The pieces' own tests and the conformance test build requests here, one way.
"""

import io
import subprocess
from dataclasses import dataclass
from pathlib import Path

import yaml

from comeni_inspect import run, wire

CAP_BYTES = 16 * 2**20
"""What a file may unpack to (spec §8)."""


@dataclass(frozen=True)
class Case:
    name: str
    folder: Path
    request: wire.Request
    payloads: list[bytes]


def _declaration(folder: Path) -> dict:
    (path,) = folder.glob("*.yml")
    return yaml.safe_load(path.read_text())


def _ref(folder: Path) -> wire.PieceRef:
    data = _declaration(folder)
    return wire.PieceRef(
        id=data["id"],
        version=data["version"],
        path=str(folder / data["entry"]),
        decided=data.get("decided", {}),
    )


def _pieces(registry: Path, kind: str) -> list[Path]:
    return sorted(p for p in (registry / "inspectors" / kind).glob("*") if p.is_dir())


def _codec_for(registry: Path, names: list[str]) -> wire.PieceRef | None:
    for folder in _pieces(registry, "codecs"):
        extensions = _declaration(folder)["extensions"]
        if any(name.endswith(tuple(extensions)) for name in names):
            return _ref(folder)
    return None


def request_for(
    registry: Path, format_folder: Path, named: list[tuple[str, bytes]], measures: list[str] | None
) -> tuple[wire.Request, list[bytes]]:
    """A request for these files, read by this format, with these measures (all of the
    format's record kind when `None`)."""
    record = _declaration(format_folder)["record"]
    chosen = [
        folder
        for folder in _pieces(registry, "measures")
        if _declaration(folder)["record"] == record
        and (measures is None or folder.name in measures)
    ]
    request = wire.Request(
        format=_ref(format_folder),
        codec=_codec_for(registry, [name for name, _ in named]),
        measures=[_ref(folder) for folder in chosen],
        files=[wire.FileHead(name=name, length=len(data)) for name, data in named],
        cap_bytes=CAP_BYTES,
    )
    return request, [data for _, data in named]


def files_of(case_folder: Path) -> list[tuple[str, bytes]]:
    paths = sorted(p for p in case_folder.iterdir() if p.is_file() and p.name != "expected.json")
    return [(p.name, p.read_bytes()) for p in paths]


def cases(registry: Path) -> list[Case]:
    """Every fixture folder of every format, with all of that format's measures."""
    found = []
    for format_folder in _pieces(registry, "formats"):
        fixtures = format_folder / "piece" / "fixtures"
        for folder in sorted(p for p in fixtures.iterdir() if p.is_dir()):
            request, payloads = request_for(registry, format_folder, files_of(folder), None)
            found.append(Case(f"{format_folder.name}/{folder.name}", folder, request, payloads))
    return found


def request_for_bytes(
    registry: Path, name: str, raw: bytes, format_id: str = "fastq"
) -> tuple[wire.Request, list[bytes]]:
    """One file, built the way `cases` builds them."""
    folder = registry / "inspectors" / "formats" / format_id
    return request_for(registry, folder, [(name, raw)], None)


def run_case(case: Case, command: list[str] | None = None) -> str:
    """The report JSON: in-process when `command` is None, else by piping the request into it."""
    if command is None:
        return run.inspect(case.request, case.payloads).to_json()
    stream = io.BytesIO()
    wire.write_request(stream, case.request, case.payloads)
    done = subprocess.run(command, input=stream.getvalue(), capture_output=True, timeout=30)
    return done.stdout.decode()

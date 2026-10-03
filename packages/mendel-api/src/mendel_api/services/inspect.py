"""Inspect an uploaded sample: match its pieces, run them in their own process, answer (spec §7-§8).

**Every failure is an answer, never an exception.** A hang, a crash, a bomb, a report nobody can
read: each is `unreadable` with a reason, and the conversation goes on. The inspection runs in a
short-lived child process with a memory limit, a time limit and a cap on what a file may unpack
to, and receives its bytes on stdin; this process never imports a piece.

**Nothing guessed** (spec §5, §7): no format names the file's extension → `no_inspector`; several
formats confirm it → `tie`, for the person to decide; an undetermined fact is returned with its
reason and is not recorded by anyone downstream.
"""

import io
import os
import subprocess
import sys
from pathlib import Path
from typing import Literal

from comeni_core.declared.inspection import CodecPiece, FormatPiece, InspectionCatalogue
from comeni_inspect import wire
from pydantic import BaseModel, ConfigDict, Field

from mendel_api.services import measurers
from mendel_api.settings import settings

HEAD_BYTES = 4 * 2**20
"""The most read of any uploaded file (spec §10)."""
CAP_BYTES = 16 * 2**20
"""What a file may unpack to; reaching it ends the head (issue 221)."""
TIMEOUT_S = 5.0
MEMORY_BYTES = 512 * 2**20


class InspectedFact(BaseModel):
    model_config = ConfigDict(extra="forbid")

    measurement: str
    value: int | float | bool | str | None = None
    undetermined: str | None = None
    pieces: list[str] = Field(default_factory=list)
    evidence: dict = Field(default_factory=dict)


class Inspection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    outcome: Literal["measured", "unreadable", "no_inspector", "tie"]
    type_id: str | None = None
    facts: list[InspectedFact] = Field(default_factory=list)
    reason: str | None = None
    steps: list[str] = Field(default_factory=list)
    """What was done, in order, for the card: returned with the answer, not streamed (an
    inspection is one short request; 14.7.6.4's ruling)."""


def _command() -> list[str]:
    """The runner, which caps its own memory (a parser that allocates past it dies, alone). A
    seam: the tests put a sleeping or crashing process here."""
    return [sys.executable, "-m", "comeni_inspect.run", "--memory-bytes", str(MEMORY_BYTES)]


def _environment() -> dict[str, str]:
    """**What the child may see: nothing of this server's.** A piece is code from a registry
    layer, run on a person's bytes; trusting the layer to bring code is not handing that code the
    database URL, the model keys or `WIENER_API_TOKEN`, the boundary in front of a root-equivalent
    Docker socket (review of #134)."""
    return {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "LANG": "C.UTF-8"}


def _unreadable(reason: str) -> wire.Report:
    return wire.Report(type_id=None, facts={}, unreadable=reason)


def launch(request: wire.Request, payloads: list[bytes]) -> wire.Report:
    """One inspection in its own process. **Every failure is an answer**, never an exception."""
    buffer = io.BytesIO()
    wire.write_request(buffer, request, payloads)
    try:
        done = subprocess.run(
            _command(),
            input=buffer.getvalue(),
            capture_output=True,
            timeout=TIMEOUT_S,
            env=_environment(),
            cwd="/",
            check=False,
        )
    except subprocess.TimeoutExpired:
        # `run` kills the child on a timeout and waits for it before raising, so nothing is
        # left behind (review focus 5, pinned by a test that looks for it).
        return _unreadable("took too long")
    except OSError as error:
        return _unreadable(f"the inspector could not start: {type(error).__name__}")
    if done.returncode != 0:
        return _unreadable(f"the inspector stopped (exit {done.returncode})")
    try:
        return wire.Report.model_validate_json(done.stdout)
    except ValueError:
        return _unreadable("the inspector's report could not be read")


def _ends(name: str, extensions: list[str]) -> str | None:
    """The longest of `extensions` that `name` ends with, lower-cased."""
    lowered = name.lower()
    hits = [e for e in extensions if lowered.endswith(e.lower())]
    return max(hits, key=len) if hits else None


def match(
    names: list[str], pieces: InspectionCatalogue
) -> tuple[CodecPiece | None, list[FormatPiece]]:
    """The codec and the candidate formats, by extension. **Every file must agree**, else none."""
    answers = set()
    for name in names:
        codec = next(
            (c for c in pieces.codecs.values() if _ends(name, c.extensions)), None
        )
        rest = name[: len(name) - len(_ends(name, codec.extensions))] if codec else name
        formats = tuple(
            sorted(f.id for f in pieces.formats.values() if _ends(rest, f.extensions))
        )
        answers.add((codec.id if codec else None, formats))
    if len(answers) != 1:
        return None, []
    (codec_id, format_ids), = answers
    if not format_ids:
        return None, []
    return (
        pieces.codecs[codec_id] if codec_id else None,
        [pieces.formats[f] for f in format_ids],
    )


def _ref(kind: str, piece) -> wire.PieceRef:
    folder = Path(settings.registry_root).resolve() / "inspectors" / kind / piece.id
    return wire.PieceRef(
        id=piece.id,
        version=piece.version,
        path=str(folder / piece.entry),
        decided=getattr(piece, "decided", {}),
    )


def _facts(report: wire.Report, pieces: InspectionCatalogue) -> list[InspectedFact]:
    """The report's facts, keyed by the measurement each measure produces, not the measure."""
    found = []
    for measure_id, fact in sorted(report.facts.items()):
        measure = pieces.measures[measure_id]
        found.append(
            InspectedFact(
                measurement=measure.measures,
                value=fact.value,
                undetermined=fact.undetermined,
                pieces=list(fact.by),
                evidence=dict(fact.evidence),
            )
        )
    return found


def inspect_sample(files: list[tuple[str, bytes]], stack) -> Inspection:
    """Inspect one sample: one file, or a pair. **Never raises.**"""
    steps = [f"read the first {HEAD_BYTES // 2**20} MB of {len(files)} file(s)"]
    pieces = measurers.usable_pieces(stack)
    codec, formats = match([name for name, _ in files], pieces)
    if not formats:
        return Inspection(outcome="no_inspector", reason="nothing reads this type yet", steps=steps)
    if codec is not None:
        steps.append(f"unpacked {codec.id}")
    payloads = [data for _, data in files]
    heads = [wire.FileHead(name=name, length=len(data)) for name, data in files]
    confirmed: list[tuple[FormatPiece, wire.Report]] = []
    refused: list[wire.Report] = []
    for fmt in formats:
        least, most = fmt.file_counts
        if not least <= len(files) <= most:
            # Refused here, where the declaration is at hand: the runner is handed pieces by
            # reference and never sees `files:` (issue 224).
            refused.append(
                _unreadable(f"{fmt.id} reads {least} to {most} files, and {len(files)} were given")
            )
            continue
        request = wire.Request(
            format=_ref("formats", fmt),
            codec=_ref("codecs", codec) if codec else None,
            measures=[
                _ref("measures", m) for m in pieces.measures.values() if m.record == fmt.record
            ],
            files=heads,
            cap_bytes=CAP_BYTES,
        )
        report = launch(request, payloads)
        if report.unreadable is None:
            confirmed.append((fmt, report))
            steps.append(f"confirmed {fmt.id.upper()}")
        else:
            refused.append(report)
    if not confirmed:
        return Inspection(outcome="unreadable", reason=refused[0].unreadable, steps=steps)
    if len(confirmed) > 1:
        names = ", ".join(fmt.id for fmt, _ in confirmed)
        return Inspection(outcome="tie", reason=f"read as each of {names}", steps=steps)
    fmt, report = confirmed[0]
    facts = _facts(report, pieces)
    decided = sum(1 for f in facts if f.undetermined is None)
    steps.append(f"measured {decided} fact(s)")
    return Inspection(outcome="measured", type_id=fmt.reads[0], facts=facts, steps=steps)

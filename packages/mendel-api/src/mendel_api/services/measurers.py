"""Who measures what, and where it runs: inspector pieces and profilers, side by side (spec §2).

A measurement can be measured two ways. An **inspector** (a format with a measure) reads an
uploaded sample's head on this server, during the conversation. A **profiler** (a contract that
produces `measurement.<id>`) runs inside the lab's pipeline, on all of the data. This index is
what the conversation offers an upload from, and what the docs' *where it runs* table lists.

**Trusted layers only run code.** A piece from a layer the operator has not named in
`MENDEL_TRUSTED_LAYERS` is listed, marked untrusted, and never run.
"""

from typing import Literal

from comeni_core.declared.inspection import InspectionCatalogue
from pydantic import BaseModel, ConfigDict

from mendel_api.settings import settings


class Measurer(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    measurement: str
    kind: Literal["inspector", "profiler"]
    by: str
    """`fastq@1.0.0 + read_length@1.0.0` for an inspector, a contract id for a profiler."""
    runs: Literal["server", "lab", "browser"]
    trusted: bool


def _trusted(catalogue: InspectionCatalogue, key: str) -> bool:
    return catalogue.origin.get(key) in settings.trusted_layers


def index(stack) -> list[Measurer]:
    """Every way the stack can measure each measurement, sorted `(measurement, kind, by)`."""
    pieces = stack.inspection
    found = [
        Measurer(
            measurement=measure.measures,
            kind="inspector",
            by=f"{fmt.id}@{fmt.version} + {measure.id}@{measure.version}",
            runs=fmt.runs,
            trusted=_trusted(pieces, f"format:{fmt.id}")
            and _trusted(pieces, f"measure:{measure.id}"),
        )
        for measure in pieces.measures.values()
        for fmt in pieces.formats.values()
        if fmt.record == measure.record
    ]
    found += [
        Measurer(
            measurement=port.type_id.removeprefix("measurement."),
            kind="profiler",
            by=contract.id,
            runs="lab",
            trusted=True,
        )
        for contract in stack.registry.all()
        for port in contract.produces
        if port.type_id.startswith("measurement.")
    ]
    return sorted(set(found), key=lambda m: (m.measurement, m.kind, m.by))


def usable_pieces(stack) -> InspectionCatalogue:
    """The pieces this server may run: from trusted layers, and formats that run on a server."""
    pieces = stack.inspection

    def keep(kind: str, entries: dict) -> dict:
        return {key: piece for key, piece in entries.items() if _trusted(pieces, f"{kind}:{key}")}

    # Only a format that runs on this server runs here; `lab` and `browser` are elsewhere.
    formats = {k: f for k, f in keep("format", pieces.formats).items() if f.runs == "server"}
    return InspectionCatalogue(
        codecs=keep("codec", pieces.codecs),
        formats=formats,
        measures=keep("measure", pieces.measures),
        origin=pieces.origin,
    )

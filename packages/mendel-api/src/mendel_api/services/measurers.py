"""Who measures what, and where it runs: every measurer, with the places it may run (#465).

A measurer produces one measurement, by our own code over a format's records or by a tool plus a
parser for its output, and lists where it runs: the **server**, over an upload's head during the
conversation, and the **pipeline**, as a step over all the data during the run. This index is
what the conversation offers an upload from, and what the docs' *where it runs* table lists.

**Trusted layers only run code here.** A piece from a layer the operator has not named in
`MENDEL_TRUSTED_LAYERS` is listed, marked untrusted, and never run on this server.
"""

from comeni_core.declared.inspection import InspectionCatalogue
from pydantic import BaseModel, ConfigDict

from mendel_api.settings import settings


class Measurer(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    measurement: str
    by: str
    """`fastq@1.1.0 + read_length@1.0.0` for our code through a format, or
    `genome_length_fai@1.0.0 (nf-core/samtools/faidx@1.21)` for a tool's output parsed."""
    runs: list[str]
    """Where it may run, `server` before `pipeline`."""
    trusted: bool


def _trusted(catalogue: InspectionCatalogue, key: str) -> bool:
    return catalogue.origin.get(key) in settings.trusted_layers


def index(stack) -> list[Measurer]:
    """Every way the stack can measure each measurement, sorted `(measurement, by)`."""
    pieces = stack.inspection
    found = []
    for measurer in pieces.measurers.values():
        mine = _trusted(pieces, f"measurer:{measurer.id}")
        if measurer.by == "tool":
            found.append(Measurer(
                measurement=measurer.measures,
                by=f"{measurer.id}@{measurer.version} ({measurer.uses})",
                runs=list(measurer.runs),
                trusted=mine,
            ))
            continue
        found += [
            Measurer(
                measurement=measurer.measures,
                by=f"{fmt.id}@{fmt.version} + {measurer.id}@{measurer.version}",
                # A format that cannot run on this server takes the server out for both.
                runs=[r for r in measurer.runs if r != "server" or fmt.runs == "server"],
                trusted=mine and _trusted(pieces, f"format:{fmt.id}"),
            )
            for fmt in pieces.formats.values()
            if fmt.record == measurer.record
        ]
    return sorted(found, key=lambda m: (m.measurement, m.by))


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
        # Only our code runs here, and only a measurer that says it runs on the server (#465).
        measurers={k: m for k, m in keep("measurer", pieces.measurers).items()
                   if m.runs_on("server")},
        origin=pieces.origin,
    )

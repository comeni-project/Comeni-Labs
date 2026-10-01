"""Codecs, formats and measures: the pieces an inspection is composed from (#134).

An uploaded sample's head is measured by **composing** pieces rather than by one inspector per
file type: a codec opens the bytes (`gzip`), a format turns them into records (`fastq`), and
each measure folds those records into one fact (`read_length`). A new compression is one codec,
a new format one format, a new fact one measure — so the number of pieces grows with the
number of ideas, not with their product. Spec §3–§4.

**A piece is declared data with code beside it.** The declaration is a file like any other kind
(`declares: format`, invariant 11); the code, its tests and its fixtures sit in `piece/` beside
it, which the layer digest covers and the loader never parses — the rule `module/` already
follows (`layered._in_source`).

**Pieces name ids, never check them.** A format names the type it reads and a measure the
measurement it produces, as strings. `InspectionCatalogue.check` holds them to the vocabulary
(invariant 7): a piece naming an id no layer declares is refused, `MD0317`, and the others stay.
"""

from collections.abc import Sequence
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from comeni_core import yaml_strict
from comeni_core.declared.layered import DeclaredKind, Kind, Policy, Stacked, layers_of, stack
from comeni_core.diagnostics import coded

_ID = r"^[a-z0-9_]+$"
_VERSION = r"^\d+\.\d+\.\d+$"
_ENTRY = r"^piece/[^.][^/]*(/[^./][^/]*)*$"


class _Piece(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str = Field(pattern=_ID, max_length=64)
    """The piece's folder name; on a fact it is `f"{id}@{version}"`."""
    version: str = Field(pattern=_VERSION)
    impl: Literal["python", "executable"] = "python"
    """`executable` leaves room for a Rust or C piece behind the same wire protocol (spec §4)."""
    entry: str = Field(pattern=_ENTRY)
    """The code, relative to the declaration, always inside `piece/`."""
    needs: list[str] = Field(default_factory=list)


class CodecPiece(_Piece):
    """Opens bytes: `gzip`. Matched by extension, confirmed by magic bytes."""

    extensions: list[str]
    magic: list[str] = Field(default_factory=list)
    """Hex prefixes, `1f8b` for gzip."""


class FormatPiece(_Piece):
    """Turns opened bytes into records: `fastq`."""

    reads: list[str] = Field(min_length=1)
    """The type ids this format confirms a file is."""
    extensions: list[str]
    record: Literal["sequence"]
    runs: Literal["server", "lab", "browser"] = "server"
    """Where it runs. Only `server` is built; the others are where a heavier one will go."""
    files: str = "1..2"


class MeasurePiece(_Piece):
    """Folds records into one fact: `read_length`."""

    measures: str
    """The measurement id the fact is for."""
    record: Literal["sequence"]
    decided: dict[str, float | int] = Field(default_factory=dict)
    """The thresholds this piece decides by, recorded on every fact it produces (spec §5)."""


def _parser(model: type[_Piece]):
    def parse(path: Path) -> list[_Piece]:
        """One piece per file. `declares:` is accepted and ignored, as `_parse_family` does."""
        data = yaml_strict.load(path) or {}
        data.pop("declares", None)
        return [model.model_validate(data)]

    return parse


class InspectionCatalogue(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    codecs: dict[str, CodecPiece] = Field(default_factory=dict)
    formats: dict[str, FormatPiece] = Field(default_factory=dict)
    measures: dict[str, MeasurePiece] = Field(default_factory=dict)

    @staticmethod
    def kinds() -> tuple[Kind, Kind, Kind]:
        """Keyed on the piece id; a higher layer replaces a lower one's piece whole."""
        return (
            Kind(DeclaredKind.CODECS, parse=_parser(CodecPiece), key=lambda p: p.id,
                 policy=Policy.REPLACE),
            Kind(DeclaredKind.FORMATS, parse=_parser(FormatPiece), key=lambda p: p.id,
                 policy=Policy.REPLACE),
            Kind(DeclaredKind.MEASURES, parse=_parser(MeasurePiece), key=lambda p: p.id,
                 policy=Policy.REPLACE),
        )

    @classmethod
    def of(cls, codecs: Stacked, formats: Stacked, measures: Stacked) -> "InspectionCatalogue":
        return cls(
            codecs=dict(codecs.entries),
            formats=dict(formats.entries),
            measures=dict(measures.entries),
        )

    @classmethod
    def load(cls, layers: Path | Sequence[Path]) -> "InspectionCatalogue":
        """Load the pieces across a layer stack. **Layer roots**, as for every kind."""
        roots = layers_of(layers)
        return cls.of(*(stack(roots, kind) for kind in cls.kinds()))

    def check(
        self, type_ids: set[str], measurement_ids: set[str]
    ) -> "tuple[InspectionCatalogue, list[str]]":
        """Drop every piece that names vocabulary the registry does not declare (invariant 7).

        **One bad piece does not stop the others.** A refused piece is reported, never loaded,
        so its files go to the characteriser like any type nothing reads.
        """
        refused: list[str] = []
        formats = {}
        for key, piece in self.formats.items():
            unknown = sorted(set(piece.reads) - type_ids)
            if unknown:
                refused.append(
                    coded(
                        "MD0317",
                        f"format {key}@{piece.version} reads {', '.join(unknown)}, "
                        "which no layer declares",
                    )
                )
            else:
                formats[key] = piece
        measures = {}
        for key, piece in self.measures.items():
            if piece.measures not in measurement_ids:
                refused.append(
                    coded(
                        "MD0317",
                        f"measure {key}@{piece.version} produces {piece.measures}, "
                        "which no layer declares",
                    )
                )
            else:
                measures[key] = piece
        usable = InspectionCatalogue(codecs=self.codecs, formats=formats, measures=measures)
        return usable, refused

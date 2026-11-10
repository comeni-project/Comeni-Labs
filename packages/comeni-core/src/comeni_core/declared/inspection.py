"""Declare the codecs, formats and measurers: everything that measures data (#465).

A codec opens bytes and a format produces records. A **measurer** produces one measurement, in one
of two ways: our own code folding a format's records (`by: code`), or a tool in the registry plus
a parser for one of its outputs (`by: tool`). Each says where it may run: on the server over an
upload's head, in the pipeline over all the data, or both. Each piece points to code under its
declaration's ``piece/`` directory. Catalogue validation removes pieces with missing code, missing
dependencies, or references to undeclared types, measurements or tools.
"""

from collections.abc import Sequence
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, PrivateAttr, field_validator, model_validator

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
    """How the inspection runner invokes the piece."""
    entry: str = Field(pattern=_ENTRY)
    """The code, relative to the declaration, always inside `piece/`."""
    needs: list[str] = Field(default_factory=list)
    """Other pieces, by id, that must be loaded for this one to run."""
    _folder: Path | None = PrivateAttr(default=None)
    """The folder its declaration was read from: set by the loader, never declared."""

    @property
    def folder(self) -> Path | None:
        """Where the declaration was read from, when it was read from a file."""
        return self._folder

    def problems(self) -> list[str]:
        """Return filesystem problems that would prevent a loaded piece from running."""
        if self._folder is None:
            return []
        found = []
        if self._folder.name != self.id:
            found.append(f"its id is {self.id!r} but its folder is {self._folder.name!r}")
        if not (self._folder / self.entry).is_file():
            found.append(f"its entry {self.entry} is not there")
        return found


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
    """How many files one sample of this format is, as `<least>..<most>`: `1..2`, a file or a
    pair. The runner refuses a sample outside it."""

    @field_validator("files")
    @classmethod
    def _a_range(cls, files: str) -> str:
        least, _, most = files.partition("..")
        if not (least.isdigit() and most.isdigit() and 1 <= int(least) <= int(most)):
            raise ValueError(f"files is {files!r}; write it as <least>..<most>, like 1..2")
        return files

    @property
    def file_counts(self) -> tuple[int, int]:
        least, _, most = self.files.partition("..")
        return int(least), int(most)


Runner = Literal["server", "pipeline"]
"""Where a measurer runs: `server`, over an upload's head, sandboxed, trusted layers only; or
`pipeline`, as a step over all the data during the run."""


class Measurer(_Piece):
    """Produces one measurement: `read_length` by our code, `genome_length` by samtools faidx and
    a parser of its `.fai`."""

    measures: str
    """The measurement id the fact is for."""
    by: Literal["code", "tool"]
    """`code`: an `Accumulator` over a format's records. `tool`: `parse(stream, decided)` over
    the output port `output` of the contract `uses`."""
    record: Literal["sequence"] | None = None
    """For `by: code`, the record shape it reads; formats of that shape feed it."""
    uses: str | None = None
    """For `by: tool`, the contract id of the tool whose output is parsed."""
    output: str | None = None
    """For `by: tool`, the output port of `uses` the parser reads."""
    decided: dict[str, float | int] = Field(default_factory=dict)
    """Thresholds recorded with every fact this piece produces."""
    runs: list[Runner]

    @field_validator("runs")
    @classmethod
    def _canonical(cls, runs: list[str]) -> list[str]:
        """Sorted and once each, so one meaning has one spelling in every dump."""
        return sorted(set(runs), key=["server", "pipeline"].index)

    @model_validator(mode="after")
    def _one_way(self) -> "Measurer":
        problems = []
        if not self.runs:
            problems.append("it runs nowhere: list `server`, `pipeline` or both in `runs`")
        if self.by == "code":
            if self.record is None:
                problems.append("`by: code` reads a format's records, so it needs `record:`")
            if self.uses is not None or self.output is not None:
                problems.append("`by: code` runs our own code; `uses:` and `output:` are for "
                                "`by: tool`")
        else:
            if self.record is not None:
                problems.append("`by: tool` parses a tool's output, not records; drop `record:`")
            if self.uses is None or self.output is None:
                problems.append("`by: tool` needs `uses:` (the tool's contract id) and "
                                "`output:` (the port its parser reads)")
            if "server" in self.runs:
                problems.append("a tool runs only in the lab's pipeline; drop `server` from "
                                "`runs`")
        if problems:
            raise ValueError(coded("MD0326", f"measurer {self.id}: " + "; ".join(problems)))
        return self

    def runs_on(self, where: Runner) -> bool:
        return where in self.runs


def _parser(model: type[_Piece]):
    def parse(path: Path) -> list[_Piece]:
        """One piece per file. `declares:` is accepted and ignored, as `_parse_family` does."""
        data = yaml_strict.load(path) or {}
        data.pop("declares", None)
        piece = model.model_validate(data)
        piece._folder = path.parent
        return [piece]

    return parse


class InspectionCatalogue(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    codecs: dict[str, CodecPiece] = Field(default_factory=dict)
    formats: dict[str, FormatPiece] = Field(default_factory=dict)
    measurers: dict[str, Measurer] = Field(default_factory=dict)
    origin: dict[str, int] = Field(default_factory=dict)
    """`"codec:<id>"`, `"format:<id>"`, `"measurer:<id>"` → the index of the layer that supplied
    it. Pieces run only from trusted layers (spec §2), and trust is per layer."""

    @staticmethod
    def kinds() -> tuple[Kind, Kind, Kind]:
        """Keyed on the piece id; a higher layer replaces a lower one's piece whole."""
        return (
            Kind(DeclaredKind.CODECS, parse=_parser(CodecPiece), key=lambda p: p.id,
                 policy=Policy.REPLACE),
            Kind(DeclaredKind.FORMATS, parse=_parser(FormatPiece), key=lambda p: p.id,
                 policy=Policy.REPLACE),
            Kind(DeclaredKind.MEASURERS, parse=_parser(Measurer), key=lambda p: p.id,
                 policy=Policy.REPLACE),
        )

    @classmethod
    def of(cls, codecs: Stacked, formats: Stacked, measurers: Stacked) -> "InspectionCatalogue":
        origin = {
            f"{kind}:{key}": index
            for kind, stacked in (("codec", codecs), ("format", formats),
                                  ("measurer", measurers))
            for key, index in stacked.origin.items()
        }
        return cls(
            codecs=dict(codecs.entries),
            formats=dict(formats.entries),
            measurers=dict(measurers.entries),
            origin=origin,
        )

    @classmethod
    def load(cls, layers: Path | Sequence[Path]) -> "InspectionCatalogue":
        """Load the pieces across a layer stack. **Layer roots**, as for every kind."""
        roots = layers_of(layers)
        return cls.of(*(stack(roots, kind) for kind in cls.kinds()))

    def check(
        self, type_ids: set[str], measurement_ids: set[str]
    ) -> "tuple[InspectionCatalogue, list[str]]":
        """Return runnable pieces and diagnostics for every refused piece.

        A bad piece does not prevent independent pieces from remaining available.
        """
        refused: list[str] = []
        known = set(self.codecs) | set(self.formats) | set(self.measurers)

        def runnable(kind: str, key: str, piece: _Piece) -> bool:
            problems = piece.problems() + [
                f"it needs {need}, which no layer declares"
                for need in piece.needs
                if need not in known
            ]
            for problem in problems:
                refused.append(
                    coded("MD0318", f"{kind} {key}@{piece.version} cannot run: {problem}")
                )
            return not problems

        codecs = {k: p for k, p in self.codecs.items() if runnable("codec", k, p)}
        formats = {}
        for key, piece in self.formats.items():
            if not runnable("format", key, piece):
                continue
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
        measurers = {}
        for key, piece in self.measurers.items():
            if not runnable("measurer", key, piece):
                continue
            if piece.measures not in measurement_ids:
                refused.append(
                    coded(
                        "MD0317",
                        f"measurer {key}@{piece.version} produces {piece.measures}, "
                        "which no layer declares",
                    )
                )
            else:
                measurers[key] = piece
        usable = InspectionCatalogue(
            codecs=codecs, formats=formats, measurers=measurers, origin=self.origin
        )
        return usable, refused

    def check_tools(self, registry) -> "tuple[InspectionCatalogue, list[str]]":
        """Drop each `by: tool` measurer whose tool or output port is not in the stack.

        Run once the registry is assembled, since a measurer may use a tool another layer
        supplies. As for MD0317, the piece is not loaded and the others are.
        """
        refused: list[str] = []
        kept = {}
        for key, piece in self.measurers.items():
            if piece.by == "tool":
                try:
                    contract = registry.get(piece.uses)
                except KeyError:
                    refused.append(coded(
                        "MD0327",
                        f"measurer {key}@{piece.version} uses {piece.uses}, which no layer "
                        "declares"))
                    continue
                ports = sorted(port.name for port in contract.produces)
                if piece.output not in ports:
                    refused.append(coded(
                        "MD0327",
                        f"measurer {key}@{piece.version} parses the output {piece.output!r} "
                        f"of {piece.uses}, which has the outputs {', '.join(ports) or 'none'}"))
                    continue
            kept[key] = piece
        return self.model_copy(update={"measurers": kept}), refused

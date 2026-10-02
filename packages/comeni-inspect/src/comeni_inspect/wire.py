"""The wire protocol between the API and an inspection process (spec §6, `PROTOCOL.md`).

A request is **one JSON line** followed by each file's bytes back to back, their lengths in the
request. The answer is one JSON report on stdout, keys sorted, so a golden report compares byte
for byte and an implementation in another language is checked against the same files.
"""

import json
from typing import BinaryIO

from pydantic import BaseModel, ConfigDict, Field


class PieceRef(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    version: str
    path: str
    """The piece's entry file, absolute."""
    decided: dict[str, float | int] = Field(default_factory=dict)


class FileHead(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str
    length: int = Field(ge=0)


class Request(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    format: PieceRef
    codec: PieceRef | None
    measures: list[PieceRef]
    files: list[FileHead]
    cap_bytes: int = Field(gt=0)
    """The most a file may unpack to; past it the inspection is `too large unpacked`."""


class Fact(BaseModel):
    model_config = ConfigDict(extra="forbid")

    by: list[str]
    """The pieces that produced it, `fastq@1.0.0` then `read_length@1.0.0`."""
    value: int | float | bool | str | None = None
    undetermined: str | None = None
    evidence: dict = Field(default_factory=dict)


class Report(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type_id: str | None = None
    facts: dict[str, Fact] = Field(default_factory=dict)
    unreadable: str | None = None

    def to_json(self) -> str:
        """Keys sorted and `None` left out, so the same report is the same bytes."""
        return json.dumps(self.model_dump(exclude_none=True), sort_keys=True)


def write_request(stream: BinaryIO, request: Request, payloads: list[bytes]) -> None:
    stream.write(request.model_dump_json().encode() + b"\n")
    for payload in payloads:
        stream.write(payload)


def read_request(stream: BinaryIO) -> tuple[Request, list[bytes]]:
    """The request and its files. **A payload shorter than declared is refused**: a pipe closed
    early must not become a file that is quietly shorter than the person's."""
    request = Request.model_validate_json(stream.readline())
    payloads = []
    for head in request.files:
        payload = stream.read(head.length)
        if len(payload) != head.length:
            raise ValueError(f"{head.name}: {len(payload)} of {head.length} bytes arrived")
        payloads.append(payload)
    return request, payloads

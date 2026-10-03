"""Read an uploaded sample's heads off the request stream: the first bytes of each file, kept in
memory, and the rest read through and dropped (14.7.6.4).

**Why not FastAPI's `UploadFile`.** Starlette spools every uploaded file to a temporary file once
it passes 1 MB, after receiving all of it, before the route runs. That writes the person's file to
this server's disk, which 14.7.6's ruling says never happens (nothing deletes a session yet, so
nothing about a sample is kept), and it buffers a 2 GB file to keep 4 MB of it. This parser
streams the body through `python-multipart` and holds at most `head` bytes per file.
"""

import asyncio
from dataclasses import dataclass, field

from python_multipart.multipart import MultipartParser, parse_options_header
from starlette.requests import ClientDisconnect, Request

READ_TIMEOUT_S = 30.0
"""The longest the body may go without a byte arriving before the upload is given up on: a body
that never finishes held its request open for ever (issue 226)."""
FIELD_CAP = 256
"""A form field (the proposal id) is an id, never prose: more than this is dropped."""
FILES = "files"
"""The one field a file is read from."""
FIELDS = frozenset({"proposal_id"})
"""The only form field this route reads. **Any other is refused**, not held: a body of 100,000
distinct field names held 200 MB before this (review of #134)."""


class BadUpload(ValueError):
    """The body is not a multipart form this route can read."""


@dataclass
class Heads:
    fields: dict[str, str] = field(default_factory=dict)
    files: list[tuple[str, bytes]] = field(default_factory=list)
    """`(file name, its first bytes)`, at most `keep` files; `count` counts them all."""
    count: int = 0


async def read_heads(request: Request, *, head: int, keep: int = 2) -> Heads:
    """Every file part counted; the first `keep` files' first `head` bytes kept."""
    kind, options = parse_options_header(request.headers.get("content-type"))
    boundary = options.get(b"boundary")
    if kind != b"multipart/form-data" or not boundary:
        raise BadUpload("send the sample as multipart/form-data")

    heads = Heads()
    part: dict = {}
    header = {"field": b"", "value": b""}

    def on_part_begin() -> None:
        part.clear()
        part.update(headers={}, data=bytearray(), cap=FIELD_CAP)

    def on_header_field(data: bytes, start: int, end: int) -> None:
        header["field"] += data[start:end]

    def on_header_value(data: bytes, start: int, end: int) -> None:
        header["value"] += data[start:end]

    def on_header_end() -> None:
        part["headers"][header["field"].lower()] = header["value"]
        header["field"], header["value"] = b"", b""

    def on_headers_finished() -> None:
        _, disposition = parse_options_header(part["headers"].get(b"content-disposition"))
        part["name"] = disposition.get(b"name", b"").decode(errors="replace")
        filename = disposition.get(b"filename")
        part["filename"] = None if filename is None else filename.decode(errors="replace")
        if part["filename"] == "":
            # An empty file input in a browser form: no file was chosen (issue 226).
            part["filename"], part["skip"], part["cap"] = None, True, 0
        elif part["filename"] is not None:
            if part["name"] != FILES:
                raise BadUpload(f"a file was sent under a field this route does not read: "
                                f"{part['name']!r}; send it as {FILES!r}")
            heads.count += 1
            part["cap"] = head if heads.count <= keep else 0
        elif not part.get("skip") and part["name"] not in FIELDS:
            raise BadUpload(f"the form has a field this route does not read: {part['name']!r}")

    def on_part_data(data: bytes, start: int, end: int) -> None:
        room = part["cap"] - len(part["data"])
        if room > 0:
            part["data"] += data[start : min(end, start + room)]

    def on_part_end() -> None:
        part["ended"] = True
        if part.get("skip"):
            return
        if part.get("filename") is not None:
            if heads.count <= keep:
                heads.files.append((part["filename"] or "sample", bytes(part["data"])))
        elif part.get("name"):
            heads.fields[part["name"]] = part["data"].decode(errors="replace")

    parser = MultipartParser(
        boundary,
        {
            "on_part_begin": on_part_begin,
            "on_header_field": on_header_field,
            "on_header_value": on_header_value,
            "on_header_end": on_header_end,
            "on_headers_finished": on_headers_finished,
            "on_part_data": on_part_data,
            "on_part_end": on_part_end,
        },
    )
    chunks = request.stream().__aiter__()
    while True:
        try:
            chunk = await asyncio.wait_for(anext(chunks), READ_TIMEOUT_S)
        except StopAsyncIteration:
            break
        except TimeoutError:
            raise BadUpload("the upload stopped arriving; send it again") from None
        except ClientDisconnect:
            raise BadUpload("the upload stopped before it finished; send it again") from None
        parser.write(chunk)
    parser.finalize()
    # **A body cut before its closing boundary** ends with a part that never ended: its bytes
    # are not a file, and answering *nothing reads this type* would be untrue (review of #134).
    if part and not part.get("ended"):
        raise BadUpload("the upload stopped before it finished; send it again")
    return heads

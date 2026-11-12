"""Read an uploaded sample's heads off the request stream: the first bytes of each file, kept in
memory, and the rest read through and dropped (14.7.6.4).

**Why not FastAPI's `UploadFile`.** Starlette spools every uploaded file to a temporary file once
it passes 1 MB, after receiving all of it, before the route runs. That writes the person's file to
this server's disk, which 14.7.6's ruling says never happens (nothing deletes a session yet, so
nothing about a sample is kept), and it buffers a 2 GB file to keep 4 MB of it. This parser
streams the body through `python-multipart` and holds at most `head` bytes per file.
"""

import asyncio
import re
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
FIELDS = frozenset({"proposal_id", "sizes"})
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


async def read_heads(request: Request, *, head: int, keep: int | None = None) -> Heads:
    """Every file part counted; the first `head` bytes of each kept, of the first `keep` files
    or, by default, of every file: an upload may hold hundreds of samples (#466)."""
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
            part["cap"] = head if keep is None or heads.count <= keep else 0
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
            if keep is None or heads.count <= keep:
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


def sizes_of(field: str | None, files: int) -> tuple[int, ...]:
    """The `sizes` field: a JSON list of each file's real size, one per file. Anything else is
    no sizes at all, so the files are heads, which is the safe reading (#465)."""
    import json

    try:
        sizes = json.loads(field) if field else None
    except ValueError:
        return ()
    if (not isinstance(sizes, list) or len(sizes) != files
            or not all(isinstance(n, int) and not isinstance(n, bool) and n >= 0 for n in sizes)):
        return ()
    return tuple(sizes)


_MATE = re.compile(
    r"^(?P<stem>.+?)(?P<sep>[._])(?P<mate>[Rr]?[12])(?P<tail>_\d+)?(?P<rest>(\.[^.]+)*)$")
"""A mate's name: a stem, `_` or `.`, `R1`/`R2` or `1`/`2` (any case), Illumina's `_001` if
there, then any extension (stage 2 review: bcl2fastq names, lowercase, none at all)."""

_COMPRESSED = (".gz", ".bz2", ".zst")


def _mate_key(name: str):
    """What two mates share: stem, separator, `R` or not, Illumina tail, and extension without
    its compression; `None` for a name with no mate token."""
    found = _MATE.match(name)
    if found is None:
        return None
    rest = found["rest"].lower()
    for suffix in _COMPRESSED:
        rest = rest.removesuffix(suffix)
    return (found["stem"], found["sep"], found["mate"][0] in "Rr", found["tail"] or "", rest)


@dataclass(frozen=True)
class Sample:
    """One sample of an upload: a file, or a pair of mates (#466)."""

    name: str
    files: tuple[tuple[str, bytes], ...]
    sizes: tuple[int, ...] = ()


def samples_of(files: list[tuple[str, bytes]], sizes: tuple[int, ...]) -> list[Sample]:
    """The upload's files as samples, in the order they came: two files whose names differ
    only in a mate token (`_R1`/`_R2`, `_1`/`_2`, `.R1`/`.R2`, any case, Illumina's `_001`
    after it, compression aside) are one sample named by their shared stem; any other file is a
    sample of its own, named by its stem. Two files alone are one sample, as an upload of two
    always was. A name given twice is numbered (`a#2`)."""
    known = len(sizes) == len(files)
    if len(files) == 2 and _mate_key(files[0][0]) is None and _mate_key(files[1][0]) is None:
        return [_sample(_stem(files[0][0]), files, sizes, [0, 1], known)]
    keyed: dict[tuple, list[int]] = {}
    order: list[tuple] = []
    for index, (name, _) in enumerate(files):
        key = _mate_key(name) or ("file", index)
        if key not in keyed:
            keyed[key] = []
            order.append(key)
        keyed[key].append(index)
    samples: list[Sample] = []
    taken: set[str] = set()
    for key in order:
        indexes = keyed[key]
        mates = (key[0] != "file" and len(indexes) == 2
                 and {_MATE.match(files[i][0])["mate"][-1] for i in indexes} == {"1", "2"})
        for group in ([indexes] if mates else [[i] for i in indexes]):
            name = key[0] if mates else _stem(files[group[0]][0])
            unique, n = name, 1
            while unique in taken:
                n += 1
                unique = f"{name}#{n}"
            taken.add(unique)
            samples.append(_sample(unique, files, sizes, group, known))
    return samples


def _stem(name: str) -> str:
    return name.split(".", 1)[0] if "." in name else name


def _sample(name: str, files, sizes, group: list[int], known: bool) -> Sample:
    ordered = sorted(group, key=lambda i: files[i][0])
    return Sample(name=name, files=tuple(files[i] for i in ordered),
                  sizes=tuple(sizes[i] for i in ordered) if known else ())

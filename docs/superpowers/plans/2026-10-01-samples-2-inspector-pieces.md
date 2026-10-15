# Samples 2 — inspector pieces: codecs, formats, measures — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A FASTQ head (plain or gzipped, one file or a pair) goes into one process and comes out as a report — `read_length`, `paired`, `quality_encoding`, each a value with its evidence or *undetermined* with a reason — from pieces that live in the registry, are written once, and are composed at run time.

**Architecture:** Three new declared kinds (`codec`, `format`, `measure`) in `comeni-core`, loaded through `layers.load()` like every kind, with each piece's code in a `piece/` folder beside its declaration (the `module/` rule: covered by the layer digest, never parsed as declarations). A new package, `comeni-inspect`, holds the record shapes, the accumulator contract, the wire protocol and the runner: one inspection per process, request on stdin, one JSON report out, one streamed pass that feeds every measure. The first pieces — `gzip`, `fastq`, `read_length`, `paired`, `quality_encoding` — land in the registry. Launching the runner with limits from the API is part 4.

**Tech Stack:** Python 3.12 standard library (`gzip`, `zlib`, `json`, `importlib`), pydantic 2, pytest.

**Spec:** `docs/superpowers/specs/2026-10-01-samples-and-inspectors-design.md` §3 (*Inspector code in the registry*), §4, §5, §6, §7. Part 14.7.6.2 of #134.

## Global Constraints

- **Pieces import only a closed allowlist:** `comeni_inspect`, `gzip`, `zlib`, `io`, `re`, `math`, `collections`, `collections.abc`, `typing`. No network, no file reads, no subprocesses. Guarded by a closed allowlist, the shape `tests/guards/test_purity.py` uses for `comeni-core`.
- **Never an exception out of an inspection.** Every outcome is a report: facts (each a value with evidence, or undetermined with a reason) or `Unreadable` with a reason.
- **Nothing guessed:** a measure below its declared threshold returns undetermined. File names never decide `paired` (spec §5).
- **One pass, the whole head:** the format yields records once; every measure is fed from that stream; no early stop (spec §4, decided B).
- **Ids are names only:** pieces name type and measurement ids as strings; whether they exist is checked by Comeni (Task 1's `check`), never assumed by a piece.
- **The registry stays the registry:** pieces go on the `one-folder-per-tool` branch of `comeni-registry` (or its successor), pushed only with the operator's say-so.
- Comments and docstrings match the repository's style. A loop is not an assertion: assert non-empty first.

## Review Focus

1. **A pair whose files have different record counts** (R2 truncated by the 4 MB cut): the side-by-side read must stop at the shorter file and say so in the evidence, not report `paired: no`. Pinned in Task 5.
2. **CRLF line endings** (a FASTQ written on Windows): records must parse, and read lengths must not count the `\r`. Pinned in Task 4.
3. **A head cut mid-record** (always true of a 4 MB head): the trailing partial record is dropped, never an error and never a short read counted. Pinned in Task 4.
4. **A gzip head cut mid-stream** (also always true of a head): decompression yields what it can and stops cleanly; only a corrupt stream is `Unreadable`. Pinned in Task 3.
5. **A FASTA file named `.fastq`**: the format's content check refuses it and the inspection is `Unreadable: named .fastq, but does not start like one`. Pinned in Task 4.

---

## File structure

| File | Responsibility |
|---|---|
| Create `packages/comeni-core/src/comeni_core/declared/inspection.py` | `CodecPiece`, `FormatPiece`, `MeasurePiece`, `InspectionCatalogue` (+ `check`) |
| Modify `packages/comeni-core/src/comeni_core/declared/layered.py` | three kinds; `PIECE_DIR`; `_in_module` → `_in_source` covering `piece/` |
| Modify `packages/mendel-resolver/src/mendel_resolver/layers.py` | `Layers.inspection` |
| Create `packages/comeni-core/tests/test_inspection_kinds.py` | the kinds and `check` |
| Create `packages/comeni-inspect/` (`pyproject.toml`, `README.md`, `LICENSE`, `PROTOCOL.md`, `src/comeni_inspect/{__init__,records,outcome,wire,run,harness}.py`) | the interface, the runner, the conformance harness |
| Create `packages/comeni-inspect/tests/test_wire.py`, `test_run.py` | the protocol and the runner over a toy piece |
| Modify root `pyproject.toml` | `comeni-inspect` in `dependencies` and `[tool.uv.sources]`; `registry/inspectors` in `testpaths` |
| In `registry/inspectors/`: `codecs/gzip/`, `formats/fastq/`, `measures/{read_length,paired,quality_encoding}/` | each `<kind>.yml` + `piece/` (code, tests, fixtures) |
| Create `tests/guards/test_inspector_pieces.py` | every piece: declaration, fixtures, tests, the import allowlist, never an exception, declared outputs only |
| Create `tests/registry/test_inspection_conformance.py` | every fixture case against its golden report; the speed budget |

---

### Task 1: Three declared kinds, and piece code beside its declaration

**Files:**
- Create: `packages/comeni-core/src/comeni_core/declared/inspection.py`
- Modify: `packages/comeni-core/src/comeni_core/declared/layered.py`
- Modify: `packages/mendel-resolver/src/mendel_resolver/layers.py`
- Modify: `packages/comeni-core/src/comeni_core/diagnostics.yml` (MD0317)
- Test: `packages/comeni-core/tests/test_inspection_kinds.py`

**Interfaces:**
- Produces:
  - `CodecPiece(id, version, extensions: list[str], magic: list[str] (hex), impl: Literal["python","executable"]="python", entry: str, needs: list[str]=[])`
  - `FormatPiece(id, version, reads: list[str], extensions: list[str], record: Literal["sequence"], runs: Literal["server","lab","browser"]="server", files: str = "1..2", impl, entry, needs)`
  - `MeasurePiece(id, version, measures: str, record: Literal["sequence"], decided: dict[str, float | int], impl, entry, needs)`
  - `InspectionCatalogue(codecs: dict, formats: dict, measures: dict)` with `.check(type_ids: set[str], measurement_ids: set[str]) -> tuple[InspectionCatalogue, list[str]]` returning the usable catalogue and one coded **MD0317** message per refused piece.
  - `DeclaredKind.CODECS="codecs"`, `FORMATS="formats"`, `MEASURES="measures"`; singulars `codec`, `format`, `measure`; `layered.PIECE_DIR = "piece"`; `Layers.inspection: InspectionCatalogue` (already checked: refused pieces are absent, and `Layers.refused_pieces: list[str]` holds the messages).
- A piece's `id` is its folder name; its identity on a fact is `f"{id}@{version}"`.

- [x] **Step 1: Write the failing tests**

```python
# packages/comeni-core/tests/test_inspection_kinds.py
"""Codecs, formats and measures as declared data; their code beside them in `piece/`."""

from comeni_core.declared.inspection import InspectionCatalogue
from comeni_core.declared.layered import declared_entries


def _write(root, rel, text=""):
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return path


FASTQ = (
    "declares: format\nid: fastq\nversion: 1.0.0\nreads: [fastq.reads]\n"
    "extensions: [.fastq, .fq]\nrecord: sequence\nentry: piece/fastq.py\n"
)
READ_LENGTH = (
    "declares: measure\nid: read_length\nversion: 1.0.0\nmeasures: read_length\n"
    "record: sequence\ndecided: {min_records: 1000, modal_share: 0.8}\nentry: piece/read_length.py\n"
)


def test_pieces_load_and_their_code_is_not_parsed(tmp_path):
    _write(tmp_path, "inspectors/formats/fastq/format.yml", FASTQ)
    _write(tmp_path, "inspectors/formats/fastq/piece/fastq.py", "x = 1\n")
    _write(tmp_path, "inspectors/formats/fastq/piece/fixtures/notes.yml", "not: declared\n")
    catalogue = InspectionCatalogue.load(tmp_path)
    assert list(catalogue.formats) == ["fastq"]


def test_piece_code_is_in_the_layer_digest(tmp_path):
    """The `module/` rule: code a layer carries is covered by what a pipeline pins."""
    code = _write(tmp_path, "inspectors/formats/fastq/piece/fastq.py", "x = 1\n")
    assert code in declared_entries(tmp_path)


def test_a_piece_naming_an_unknown_id_is_refused_and_the_rest_stay(tmp_path):
    _write(tmp_path, "inspectors/formats/fastq/format.yml", FASTQ)
    _write(tmp_path, "inspectors/measures/read_length/measure.yml", READ_LENGTH)
    _write(
        tmp_path, "inspectors/measures/gc/measure.yml",
        READ_LENGTH.replace("id: read_length", "id: gc").replace("measures: read_length", "measures: gc_content"),
    )
    usable, refused = InspectionCatalogue.load(tmp_path).check(
        type_ids={"fastq.reads"}, measurement_ids={"read_length"}
    )
    assert sorted(usable.measures) == ["read_length"]
    assert len(refused) == 1 and "MD0317" in refused[0] and "gc_content" in refused[0]
```

- [x] **Step 2: Run them to see them fail**

Run: `uv run pytest packages/comeni-core/tests/test_inspection_kinds.py -q`
Expected: FAIL — no module `comeni_core.declared.inspection`.

- [x] **Step 3: Implement**

`layered.py`: add `CODECS`, `FORMATS`, `MEASURES` to `DeclaredKind` (one-line docstrings: *"A piece of an inspection — `comeni_core.declared.inspection` (#134)."*), the singulars to `_KIND_OF`, and generalise the source rule:

```python
PIECE_DIR = "piece"
"""An inspector piece's own code, tests and fixtures, beside the declaration that names it."""


def _in_source(path: Path, root: Path) -> bool:
    """Is this file code a layer carries rather than a declaration about it?

    `module/` (a tool's source) and, since #134, `piece/` (an inspector piece's code, tests and
    fixtures). Same two answers for the same two callers: the digest covers everything here,
    the loader parses nothing here.
    """
    parts = path.relative_to(root).parts
    return MODULE_DIR in parts or PIECE_DIR in parts
```

Rename `_in_module` to `_in_source` at its call sites (grep `_in_module`), keeping its long docstring on the new function and adding the paragraph above.

`inspection.py`: pydantic models as in Interfaces, `extra="forbid", frozen=True`; `id` matches `^[a-z0-9_]+$`; `version` matches `^\d+\.\d+\.\d+$`; `entry` must start with `piece/`. Parsers as `_parse_family` does (pop `declares`). Three `Kind`s keyed on `id`, `Policy.REPLACE`. `InspectionCatalogue.of(codecs, formats, measures)`, `.load(layers)` stacking all three, and:

```python
    def check(self, type_ids: set[str], measurement_ids: set[str]) -> "tuple[InspectionCatalogue, list[str]]":
        """Drop every piece that names vocabulary the registry does not declare (invariant 7).

        **One bad piece does not stop the others.** A refused piece is reported, never loaded,
        so its files go to the characteriser like any type nothing reads.
        """
        refused: list[str] = []
        formats = {}
        for key, piece in self.formats.items():
            unknown = sorted(set(piece.reads) - type_ids)
            if unknown:
                refused.append(coded("MD0317", f"format {key}@{piece.version} reads {', '.join(unknown)}, which no layer declares"))
            else:
                formats[key] = piece
        measures = {}
        for key, piece in self.measures.items():
            if piece.measures not in measurement_ids:
                refused.append(coded("MD0317", f"measure {key}@{piece.version} produces {piece.measures}, which no layer declares"))
            else:
                measures[key] = piece
        return InspectionCatalogue(codecs=self.codecs, formats=formats, measures=measures), refused
```

`diagnostics.yml`: `MD0317` (shape of `MD0316`): says *"an inspector piece names a type or measurement no layer declares"*, `refuses: true`, explain: the piece is not loaded, the others are; declare the id in `vocabulary/` or fix the piece.

`layers.py`: stack the three kinds with the shared `buckets`, then `inspection, refused = InspectionCatalogue.of(...).check(set(vocabulary.types), set(measurements.measurements))` (read the attribute names of `Vocabulary` and `MeasurementRegistry` first), and add `inspection: InspectionCatalogue` and `refused_pieces: list[str] = []` to `Layers`. Displacements of the three kinds join the list.

- [x] **Step 4: Run them, the loader's tests and the diagnostics page**

Run: `uv run python tools/generate_diagnostics_doc.py && uv run pytest packages/comeni-core tests/registry -q`
Expected: PASS. If a test pins `len(DeclaredKind)`, update its number here.

- [x] **Step 5: Commit**

```bash
git add packages/comeni-core packages/mendel-resolver/src/mendel_resolver/layers.py docs/handbook/reference/diagnostics.md
git commit -m "feat(core): codecs, formats and measures as declared kinds, code beside them (#134)"
```

---

### Task 2: `comeni-inspect`: records, outcomes, the wire protocol

**Files:**
- Create: `packages/comeni-inspect/pyproject.toml`, `README.md`, `LICENSE` (copy `packages/comeni-vendor/LICENSE`), `PROTOCOL.md`
- Create: `packages/comeni-inspect/src/comeni_inspect/__init__.py`, `records.py`, `outcome.py`, `wire.py`, `py.typed`
- Modify: root `pyproject.toml`
- Test: `packages/comeni-inspect/tests/test_wire.py`

**Interfaces:**
- Produces:
  - `records.SequenceRecord(name: str, sequence: bytes, quality: bytes | None)` — a frozen dataclass-free `NamedTuple`.
  - `outcome.Value(value: int | float | bool | str, evidence: dict)`; `outcome.Undetermined(reason: str, evidence: dict)`; `outcome.Accumulator` (`Protocol`: `__init__(self, decided: dict, files: list[str])` — `files` are the sample's file names, which a measure may quote in a reason but never decide on, `add(self, row: tuple[SequenceRecord, ...]) -> None`, `result(self) -> Value | Undetermined`).
  - `wire.Request(format: PieceRef, codec: PieceRef | None, measures: list[PieceRef], files: list[FileHead], cap_bytes: int)` where `PieceRef(id, version, path: str, decided: dict = {})` (`path` is the piece's entry file, absolute) and `FileHead(name: str, length: int)`; `wire.write_request(stream, request, payloads: list[bytes])`, `wire.read_request(stream) -> tuple[Request, list[bytes]]`; `wire.Report(type_id: str | None, facts: dict[str, Fact], unreadable: str | None)` with `Fact(by: list[str], value=None, undetermined: str | None = None, evidence: dict)`; `Report.to_json() -> str` (keys sorted, so goldens compare bytes).

- [x] **Step 1: Write the failing test**

```python
# packages/comeni-inspect/tests/test_wire.py
import io

from comeni_inspect import wire


def test_a_request_round_trips_with_its_bytes():
    request = wire.Request(
        format=wire.PieceRef(id="fastq", version="1.0.0", path="/x/fastq.py"),
        codec=None,
        measures=[wire.PieceRef(id="read_length", version="1.0.0", path="/x/rl.py", decided={"min_records": 2})],
        files=[wire.FileHead(name="a_R1.fq", length=3), wire.FileHead(name="a_R2.fq", length=2)],
        cap_bytes=16 * 2**20,
    )
    stream = io.BytesIO()
    wire.write_request(stream, request, [b"abc", b"de"])
    stream.seek(0)
    back, payloads = wire.read_request(stream)
    assert back == request and payloads == [b"abc", b"de"]


def test_a_report_serialises_in_a_stable_order():
    report = wire.Report(type_id="fastq.reads", facts={
        "read_length": wire.Fact(by=["fastq@1.0.0", "read_length@1.0.0"], value=151, evidence={"records": 9, "share": 1.0}),
        "paired": wire.Fact(by=["fastq@1.0.0", "paired@1.0.0"], undetermined="only one file", evidence={}),
    })
    text = report.to_json()
    assert text.index('"paired"') < text.index('"read_length"')
    assert wire.Report.model_validate_json(text) == report
```

- [x] **Step 2: Run it to see it fail**

Run: `uv sync && uv run pytest packages/comeni-inspect -q`
Expected: FAIL (the package does not exist yet; `uv sync` may also fail until Step 3 adds it — then run after Step 3's `pyproject` only).

- [x] **Step 3: Implement**

`pyproject.toml`: copy `comeni-vendor`'s and change `name = "comeni-inspect"`, the description (*"Measure an uploaded sample's head: the records, the accumulators, the wire protocol and the runner"*), `dependencies = ["pydantic>=2.9"]` (no `comeni-core`: a piece imports only this package, and this package needs nothing of ours), `[project.scripts] comeni-inspect = "comeni_inspect.run:main"`, `packages = ["src/comeni_inspect"]`, and drop `[tool.uv.sources]`. Root `pyproject.toml`: add `"comeni-inspect"` to `dependencies` and `comeni-inspect = { workspace = true }` to `[tool.uv.sources]`.

`wire.py`: pydantic models (`extra="forbid"`). The request is **one JSON line** (the `Request`) followed by each file's bytes back to back, lengths from `files[i].length`:

```python
def write_request(stream, request: Request, payloads: list[bytes]) -> None:
    stream.write(request.model_dump_json().encode() + b"\n")
    for payload in payloads:
        stream.write(payload)


def read_request(stream) -> tuple[Request, list[bytes]]:
    request = Request.model_validate_json(stream.readline())
    return request, [stream.read(f.length) for f in request.files]
```

`Report.to_json()` returns `json.dumps(self.model_dump(exclude_none=True), sort_keys=True)`.

`PROTOCOL.md`: the request line's fields, the payloads, the report's fields, exit codes (0 with a report on stdout; anything else, or nothing in time, is `Unreadable` on the caller's side), and *"an implementation in any language is valid if `comeni_inspect.harness` reproduces every golden report byte for byte against it"*. `README.md`: what the package is, in three paragraphs, leading with what a reader gets.

- [x] **Step 4: Run it to see it pass**

Run: `uv sync && uv run pytest packages/comeni-inspect -q`
Expected: PASS.

- [x] **Step 5: Commit**

```bash
git add packages/comeni-inspect pyproject.toml uv.lock
git commit -m "feat(inspect): records, outcomes and the wire protocol (#134)"
```

---

### Task 3: The runner — one pass, every measure, capped decompression

**Files:**
- Create: `packages/comeni-inspect/src/comeni_inspect/run.py`
- Create: `packages/comeni-inspect/src/comeni_inspect/stream.py` (`Capped`, `TooLarge`)
- Test: `packages/comeni-inspect/tests/test_run.py`

**Interfaces:**
- Consumes: Task 2's `wire`, `outcome`, `records`.
- Produces: `run.inspect(request: Request, payloads: list[bytes]) -> Report` (pure, no I/O beyond importing piece files); `run.main()` reads stdin, writes the report to stdout, exits 0. A piece module's contract:
  - codec: `def open(raw: bytes) -> BinaryIO` (a stream; `run` wraps it in `Capped`).
  - format: `def confirms(first: bytes) -> bool` (given up to the first 4 KiB after the codec) and `def records(stream: BinaryIO) -> Iterator[SequenceRecord]`.
  - measure: `class Accumulator` per `outcome.Accumulator`.

- [x] **Step 1: Write the failing tests, over toy pieces written into `tmp_path`**

```python
# packages/comeni-inspect/tests/test_run.py
"""The runner over toy pieces: composition, one pass, every outcome a report."""

import gzip
import textwrap

from comeni_inspect import run, wire

FORMAT = textwrap.dedent('''
    from comeni_inspect.records import SequenceRecord

    def confirms(first):
        return first.startswith(b">")

    def records(stream):
        for line in stream:
            line = line.rstrip(b"\\r\\n")
            if line.startswith(b">"):
                yield SequenceRecord(name=line[1:].decode(), sequence=b"", quality=None)
''')
COUNT = textwrap.dedent('''
    from comeni_inspect.outcome import Undetermined, Value

    class Accumulator:
        def __init__(self, decided, files):
            self.n, self.need = 0, decided["min_records"]
        def add(self, row):
            self.n += len(row)
        def result(self):
            if self.n < self.need:
                return Undetermined(reason=f"only {self.n} records", evidence={"records": self.n})
            return Value(value=self.n, evidence={"records": self.n})
''')
GZIP = "import gzip, io\n\ndef open(raw):\n    return gzip.GzipFile(fileobj=io.BytesIO(raw))\n"


def _request(tmp_path, n=2, codec=False, cap=2**20):
    (tmp_path / "fmt.py").write_text(FORMAT)
    (tmp_path / "count.py").write_text(COUNT)
    (tmp_path / "gz.py").write_text(GZIP)
    return wire.Request(
        format=wire.PieceRef(id="toy", version="1.0.0", path=str(tmp_path / "fmt.py")),
        codec=wire.PieceRef(id="gzip", version="1.0.0", path=str(tmp_path / "gz.py")) if codec else None,
        measures=[wire.PieceRef(id="count", version="1.0.0", path=str(tmp_path / "count.py"), decided={"min_records": n})],
        files=[], cap_bytes=cap,
    )


def _with(request, *payloads):
    files = [wire.FileHead(name=f"f{i}", length=len(p)) for i, p in enumerate(payloads)]
    return request.model_copy(update={"files": files}), list(payloads)


def test_every_record_reaches_the_measure(tmp_path):
    report = run.inspect(*_with(_request(tmp_path), b">a\n>b\n>c\n"))
    fact = report.facts["count"]
    assert fact.value == 3 and fact.by == ["toy@1.0.0", "count@1.0.0"]


def test_below_the_threshold_is_undetermined(tmp_path):
    report = run.inspect(*_with(_request(tmp_path, n=10), b">a\n"))
    assert report.facts["count"].undetermined == "only 1 records"


def test_content_that_does_not_confirm_is_unreadable(tmp_path):
    report = run.inspect(*_with(_request(tmp_path), b"@a\nACGT\n"))
    assert report.unreadable and "does not start like" in report.unreadable


def test_a_gzip_cut_mid_stream_yields_what_it_can(tmp_path):
    whole = gzip.compress(b">a\n" * 5000)
    report = run.inspect(*_with(_request(tmp_path, codec=True), whole[: len(whole) // 2]))
    assert report.unreadable is None and report.facts["count"].value > 0


def test_a_bomb_is_unreadable_not_a_crash(tmp_path):
    bomb = gzip.compress(b">" + b"A" * (8 * 2**20))
    report = run.inspect(*_with(_request(tmp_path, codec=True, cap=2**20), bomb))
    assert report.unreadable == "too large unpacked"


def test_a_piece_that_raises_is_unreadable(tmp_path):
    request = _request(tmp_path)
    (tmp_path / "count.py").write_text("class Accumulator:\n    def __init__(self, d, f): raise RuntimeError('boom')\n")
    report = run.inspect(*_with(request, b">a\n"))
    assert report.unreadable and "count" in report.unreadable
```

- [x] **Step 2: Run them to see them fail**

Run: `uv run pytest packages/comeni-inspect/tests/test_run.py -q`
Expected: FAIL — no module `comeni_inspect.run`.

- [x] **Step 3: Implement `stream.py`**

```python
class TooLarge(Exception):
    """More bytes came out than the cap allows: a decompression bomb, or simply too much."""


class Capped(io.RawIOBase):
    """Reads through `inner`, refusing past `cap` bytes; a stream cut mid-way ends quietly.

    **A head is always cut.** A 4 MB head of a gzip file ends mid-stream every time, so
    `EOFError` from the decompressor is the normal end of a head, never an error. Only
    `zlib.error` and `gzip.BadGzipFile` (corruption) reach the caller.
    """

    def __init__(self, inner, cap: int):
        self.inner, self.cap, self.seen = inner, cap, 0

    def readable(self) -> bool:
        return True

    def readinto(self, buffer) -> int:
        try:
            chunk = self.inner.read(len(buffer))
        except EOFError:
            return 0
        self.seen += len(chunk)
        if self.seen > self.cap:
            raise TooLarge
        buffer[: len(chunk)] = chunk
        return len(chunk)
```

- [x] **Step 4: Implement `run.py`**

```python
def _load(ref: wire.PieceRef):
    spec = importlib.util.spec_from_file_location(f"piece_{ref.id}", ref.path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def inspect(request: wire.Request, payloads: list[bytes]) -> wire.Report:
    """One inspection. **Never raises**: every way it can go wrong is a report (spec §6)."""
    try:
        return _inspect(request, payloads)
    except TooLarge:
        return wire.Report(type_id=None, facts={}, unreadable="too large unpacked")
    except (zlib.error, gzip.BadGzipFile, OSError) as error:
        return wire.Report(type_id=None, facts={}, unreadable=f"could not be unpacked: {error}")
    except _PieceFailed as failed:
        return wire.Report(type_id=None, facts={}, unreadable=str(failed))


def _inspect(request, payloads):
    fmt = _guarded(request.format, _load)
    codec = _guarded(request.codec, _load) if request.codec else None
    streams = []
    for head, raw in zip(request.files, payloads, strict=True):
        opened = codec.open(raw) if codec else io.BytesIO(raw)
        stream = io.BufferedReader(Capped(opened, request.cap_bytes))
        if not fmt.confirms(stream.peek(4096)[:4096]):
            return wire.Report(type_id=None, facts={}, unreadable=f"{head.name} is named like {request.format.id}, but does not start like one")
        streams.append(fmt.records(stream))
    names = [f.name for f in request.files]
    accumulators = {m.id: _guarded(m, lambda r: _load(r).Accumulator(r.decided, names)) for m in request.measures}
    rows = 0
    for row in zip(*streams):  # side by side; stops at the shorter file
        rows += 1
        for key, acc in accumulators.items():
            _guarded(key, lambda _: acc.add(row))
    by_format = f"{request.format.id}@{request.format.version}"
    facts = {}
    for ref in request.measures:
        outcome = _guarded(ref, lambda _: accumulators[ref.id].result())
        by = [by_format, f"{ref.id}@{ref.version}"]
        if isinstance(outcome, Value):
            facts[ref.id] = wire.Fact(by=by, value=outcome.value, evidence=outcome.evidence)
        else:
            facts[ref.id] = wire.Fact(by=by, undetermined=outcome.reason, evidence=outcome.evidence)
    return wire.Report(type_id=None, facts=facts, unreadable=None)
```

`_guarded(ref_or_name, call)` runs `call(ref)` and turns any exception into `_PieceFailed(f"{name} failed: {type(e).__name__}")` — the only `except Exception` in the package, with a comment saying why (a piece is code we did not write at this call site; its failure is one inspection's answer, spec §8). The format's `type_id` is filled by the caller in part 4 from the format's `reads` (one type for FASTQ); keep `type_id=None` here and say so in the docstring. `main()`: `report = inspect(*wire.read_request(sys.stdin.buffer)); sys.stdout.write(report.to_json()); return 0`.

**When the files have different record counts**, `zip` stops at the shorter one; add `"rows": rows` to every fact's evidence so a truncated R2 is visible in the report (Review Focus 1).

- [x] **Step 5: Run them to see them pass**

Run: `uv run pytest packages/comeni-inspect -q`
Expected: PASS.

- [x] **Step 6: Commit**

```bash
git add packages/comeni-inspect
git commit -m "feat(inspect): the runner — one pass, every measure fed, every outcome a report (#134)"
```

---

### Task 4: The gzip codec and the FASTQ format, in the registry

**Files (inside `registry/`, on the registry branch):**
- Create: `inspectors/codecs/gzip/codec.yml`, `inspectors/codecs/gzip/piece/gzip_codec.py`
- Create: `inspectors/formats/fastq/format.yml`, `inspectors/formats/fastq/piece/fastq.py`, `inspectors/formats/fastq/piece/test_fastq.py`
- Create: `inspectors/formats/fastq/piece/fixtures/` (see Step 1)

**Interfaces:**
- Consumes: Task 3's piece contract.
- Produces: format `fastq@1.0.0` (`reads: [fastq.reads]`, `extensions: [.fastq, .fq]`, `record: sequence`, `runs: server`); codec `gzip@1.0.0` (`extensions: [.gz]`, `magic: ["1f8b"]`).

- [x] **Step 1: Generate the fixtures, deterministically**

Write `inspectors/formats/fastq/piece/fixtures/make.py` (kept, so the fixtures can be regenerated and reviewed) producing, with `random.Random(134)`:

| Case folder | Files | What it is |
|---|---|---|
| `single_150/` | `s_R1.fastq.gz` | 2,000 reads of 150 bp, Phred+33 |
| `pair_150/` | `s_R1.fq.gz`, `s_R2.fq.gz` | 2,000 pairs, names `@r{n}/1` and `@r{n}/2` |
| `pair_casava/` | `s_1.fq`, `s_2.fq` | names `@r{n} 1:N:0:1` and `@r{n} 2:N:0:1` |
| `interleaved/` | `s.fq` | R1 and R2 alternating, shared names |
| `names_disagree/` | `a_R1.fq`, `a_R2.fq` | file names pair; read names do not |
| `trimmed/` | `t.fq` | lengths uniform over 100–151 |
| `few/` | `f.fq` | 12 reads |
| `phred64/` | `old.fq` | qualities in `@`–`h` |
| `ambiguous_quality/` | `q.fq` | qualities only in `@`–`I` |
| `crlf/` | `w.fq` | CRLF line ends |
| `cut/` | `c.fq` | the last record cut after its sequence line |
| `fasta_named_fastq/` | `x.fastq` | `>a\nACGT\n` records |
| `truncated_gzip/` | `t.fq.gz` | a gzip stream cut in half |
| `pair_r2_short/` | `s_R1.fq`, `s_R2.fq` | R2 holds half as many records |
| `empty/` | `e.fq` | zero bytes |

No `.yml` anywhere under `fixtures/` (the loader would try to parse it). Run: `cd registry && uv run --project .. python inspectors/formats/fastq/piece/fixtures/make.py && ls inspectors/formats/fastq/piece/fixtures`.

- [x] **Step 2: Write the failing tests**

```python
# inspectors/formats/fastq/piece/test_fastq.py
"""The FASTQ format: four-line records, confirmed by content, a cut head handled."""

import io
import pathlib

import fastq  # the piece; the conftest in inspectors/ puts each piece/ on sys.path

FIX = pathlib.Path(__file__).parent / "fixtures"


def _records(path):
    return list(fastq.records(io.BufferedReader(io.BytesIO(path.read_bytes()))))


def test_confirms_fastq_and_refuses_fasta():
    assert fastq.confirms((FIX / "few/f.fq").read_bytes()[:4096])
    assert not fastq.confirms((FIX / "fasta_named_fastq/x.fastq").read_bytes()[:4096])


def test_crlf_is_read_without_the_carriage_return():
    records = _records(FIX / "crlf/w.fq")
    assert records and all(not r.sequence.endswith(b"\r") for r in records)


def test_a_cut_last_record_is_dropped():
    records = _records(FIX / "cut/c.fq")
    assert records and all(len(r.sequence) == len(r.quality) for r in records)


def test_the_name_stops_at_the_first_space():
    assert _records(FIX / "pair_casava/s_1.fq")[0].name == "r0"
```

and `registry/inspectors/conftest.py`:

```python
"""Each piece's tests import the piece by its file name: put every `piece/` on `sys.path`."""

import pathlib
import sys

for piece in sorted(pathlib.Path(__file__).parent.glob("*/*/piece")):
    sys.path.insert(0, str(piece))
```

Add `"registry/inspectors"` to `testpaths` in the root `pyproject.toml`.

- [x] **Step 3: Run them to see them fail**

Run: `uv run pytest registry/inspectors -q`
Expected: FAIL — `ModuleNotFoundError: fastq`.

- [x] **Step 4: Implement the pieces**

`codec.yml`: `declares: codec`, `id: gzip`, `version: 1.0.0`, `extensions: [.gz]`, `magic: ["1f8b"]`, `entry: piece/gzip_codec.py`. Code: `def open(raw): return gzip.GzipFile(fileobj=io.BytesIO(raw))`.

`format.yml`: as in Interfaces, `entry: piece/fastq.py`, `files: "1..2"`. Code:

```python
def confirms(first: bytes) -> bool:
    """`@name`, a sequence line, a `+` line, and a quality line the sequence's length."""
    lines = first.replace(b"\r\n", b"\n").split(b"\n")
    return (
        len(lines) >= 4
        and lines[0].startswith(b"@")
        and lines[2].startswith(b"+")
        and len(lines[1]) == len(lines[3]) > 0
    )


def records(stream):
    """Four lines at a time. A record cut by the head (fewer than four lines, or a quality line
    shorter than its sequence) ends the stream quietly: a head is always cut somewhere."""
    while True:
        lines = [stream.readline() for _ in range(4)]
        if not lines[3].endswith(b"\n"):
            return
        head, sequence, _, quality = (line.rstrip(b"\r\n") for line in lines)
        if not head.startswith(b"@") or len(quality) != len(sequence):
            return
        yield SequenceRecord(name=head[1:].split(b" ", 1)[0].decode(errors="replace"), sequence=sequence, quality=quality)
```

(The name keeps any `/1` `/2` suffix: stripping it is the `paired` measure's business, which is where the rule is declared.)

- [x] **Step 5: Run them to see them pass**

Run: `uv run pytest registry/inspectors -q`
Expected: PASS.

- [x] **Step 6: Commit in the registry**

```bash
cd registry && git add inspectors && git commit -m "Inspectors: the gzip codec and the FASTQ format (comeni-labs #134)"
```

---

### Task 5: Three measures, in the registry

**Files (inside `registry/`):**
- Create: `inspectors/measures/{read_length,paired,quality_encoding}/measure.yml` and `piece/<id>.py`, `piece/test_<id>.py`

**Interfaces:**
- Consumes: Task 4's fixtures; Task 3's accumulator contract (`add(row)` gets one record per file, side by side).
- Produces: `read_length@1.0.0` (`decided: {min_records: 1000, modal_share: 0.8}`), `paired@1.0.0` (`decided: {min_rows: 100, agreement: 0.99}`), `quality_encoding@1.0.0` (`decided: {min_records: 100}`); values: `read_length` an int, `paired` a bool, `quality_encoding` one of `phred33`, `phred64`.

The rules are spec §5's table, exactly:

- **`read_length`:** counts lengths over every record of every file; decided when records ≥ `min_records` and the modal length's share ≥ `modal_share`; evidence `{records, share, min, max}` (`share` is the modal length's share — the name the goal's `Evidence` uses); undetermined reasons `only {n} reads` or `lengths vary: {min}–{max}, trimmed?`.
- **`paired`:** with two files, a row agrees when both names are equal after stripping a trailing `/1` or `/2`; decided **true** when rows ≥ `min_rows` and agreeing share ≥ `agreement`, else undetermined `names say R1/R2, read names don't match` (if the first file's name matches `_R?1` / `_1`) or `read names don't match`. With one file, consecutive records are compared in pairs: decided **true** (interleaved) at the same thresholds, decided **false** when the agreeing share ≤ 1 − `agreement`, undetermined between. File names never decide. Evidence `{rows, agreeing}`.
- **`quality_encoding`:** over every quality byte: any byte below `;` (59) → `phred33`; else any byte above `J` (74) → `phred64`; else undetermined `characters fit both Phred+33 and Phred+64`. Below `min_records`: undetermined `only {n} reads`.

Each accumulator receives the sample's file names (Task 2's contract) only to word the `names say R1/R2` reason; a test below pins that file names alone never decide.

- [x] **Step 1: Write the failing tests, one file per measure, over the fixtures**

```python
# inspectors/measures/read_length/piece/test_read_length.py
from comeni_inspect.run import inspect
from support_pieces import request_for  # inspectors/conftest.py builds a Request from a fixture case

def test_uniform_150_is_decided():
    fact = inspect(*request_for("single_150", ["read_length"])).facts["read_length"]
    assert fact.value == 150 and fact.evidence["share"] == 1.0

def test_trimmed_is_undetermined_with_the_range():
    fact = inspect(*request_for("trimmed", ["read_length"])).facts["read_length"]
    assert fact.undetermined.startswith("lengths vary: 100–151")

def test_twelve_reads_are_not_enough():
    assert inspect(*request_for("few", ["read_length"])).facts["read_length"].undetermined == "only 12 reads"
```

```python
# inspectors/measures/paired/piece/test_paired.py
from comeni_inspect.run import inspect
from support_pieces import request_for

def _paired(case):
    return inspect(*request_for(case, ["paired"])).facts["paired"]

def test_two_files_with_matching_names_are_paired():
    assert _paired("pair_150").value is True
    assert _paired("pair_casava").value is True

def test_one_interleaved_file_is_paired():
    assert _paired("interleaved").value is True

def test_one_plain_file_is_single_end():
    assert _paired("single_150").value is False

def test_file_names_alone_never_decide():
    assert _paired("names_disagree").undetermined == "names say R1/R2, read names don't match"

def test_a_short_r2_stops_at_the_shorter_file_and_still_decides():
    fact = _paired("pair_r2_short")
    assert fact.value is True and fact.evidence["rows"] < 2000
```

```python
# inspectors/measures/quality_encoding/piece/test_quality_encoding.py
from comeni_inspect.run import inspect
from support_pieces import request_for

def _enc(case):
    return inspect(*request_for(case, ["quality_encoding"])).facts["quality_encoding"]

def test_modern_is_phred33():
    assert _enc("single_150").value == "phred33"

def test_old_illumina_is_phred64():
    assert _enc("phred64").value == "phred64"

def test_overlap_is_undetermined():
    assert _enc("ambiguous_quality").undetermined == "characters fit both Phred+33 and Phred+64"
```

Add `inspectors/support_pieces.py`, which `request_for(case, measures)` builds a `wire.Request` from `formats/fastq/piece/fixtures/<case>/` (sorted file names; the `gzip` codec when a name ends in `.gz`; each measure's `decided` read from its `measure.yml` with `yaml.safe_load`; `cap_bytes = 16 * 2**20`) and returns `(request, payloads)`.

- [x] **Step 2: Run them to see them fail**

Run: `uv run pytest registry/inspectors -q`
Expected: FAIL — the measure pieces do not exist.

- [x] **Step 3: Implement the three accumulators and their `measure.yml`, by the rules above**

Use `collections.Counter` for lengths and agreement; keep counts, never records.

- [x] **Step 4: Run them to see them pass**

Run: `uv run pytest registry/inspectors packages/comeni-inspect -q`
Expected: PASS.

- [x] **Step 5: Commit, in the registry and here**

```bash
cd registry && git add inspectors && git commit -m "Inspectors: read length, pairing and quality encoding (comeni-labs #134)" && cd ..
git add registry && git commit -m "chore(registry): the three measures (#134)"
```

---

### Task 6: Guards over every piece, the conformance goldens, the speed budget

**Files:**
- Create: `tests/guards/test_inspector_pieces.py`
- Create: `packages/comeni-inspect/src/comeni_inspect/harness.py`
- Create: `tests/registry/test_inspection_conformance.py`
- Create (registry): `inspectors/formats/fastq/piece/fixtures/<case>/expected.json` for every case

**Interfaces:**
- Produces: `harness.cases(registry: Path) -> list[Case]` (every fixture folder of every format, with its request built as `support_pieces` does, all of that format's measures); `harness.run_case(case, command: list[str] | None = None) -> str` — the report JSON, from `run.inspect` in-process when `command` is None, else by piping the request into `command` (any implementation, any language).

- [x] **Step 1: Write the guards**

```python
# tests/guards/test_inspector_pieces.py
"""Every inspector piece in the shipped registry keeps the rules (spec §3)."""

import ast
import pathlib

import pytest
from support.paths import ROOT

INSPECTORS = ROOT / "registry" / "inspectors"
PIECES = sorted(p for p in INSPECTORS.glob("*/*") if p.is_dir())
ALLOWED = {"comeni_inspect", "gzip", "zlib", "io", "re", "math", "collections", "typing"}


def test_there_are_pieces():
    assert PIECES, "no pieces found: the loop below would assert nothing"


@pytest.mark.parametrize("piece", PIECES, ids=lambda p: f"{p.parent.name}/{p.name}")
def test_a_piece_has_its_declaration_code_and_tests(piece):
    assert len(list(piece.glob("*.yml"))) == 1
    assert list((piece / "piece").glob("*.py"))
    tests = list((piece / "piece").glob("test_*.py"))
    assert tests and any("def test_" in t.read_text() for t in tests)


@pytest.mark.parametrize(
    "code",
    sorted(p for p in INSPECTORS.rglob("piece/*.py") if not p.name.startswith("test_") and p.parent.name == "piece" and "fixtures" not in p.parts),
    ids=lambda p: str(p.relative_to(INSPECTORS)),
)
def test_a_piece_imports_only_the_allowlist(code):
    tree = ast.parse(code.read_text())
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module.split(".")[0])
        elif isinstance(node, ast.Call) and getattr(node.func, "id", "") in {"__import__", "open", "exec", "eval"}:
            names.add(f"<{node.func.id}()>")
    assert names <= ALLOWED, f"{code.name} reaches past the allowlist: {sorted(names - ALLOWED)}"
```

(`open` the builtin is banned: a piece reads only the stream it is handed. The codec's own function is also called `open`; that is a definition, not a call, and is not matched.)

- [x] **Step 2: Watch each guard fail (A14)**

Add `import socket` to `fastq.py`; run `uv run pytest tests/guards/test_inspector_pieces.py -q`; see the allowlist test FAIL naming `socket`; revert. Rename `test_fastq.py` to `check_fastq.py`; see the declaration test FAIL; revert. Record both in `tests/fixtures/guard-ledger.md`.

- [x] **Step 3: Write the conformance test**

```python
# tests/registry/test_inspection_conformance.py
"""Every fixture case reproduces its golden report byte for byte (spec §4).

The goldens are the contract a faster implementation must meet: run the same cases against its
command with `harness.run_case(case, command=[...])`.
"""

import gzip
import io
import random
import time

import pytest
from support.paths import ROOT

from comeni_inspect import harness, run, wire

CASES = harness.cases(ROOT / "registry")


def test_there_are_cases():
    assert CASES


@pytest.mark.parametrize("case", CASES, ids=lambda c: c.name)
def test_a_case_matches_its_golden_report(case):
    assert harness.run_case(case) == (case.folder / "expected.json").read_text().strip()


@pytest.mark.parametrize("case", CASES, ids=lambda c: c.name)
def test_a_case_never_raises(case):
    json = harness.run_case(case)
    assert wire.Report.model_validate_json(json)


def test_the_speed_budget():
    """A 4 MB gzipped FASTQ head in under a second (spec §4): says when Python stops being enough."""
    rng = random.Random(134)
    lines = []
    for n in range(40_000):
        seq = "".join(rng.choice("ACGT") for _ in range(150))
        lines.append(f"@r{n}/1\n{seq}\n+\n{'I' * 150}\n")
    raw = gzip.compress("".join(lines).encode())[: 4 * 2**20]
    request, payloads = harness.request_for_bytes(ROOT / "registry", "x_R1.fq.gz", raw)
    start = time.perf_counter()
    report = run.inspect(request, payloads)
    elapsed = time.perf_counter() - start
    assert report.unreadable is None
    assert elapsed < 1.0, f"{elapsed:.2f}s for a 4 MB head"
```

`harness.request_for_bytes(registry, name, raw)` builds a request for one file the way `cases` does. Move `support_pieces.request_for`'s logic into `harness` and make `support_pieces` a two-line wrapper over it, so the piece tests and the conformance test build requests one way.

- [x] **Step 4: Generate the goldens once, read them, then commit them**

Run: `uv run python -c "from comeni_inspect import harness; from pathlib import Path; [ (c.folder/'expected.json').write_text(harness.run_case(c)+'\n') for c in harness.cases(Path('registry')) ]"`
Then **read every `expected.json`** against spec §5's table and the case's description in Task 4; a golden that encodes a wrong answer is a wrong contract. Fix the piece, not the golden, if one is wrong.

- [x] **Step 5: Run everything**

Run: `uv run pytest tests/guards/test_inspector_pieces.py tests/registry/test_inspection_conformance.py registry/inspectors packages/comeni-inspect -q`
Expected: PASS; the speed budget's elapsed time recorded in the execution record.

- [x] **Step 6: Commit, in the registry and here**

```bash
cd registry && git add inspectors && git commit -m "Inspectors: golden reports for every FASTQ case (comeni-labs #134)" && cd ..
git add tests packages/comeni-inspect registry && git commit -m "test(inspect): guards over every piece, the conformance goldens, the speed budget (#134)"
```

- [x] **Step 7: Run `make check`, separately**

Run: `make check > /tmp/claude-1000/check.log 2>&1; tail -20 /tmp/claude-1000/check.log`
Expected: PASS.

---

## Execution record

*(Filled in while executing: rulings, measurements, deviations.)*

- **Measured:** a 4 MB gzipped FASTQ head takes 0.21 s in one pass with three measures (budget 1 s).
- **Registry:** pieces on comeni-registry branch `inspectors` (from `main` after `one-folder-per-tool` merged). `quality_encoding` joined the measurements: MD0317 refused the piece without it. It stays assertion-only until plan 3 counts pieces as producers.
- **Rulings:** an entry must stay inside `piece/`; the lint skips `piece/` like `module/`; a payload shorter than declared is refused; the format's own iteration is guarded and an empty file says so; the cut-gzip test uses varied records (identical ones compress to nothing decodable); fixtures that must pass 1,000 reads are gzipped (1.7 MB in all); `paired` reports `{pairs, agreeing}` because the runner owns `rows`; `comeni-inspect` is classified impure and depends on PyYAML for its harness; forge goldens gained `measurement.quality_encoding`.

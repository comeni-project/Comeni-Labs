# Samples and inspectors — design

**Issue:** #134 (step 14.7.6, under #126). **Decided** by the operator on 2026-10-01, in the
brainstorm this spec records. It replaces *Samples and inspectors* in §6 of
`2026-09-28-the-consultant-design.md`, which put inspectors in a dict inside `mendel-api`; that
does not survive hundreds of data types.

Built in six parts, 14.7.6.1–14.7.6.6 (§12). Each part gets its own plan.

Opened from this brainstorm, out of scope here: #216 (registry: one folder per tool, and finding
a file without searching the layout; lands before 14.7.10), #217 (runtime decisions: a profiler
sets a later step's parameters; after Task 14), #218 (samples that disagree: split the data and
run smaller pipelines; after the MVP).

## 1. What a person gets

In the conversation, a gap the person is *not sure* of can be answered with a file. They upload
**one sample** (a file or a pair); the engine reads its head, on our server, and the facts it can
read close their gaps together, each marked **measured**, with who measured it and on how much:

```
read_length: 151        measured · fastq 1.0.0 · 8,412 reads · 97% at 151
paired: undetermined    names say R1/R2, read names don't match
```

Nothing is guessed (protocol rule 5). A head that cannot decide a fact says so, and the fact stays
open (rule 6). A file nothing can read says *nothing reads this type yet*; the characteriser fills
that branch in 14.7.7.

## 2. Three kinds of measurer

| | **Module** | **Profiler** | **Inspector** |
|---|---|---|---|
| What it is | a tool that does work | a tool that **measures** | code that **measures a sample** |
| Made of | Nextflow module + contract | Nextflow module + contract (produces `measurement.*`) | codecs, formats, measures (§4) |
| Where it lives | the registry | the registry | `comeni-inspectors` (§3) |
| **Runs** | **the lab's machine**, in the pipeline | **the lab's machine**, in the pipeline | **our server**, in the conversation |
| Reads | all the data | all the data | the first 4 MB of one upload |
| Gives | outputs | a profile, read back as facts | facts for the goal |

- **Profilers stay contracts.** They already are (`profile-fastqc` produces
  `measurement.read_length`); a separate registry kind would duplicate the contract machinery.
  #216 makes them visible in the layout.
- **Inspectors are code that runs on a person's file**, so they are not registry data (CC-BY,
  approved by a curator) but their own repository (Apache-2.0).
- **What unifies them is the measurement id.** Comeni builds one **who-measures-what index** at
  load: for each measurement, every inspector and profiler that produces it, with its version
  and where it runs.
- **Where something runs is declared, never assumed:** every measurer carries
  `runs: server | lab` (later `browser`, the `guarded` level's *read in the browser, facts only*).
  Moving a measurer is a change to that field and a runner, and a protection level can refuse
  anything that runs on the server. This is written into the protocol page and `ARCHITECTURE.md`
  as a table, because it is expected to change.

## 3. The `comeni-inspectors` repository

A separate public repository, `comeni-project/comeni-inspectors`, Apache-2.0. **It depends on
nothing of ours**: it reports plain values keyed by id strings, and Comeni decides what they mean
(invariant 2). The only coupling is names (type and measurement ids), the coupling the registry
already has.

```
comeni-inspectors/
  README.md            what an inspector is; add a format or a measure in five steps
  PROTOCOL.md          the wire protocol (§6), the contract every implementation speaks
  src/comeni_inspectors/
    contract.py        Head, Report, Fact, Undetermined, Unreadable, the declarations
    run.py             the runner: one inspection per process, request on stdin, report out
    codecs/gzip/       codec.yml, code, fixtures, tests
    formats/fastq/     format.yml, code, fixtures, tests
    measures/read_length/  measure.yml, code, fixtures, tests
    measures/paired/
    measures/quality_encoding/
  conformance/         fixtures and golden reports every implementation must reproduce
  tests/               guards over every piece
```

- **One folder per piece**, each with its declaration, code, fixtures and tests.
- **Consumed by Comeni as a git dependency pinned to a tag**, not a submodule. The repository is
  tagged (`v0.1.0`); each piece's own `version` is what a fact records.
- **Guards, in its CI, over every piece:** a declaration, fixtures and tests exist, and the tests
  are non-empty; no network, no file reads, no subprocesses (the pure packages' import ban);
  every fixture returns a report, never an exception, including malformed files, a truncated
  gzip, a decompression bomb and an empty file; every value a piece returns is one its
  declaration names. Each guard is watched failing (A14).

## 4. Inside an inspector: codecs, formats, measures

"Hundreds of types" repeats itself: the same compression wraps most formats, many formats hold
the same kind of record, and the same measurement applies across formats. So an inspection is
**composed from three kinds of piece**, each written once:

- **Codec**: unwraps bytes (gzip first; BGZF, bzip2, zstd later). Declares its magic bytes.
- **Format**: turns bytes into typed records, and confirms the content is what the name says.
  Declares the types it reads, its extensions, its **record shape** (`fastq` yields *sequence
  records*: name, sequence, quality) and `runs:`.
- **Measure**: reads records of one shape and produces one measurement. Declares the measurement
  id, the record shape it reads, its arity (one file, or a pair) and its threshold (§5).

**"The FASTQ inspector" is the FASTQ format plus every measure that reads sequence records**,
assembled at load. A new format yielding sequence records gets `read_length` for free; a new
measure works on every format of its shape. A fact records every piece that made it:
`read_length by fastq@1.0.0 + read_length@1.0.0`.

**Formats as data, later.** A tabular format (BED, GTF, VCF bodies, counts matrices) can be
declared as YAML (columns, separator, comment prefix, content check) and read by one generic
tabular format. Not built in 14.7.6; the layering leaves room for it, and it is the first format
after FASTQ that should use it.

### Efficiency: one pass

The format yields records **once**, as a stream, and every measure is an **accumulator**
(`add(record)`, `result()`) fed from that stream. Decompression is streamed and capped, never
whole in memory; accumulators keep counts, not records. One decompression and one parse, whatever
the number of measures. **The whole head is read**, so every fact rests on the same records and
the card can say *measured on the first N reads*. Stopping early (`enough()` on the accumulator)
is a later change that touches no measure.

A **pair** is two streams read side by side: record *n* of R1 with record *n* of R2.

### Speed, and room for Rust or C

- **The boundary is the wire protocol (§6)**, not Python. A piece declares `impl: python` or
  `impl: executable`; an executable speaking the protocol is a valid implementation in any
  language. A hot loop may also be a compiled extension inside the Python runner (PyO3).
- **One conformance suite** (`conformance/`): the same fixtures, the expected reports as golden
  files. A Rust format must reproduce the Python one's reports byte for byte before it replaces
  it, so faster code cannot change a fact.
- **A speed budget is a test:** a 4 MB gzipped FASTQ head inspected in under one second. It
  says when Python stops being enough, instead of guessing.

### Native libraries

Every piece is pure Python by default. A piece that needs a compiled library declares it
(`needs: [pysam]`) and is packaged as an extra (`comeni-inspectors[bam]`). A piece whose library
is not installed is **listed as not installed here**, never hidden, and its files go to the
characteriser. CI tests each extra separately. 14.7.6 builds nothing native: gzip and FASTQ are
standard library.

## 5. Trusting a head

Four megabytes is sometimes not enough. Each measure declares **what counts as decided**, and
below it returns **undetermined, with the reason**, never a value:

| Measure | Decided when | Undetermined says |
|---|---|---|
| `read_length` | ≥ 1,000 records and the modal length covers ≥ 80% of them | *lengths vary: 139–151, trimmed?* / *only 12 reads* |
| `paired` | **yes:** two files whose read names match record by record (after stripping `/1` `/2` and the comment), or one interleaved file whose consecutive records share a name. **No:** one file whose names do not pair. File names (`_R1`/`_R2`) only ever corroborate, never decide | *names say R1/R2, read names don't match* |
| `quality_encoding` | every quality character in the head falls in one encoding's range | *characters fit both Phred+33 and Phred+64* |

The thresholds live in each measure's declaration, visible and tunable (rules are tuned, never
forced). **An undetermined fact stays open**: the gap is asked again with the reason, or the
decision falls to tier 4 in the build. Every fact, decided or not, carries its evidence (records
read, agreement).

## 6. The wire protocol

One inspection is one process (§8). Request on stdin, one report on stdout, as JSON:

- **Request:** the pieces to run (format id and version, measure ids and versions), then each
  file's name and bytes (length-prefixed, the head already capped).
- **Report:** `type_id` (or none), and per measure either `{value, evidence}` or
  `{undetermined, reason, evidence}`; or the whole inspection `Unreadable` with a reason
  (*named .fastq but isn't one*, *too large unpacked*).
- **Exit codes:** 0 with a report; anything else, or no report in time, is `Unreadable` on
  Comeni's side, never a crash.

`PROTOCOL.md` is the written contract and the conformance suite is its test.

## 7. How a file finds its inspector

1. **Extension narrows:** the formats whose declared extensions match (after any codec's
   extension, `.fq.gz` → gzip → `.fq`).
2. **Content confirms:** each candidate format checks the first records (`@` header, a sequence,
   `+`, a quality line of the same length).
3. Exactly one confirms → it reads the file. **None claims the extension** → the characteriser
   (14.7.7; until then, *nothing reads this type yet*). **Several confirm** → a tie, decided by
   the characteriser or the person, never a coin flip (as invariant 8). **The extension matches
   and the content does not** → `Unreadable`, with the reason.

## 8. Safety: a separate process with hard limits

Each inspection runs in **its own short-lived process**, with a time limit (a few seconds), a
memory limit, and a decompressed-size cap (16 MB), and receives its bytes on stdin. A hang, a
crash or a bomb costs one inspection, which is `Unreadable: took too long` (or *too large
unpacked*), never a 500. The guards in §3 keep pieces off the network and the filesystem.
**Container isolation per inspection** is the next step, when outside contributors or native
pieces arrive; the protocol is the same, only the launch changes.

## 9. Comeni's side

**Loading** (`mendel-api`, never a pure package, since inspectors read people's files): at
startup, every installed piece's declaration is read. A piece naming a type or measurement the
registry does not declare is **refused** with a declared code, and the others still load
(invariant 7: an inspector cannot invent vocabulary). The **who-measures-what index** is built
from the pieces and the profiler contracts, and served by the vocabulary endpoint so the card can
say *measured by an inspector*, *measured when the pipeline runs*, or *nothing measures this yet*
(rule 4).

**Inspecting** (`services/inspect.py`) follows the detailed diagram (§11): match, launch the
runner with its limits, read the report.

**Admitting** (`comeni-core`): `ValueSource.INSPECTED`; `Measured.by` naming the pieces and
versions; `MeasurementRegistry.profile_of(entries)` for a profile whose entries carry their own
sources (the construction guard forbids building a `DataProfile` anywhere else). Each value is
checked with `MeasurementRegistry.check`; one that fails is dropped with a reason shown to the
person. An undetermined fact is not admitted, and the measurement stays open.

**`assertion_only` is checked against the index.** A measurement marked `assertion_only` that a
piece now measures is refused by the registry test, so the declaration is corrected rather than
drifting. 14.7.6 removes it from `paired`.

**Into the goal, and replayed:** a measured fact enters the goal with its source, `by` and
evidence. A rebuild from that goal reuses it; the inspector runs again only on a new upload. The
file's bytes and name never enter the goal or `pipeline.yml`.

## 10. The upload, in the conversation

- **A measurement gap's *Not sure*** becomes *Not sure: upload a sample and I'll measure it*,
  opening a picker for **one file or one pair**. **An input gap's** *I have it, and will upload it*
  opens the same picker. One upload closes every gap it answers, each marked measured.
- **While it is inspected,** the card shows the detailed diagram's steps as they happen
  (*reading the head… confirming it's FASTQ… measuring*), never a silent spinner.
- **Unreadable** shows its reason and offers the gap's other answers again.
- **The route:** `POST /api/pipeline/authoring/{id}/samples`, multipart. It asks the protection
  level first and refuses above level 0 with a declared code. It keeps **only the first 4 MB**
  of each file (a longer file is cut to its head, never refused for size) under
  `workspace/samples/<session>/<sample>/`, **deleted with the session**; nothing is kept beyond
  it. It runs the inspection, returns the report, and the session records the facts it admitted
  (`FACT_ADDED`, as a click does).
- **The protection level setting:** *Level 0* is built and stops showing *Not built*; open,
  guarded and sealed stay designed (#71).
- **The goal card** shows *measured · fastq 1.0.0 · from 1 sample* where *you said* and *read by
  AI* appear. The tier stays 3 (yellow, *check the premise*).
- **One sample only.** Several samples, and samples that disagree, are #218.
- **Design first:** the upload states (picking, inspecting step by step, measured, undetermined,
  unreadable) get a Claude Design pass the operator approves before frontend code, and the build
  is compared to its artboards by screenshot.

## 11. The diagrams

The general protocol diagram has about 30 nodes and 50 edges; the inspection would add a dozen.
So diagrams split, **one general and several detailed**:

- **A node in `PROTOCOL` may carry a `detail`**: its own steps and edges, checked at load like the
  main object. Its steps sit inside one phase (gathering), so the state machine does not change.
- The general diagram keeps *Engine reads it exactly → measured*, marked as having a detail and
  linked to it.
- **The first detailed diagram, *Inspecting a sample***: upload received → keep the first 4 MB →
  protection level → formats claiming the extension (none → characteriser) → in its own process:
  decompress, capped (bomb → unreadable) → content confirms (no → unreadable; several → tie)
  → measure (hangs → unreadable; below threshold → undetermined) → admit each value (refused →
  dropped, says which) → stamped measured → the next gap. All of it marked **on our server**.
  The characteriser branch is dashed until 14.7.7.
- **The diagrams live in one folder**, `docs/design/diagrams/`: `authoring-protocol.md` (moved
  from `docs/design/authoring-protocol-diagram.md`), `inspecting-a-sample.md`, and a generated
  `README.md` listing every diagram. The generator writes the whole folder; `make docs` fails when
  it is stale. The next detailed diagram (likely the consultant build, 14.7.8) uses the same
  mechanism.

## 12. Build order

| Part | What | Depends on |
|---|---|---|
| **14.7.6.1** | `comeni-inspectors`: the repository, the declarations, the wire protocol and runner, gzip, the FASTQ format, the three measures, the conformance suite, the guards, the speed budget. Tagged `v0.1.0`. | the operator creates the GitHub repository |
| **14.7.6.2** | `comeni-core`: `INSPECTED`, `Measured.by` and evidence, `profile_of`; `paired` loses `assertion_only` | — |
| **14.7.6.3** | `mendel-api`: loading and refusing pieces, the who-measures-what index, the inspection service and its limits, the upload route, protection level 0 built | 1, 2 |
| **14.7.6.4** | Protocol: `detail` on a node, `docs/design/diagrams/`, the inspection diagram, the upload branch built | 3 |
| **14.7.6.5** | Design pass, then the gap card's upload states and the goal card's measured label | 3 |
| **14.7.6.6** | The where-it-runs table (protocol page, `ARCHITECTURE.md`), the inspectors README, and scenario 1 walked with a real model and a real FASTQ pair | all |

## 13. Errors

New diagnostics, declared in `comeni_core/diagnostics.yml` and emitted through `coded()`: a piece
refused at load (unknown type or measurement, or a missing native library); an upload refused by
the protection level; an upload with the wrong number of files. An unreadable file and an
undetermined fact are **answers**, not errors: shown with their reason, never a code.

## 14. Testing

- **`comeni-inspectors`:** fixture heads (plain, gzipped, R1/R2, `_1`/`_2`, interleaved,
  Phred+33 and Phred+64, trimmed lengths, too few reads); malformed files, a truncated gzip, a
  decompression bomb, an empty file; the conformance goldens; the speed budget; each guard watched
  failing.
- **Comeni:** the runner's limits against a deliberately slow, crashing and oversized test piece,
  each `Unreadable` and never a 500; a piece naming an unknown id refused while the rest load; the
  index; `profile_of` with mixed sources; an undetermined fact left open; the route refused above
  level 0; samples deleted with the session; `paired` no longer `assertion_only`; the diagrams'
  `--check`.
- **Frontend:** the upload states, and screenshots compared to the artboards.
- **Acceptance:** scenario 1, walked with a real model and a real FASTQ pair, ends with `paired`
  and `read_length` **measured** and nothing invented.

## 15. Open questions

- **A sample's head as model input** (14.7.7): the characteriser receives the head at level 0. The
  head stored here is the same bytes; 14.7.7 decides whether it reads from this store.
- **The `comeni-core` version:** `INSPECTED` and `profile_of` are features; the bump is judged at
  release time (`docs/internals/releasing.md`).

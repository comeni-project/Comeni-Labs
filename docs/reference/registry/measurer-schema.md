# Measurer schema

A measurer produces one measurement. It says how it measures and where it may run:

- **on the server**, over the first 4 MB of an upload, during the conversation. Its facts are an
  estimate unless the whole file fitted;
- **in the pipeline**, as a step over all the data, during the run.

One file per measurer, carrying `declares: measurer`, in its own folder beside its code. The
public registry keeps them in `measurers/measures/<id>/measurer.yml`, with codecs and formats
beside them in `measurers/codecs/` and `measurers/formats/`.

## Two ways to measure

**Our own code** (`by: code`). A format turns a file into records, and the measurer reads
records of one shape. The same code runs in both places.

```yaml
declares: measurer
id: read_length
version: 1.0.0
measures: read_length
by: code
record: sequence
runs: [server, pipeline]
decided: {min_records: 1000, modal_share: 0.8}
entry: piece/read_length.py
```

**A tool and a parser of its output** (`by: tool`). The tool runs as an ordinary step in the
pipeline, and the parser reads one of its outputs. A tool never runs on the server.

```yaml
declares: measurer
id: genome_length_fai
version: 1.0.0
measures: genome_length
by: tool
uses: nf-core/samtools/faidx@1.24
output: fai
entry: piece/fai.py
runs: [pipeline]
```

## Fields

Model: `comeni_core.declared.inspection.Measurer`

| Field | Type | Meaning |
|---|---|---|
| `id` | identifier | the folder's name; on a fact it is `<id>@<version>` |
| `version` | `x.y.z` | recorded on every fact it produces |
| `measures` | measurement id | the measurement it produces, declared in `vocabulary/measurements/` |
| `by` | `code` \| `tool` | our code over a format's records, or a tool's output parsed |
| `record` | `sequence` | `by: code` only: the record shape it reads |
| `uses` | contract id | `by: tool` only: the tool whose output is parsed |
| `output` | port name | `by: tool` only: that tool's output the parser reads |
| `runs` | list of `server`, `pipeline` | where it may run; at least one. `by: tool` has no `server` |
| `decided` | map | thresholds below which it says *undetermined*, recorded on every fact |
| `entry` | path in `piece/` | the code |
| `needs` | list of piece ids | other pieces it needs loaded |
| `impl` | `python` \| `executable` | how the runner invokes the code; `python` by default |

### Refusals at load

| Code | When |
|---|---|
| `MD0326` | the declaration does not fit its `by:` (a code measurer with no `record`, a tool measurer with one, or with `server` in `runs`, or without `uses`/`output`), or `runs` is empty |
| `MD0327` | `uses` names a contract no layer declares, or `output` is not one of its ports. The measurer is dropped and the others load |
| `MD0317` | `measures` names a measurement no layer declares |
| `MD0318` | the code is missing, the folder is not the id, or a `needs` entry is not declared |

## The code

A `by: code` measurer's `entry` defines `Accumulator`: `__init__(self, decided, files)`, then
`add(row)` for each row of records, then `result()` returning `Value(value=..., evidence={...})`
or `Undetermined(reason=..., evidence={...})` from `comeni_inspect.outcome`.

A `by: tool` measurer's `entry` defines `parse(stream, decided)`, given the tool's output as a
byte stream, returning the same `Value` or `Undetermined`.

Either imports only the pieces' allowlist (`tests/guards/test_inspector_pieces.py`): no network,
no files, no processes. It never raises, and it never decides on a file's name.

## Coverage

Every fact a measurer produces says how much of the data it read: `coverage: all` when every
file was read to its end, and `head` otherwise (an upload's first 4 MB, a file cut short, a stop
at a malformed record, or the unread tail of a pair's longer file). A rule can require all of the
data with `coverage: all` ([rule schema](rule-schema.md#coverage)).

## In the pipeline

A measurer with `pipeline` in `runs` becomes a generated step, `comeni/measure/<name>`, that the
router can place like any other step. Our code's measurers share one step per format, so a file
is read once for every fact. A tool's measurer has its own step after the tool. The steps run on
a pinned plain Python image, and their files are recorded in `pipeline.yml`.

The build adds such a step for two reasons:

- **a setting decided at run time**: a rule needs a fact nobody stated, and the pipeline can
  measure it ([rule schema](rule-schema.md#decided-at-run-time));
- **an estimate confirmed**: a decision used a fact read from part of the data, and the pipeline
  measures it again over all of it. After the run, the run page shows whether they agree, and a
  disagreement names every decision built on the estimate.

Each step writes `<outdir>/<process>/<sample>.measured.json`, and Wiener reads them when the run
completes.

# Measurers and run-time decisions

Part 4 of #463: issues #465 (measurers) and #217 (run-time decisions). Follows rules v2
([its design](2026-11-10-rules-v2-design.md)). This replaces the "own `profiler` kind, later" of
[samples and inspectors](2026-10-01-samples-and-inspectors-design.md) §2.

## Why

The goal for #463 parts 2–5 (operator, 2026-11-10) is to import a tool easily and have the
builder actually build with it. Part 3 made a setting decidable from a fact, but every fact
still has to be known before the build: a person states it, or the server measures the first
4 MB of an upload. Many facts cannot be known that way. A genome's length needs the whole
reference, and strandedness needs an alignment. nf-core works these out inside the pipeline,
where nobody sees them. This part measures them in the pipeline, decides from them there, and
shows both.

**What exists:**

- **Inspector pieces** (`registry/inspectors/`): codecs, formats and measures, run by
  `comeni-inspect` in a sandboxed subprocess on the head of an upload, trusted layers only
  (`mendel_api/services/measurers.py`).
- **Profilers** (`registry/profilers/comeni/profile/`): two hand contracts, FastQC producing
  `measurement.read_length` and MultiQC collecting `profile.yml`, routed by `mendel profile`.
  Nothing reads `profile.yml` back, so pipeline measurement is half-built.
- **Facts** (`Measured`, `PremiseRecord`) carry the origin, the measurer (`by` or `pieces`) and
  evidence. They do not say how much of the data was read: a fact from a capped head and one
  from a whole file look the same.
- **Metadata from facts:** a measurement with `describes:` and `meta_key:` already reaches the
  input channel's `meta` (`meta_sources_by_type`). `ext.args` with `${…}` is already emitted as
  a per-task closure, which can read `meta`. This is how nf-core passes strandedness to
  featureCounts.
- **Wiener** folds Nextflow's events and its own (`HEARTBEAT`, `CANCELLED`). It reads nothing
  from a run's results.

## The demo (my call)

**STAR's genome index, sized during the run.** Part 3 decides `--genomeSAindexNbases` from a
stated genome length. With this part, a person who states nothing gets:

- the build adds `samtools faidx` on the genome and a parser that sums the `.fai`, and the
  `genome_length` fact joins the genome's `meta`;
- STAR genomegenerate's setting shows "decided at run time by the STAR index rule, from
  genome length measured by samtools faidx: log2, ÷2, −1, at most 14, rounded";
- in the run, a 29,903 bp genome gives `--genomeSAindexNbases 6`, and the run page shows the
  measured length and the value it led to.

**The second half of the demo is read length, confirmed on all the reads.** The server's 4 MB
estimate (say 150) is what the aligner was chosen on. The pipeline measures every read with the
same measure code. If it agrees, the run page says "confirmed on all the data". If it does not,
it shows the disagreement and names the decisions built on the estimate.

Together these show both ways a fact is measured: our code, or a tool plus a parser. They show
both runners, a decision made at run time, and a disagreement.

## Goals

- **A. One declaration kind, the measurer.** It replaces `declares: measure` and the profiler
  contracts. It names the measurement it produces and how:
  - `by: code`: our own code (today's measures, unchanged inside);
  - `by: tool`: a contract in the registry, plus a parser for one of its outputs.

  Each lists where it may run (`runs: [server, pipeline]`). The who-measures-what index lists
  every measurer.
- **B. Two runners, one measure.**
  - `server` is today's inspection, unchanged: the head of an upload, sandboxed, trusted layers
    only.
  - `pipeline` is a step over all the data.

  A `by: code` measurer runs in both from the same file. A `by: tool` measurer runs only in the
  pipeline.
- **C. Facts record their coverage.** Either `head` (the server read part of the file) or
  `all`. A server inspection that reached the file's natural end, uncapped, read all of it. A
  decision may require `coverage: all`.
- **D. Run-time decisions.** A decision whose fact is unknown before the build, or known only
  from a head under `coverage: all`, is compiled into the pipeline when a pipeline measurer can
  reach the fact. The measurer's steps are added, the fact reaches `meta`, and the setting is
  emitted as a lookup over `meta`. Every outcome is listed in the build before the run. No model
  runs at run time, and the same goal gives the same `.nf`.
- **E. Estimates confirmed, disagreements shown.** A `head` fact that a build decision used is
  measured again in the pipeline when a pipeline measurer exists for it. At the end of the run,
  Wiener reads the pipeline's facts. The pipeline's value wins: the run records it, shows any
  disagreement, and flags the decisions that rested on the estimate.
- **F. The builder and the run page show it.** The step card shows a run-time decision and its
  outcomes. The run page shows measured facts, run-time values and disagreements.

## Non-goals

- **Rebuilding after a disagreement**, and splitting samples that disagree: part 5 (#466) and
  #218. Here a disagreement is recorded, shown and flagged.
- **The forge drafting measurers**, including parser code. A measurer is hand-written and
  reviewed in this part, and the forge imports the tool it uses (samtools faidx). This is
  recorded on #465.
- **A run-time decision over two or more run-time facts.** Facts known before the build are
  substituted into the table at build time, and at most one fact per decision is left for run
  time. A second one is refused with a code.
- **`by: tool` measurers on the server.** A tool runs only in the lab's pipeline.
- **The `browser` runner.**

## Anti-goals

- A value set at run time that the build did not show beforehand, with its rule, its measurer
  and every outcome it can take.
- A run-time value nobody can trace afterwards.
- A pipeline value silently replacing an estimate that decisions were built on.
- Generated Groovy from anything but the closed operations and checked literals.

## Constraints

- `comeni-core`, `mendel-resolver`, `mendel-compiler` and `wiener-core` stay pure. The pipeline
  runner's measure code reads only the files it is handed, like the server's.
- The same goal and recorded decisions reproduce the same pipeline (invariant 10). Run-time
  values come from the data, through the emitted lookup.
- Measure and parser code imports only the pieces' allowlist (`tests/guards/test_inspector_pieces.py`).
- Pipeline steps are pinned: the runner's image by digest, and the staged measurer code
  by content digest in `pipeline.yml`, as modules are.
- No backward compatibility before v0.1.0. `declares: measure`, `profilers/`, `profile.yml`
  and `mendel profile` are removed, not aliased.
- Diagnostics are declared in `diagnostics.yml` and emitted through `coded()`.
- Registry changes land in the registry's own repository. Tests use overlays until they do.

## Design

### A. The measurer declaration

```yaml
declares: measurer
id: read_length
version: 1.1.0
measures: read_length
by: code
record: sequence
decided: {min_records: 1000, modal_share: 0.8}
entry: piece/read_length.py      # class Accumulator, as today
runs: [server, pipeline]
```

```yaml
declares: measurer
id: genome_length_fai
version: 1.0.0
measures: genome_length
by: tool
uses: nf-core/samtools/faidx@1.21   # a contract id
output: fai                         # the port the parser reads
entry: piece/fai.py                 # def parse(stream, decided) -> Value | Undetermined
runs: [pipeline]
```

- `comeni_core.declared.inspection.MeasurePiece` becomes `Measurer`, with `by`, `uses`,
  `output` and `runs`. Load checks that a `by: code` measurer has a `record`, and that a
  `by: tool` measurer names a contract and one of its output ports, has no `server` in `runs`
  and has no `record`. Refusals are new MD codes.
- The registry moves `inspectors/` to `measurers/` (`codecs/`, `formats/`, `measures/`).
  `profilers/` is deleted, along with the `measurement.*` types if nothing else reads them.
- The measurement declaration for `genome_length` drops `assertion_only` and gains
  `describes: genome.fasta` and `meta_key: genome_length`.
- The index (`services/measurers.py`) lists measurers with their `runs`.

### B. The pipeline runner

- `comeni_inspect`'s inspection core moves behind plain stdlib types, so it runs without
  pydantic. `wire.py` stays the server's process boundary.
- `comeni-measure` is a stdlib-only entry point. It reads whole files with no cap: a format and
  its `by: code` measurers, or one parser over a tool's output. It writes one report per
  sample in the wire `Report` shape, with `coverage: all`.
- The emitter stages the runner and the measurer pieces into the pipeline directory, digested,
  and adds two kinds of process: `MEASURE_<FORMAT>` over an input, and `PARSE_<MEASURER>` after
  a tool step. Both run on a pinned plain Python 3.12 image. Each publishes
  `measurements/<measurement>/<meta.id>.json`.
- A `by: tool` measurer's tool step is an ordinary step, routed and pinned like any other.

### C. Coverage

- `wire.Fact` and `Measured` gain `coverage: head | all`. An asserted fact has none.
- The server's coverage is `all` when no file was capped, and `head` otherwise.
- `Decision.coverage: all` (default unset): a premise with `head` coverage does not satisfy
  that decision before the build.
- The reason says it: "read length is 150, measured on the first 4 MB".

### D. Run-time decisions

**When.** A `param` decision is run-time when all of these hold:
- a fact it reads has no value before the build, or only `head` coverage under
  `coverage: all`;
- the stack has a pipeline measurer for that fact;
- the fact's `describes` type reaches the setting's step through `meta`, either as a direct
  input or along the same sample's lineage.

Otherwise the decision falls to tier 2 or 4, as today. A run-time decision on an
`implementation` or `presence` decision is refused: the graph is fixed at build.

**What the build records.** The setting gets `at_run`: the fact, the measurer, the table
with known facts substituted (each row's `when` on the run-time fact, then its `then`), and a
`fallback`. The fallback is the value the setting would have had without the rule (tier 2, or
an answered tier 4), used when the measurement is undetermined or no row matches. Its `why` is
tier 3, advisory, with the reason "decided at run time by <rule> from <fact> measured by
<measurer>" and every outcome listed.

**What is emitted.**
- The measurer's steps.
- A join that puts the fact into the described channel's `meta` under its `meta_key`.
- The setting's `ext` fragment, as a closure over `meta.<key>`.
  - Rows become a Groovy conditional chain over literals already checked as substitutable.
  - A `{fact:}` row over a derived fact becomes its transform chain in Groovy. `round` is
    `Math.rint` (half to even, as the resolver's `round`), and `log2` is
    `Math.log(x) / Math.log(2)`.
  - The fallback is the last branch.
- The resolver and emitter are tested against the same cases, so the Groovy and the Python
  agree. Nothing outside the closed operations is generated.
- The pipeline records each run-time value it used beside the facts
  (`measurements/decided/<step>.<setting>/<meta.id>.json`).

### E. Confirmation and disagreement

- For each `head` premise that a build decision used, where a `by: code` pipeline measurer
  exists and its input is in the pipeline, the build adds a `MEASURE_<FORMAT>` step. One step
  per input covers every such fact.
- Wiener gets a Wiener-own event `MEASURED`, appended at completion from
  `results/measurements/`. Like `HEARTBEAT`, it is not `FROM_NEXTFLOW`. Its payload is closed:
  the measurement id, sample, value, coverage and measurer, and for decided values the step,
  setting and value.
- The fold keeps the facts. The run's projection compares them with `pipeline.yml`'s premises:
  - equal: confirmed;
  - different: a disagreement, naming every setting and selection whose premise it was.

### F. Showing it

- **Step card:** a run-time setting shows "decided at run time", the rule, the measurer and its
  outcomes table, and the fallback.
- **Run page:** a "Measured in this run" section with each fact, its coverage and measurer, each
  run-time value, and disagreements, flagged and linking to the step.

## Proof

- From a goal with `genome.fasta` and no `genome_length`, the emitted pipeline has the faidx
  and parse steps, the meta join, and a closure for `--genomeSAindexNbases`. A real run (a slow
  gate test with Nextflow and Docker) over the 29,903 bp genome runs STAR with
  `--genomeSAindexNbases 6`. The same goal stating `genome_length` decides at build, with no
  faidx step.
- The Groovy lookup and the resolver agree on the table check's cases, for the STAR chain and
  for an enum table (strandedness → featureCounts `-s`, fact `strandedness` stated as unknown).
- The same `read_length` piece gives the same value from the server, on an uncapped fixture
  with `coverage: all`, and from the pipeline runner.
- A run whose full-data read length differs from the head estimate records `MEASURED`, and its
  projection shows a disagreement naming the aligner selection.
- Refusals: a `by: tool` measurer with `server` in `runs`; a run-time decision over two
  run-time facts; a run-time `implementation` decision; a fact that cannot reach the step's
  `meta`.

## Left to the builder

- Diagnostic wording, per `docs/design/voice.md`.
- The runner's image and how the pieces are staged, within the constraints above.
- Process naming, and how the join into `meta` is written.
- The run page's layout, inside the existing run view's patterns.

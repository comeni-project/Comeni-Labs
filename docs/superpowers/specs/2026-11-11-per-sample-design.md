# Per-sample facts and decisions

Part 5 of #463: issues #466 (per-sample facts and decisions from a design table) and #218
(samples that disagree). Follows measurers and run-time decisions
([its design](2026-11-10-measurers-design.md)).

## Why

The builder plans as if a study were one sample. Every fact is one value, `meta` carries the same
constants for every sample, and a study whose samples differ is either refused or built for
whichever sample was uploaded. Real pipelines are not like that. The operator's direction
(2026-11-11): make this future-proof, not small; a pipeline can fan out and take several inputs,
and where it can it must.

**What eleven nf-core pipelines do with their samplesheets** (rnaseq, sarek, taxprofiler,
quantms, ampliseq, chipseq, atacseq, mag, methylseq, viralrecon, differentialabundance; their
`assets/schema_input.json` and `docs/usage.md` on master, read 2026-11-11):

- **A column sets a tool's parameter per sample.** rnaseq's `strandedness` sets Salmon's library
  type; sarek's tumour `status` adds `-B 3` to bwa and names the normal for Mutect2; mag passes
  each sample's read platform to its aligners.
- **A value routes a sample to another branch.** taxprofiler sends Nanopore and Illumina samples
  to different tools and databases; mag treats short-only, long-only and hybrid rows
  differently; sarek and rnaseq start each row where its input type says (FASTQ, BAM, CRAM).
- **Which inputs a row has.** An empty `fastq_2` makes a sample single-end, and atacseq mixes
  both in one sheet.
- **A value is inferred per sample in the run.** rnaseq's `strandedness: auto` runs Salmon on a
  subsample and passes the result on, with thresholds that apply to the whole run.
- **Samples relate.** Merge: one sample over several lanes or runs is joined before analysis
  (rnaseq, sarek, chipseq, mag, methylseq, viralrecon). Pair: tumour with normal by `patient`;
  a ChIP sample with its `control` and `control_replicate`. Group: mag's co-assembly `group`,
  chipseq's `antibody`, ampliseq's sequencing `run`.
- **A per-sample fact must agree across the study.** mag needs one sheet to be all single-end or
  all paired-end; taxprofiler's run merging needs one endedness per sample.
- **A second table crosses the samples.** taxprofiler profiles every sample against every row of
  a database sheet, each with its own parameters, and skips the pairs a read type rules out.
- **Nobody splits the study into separate pipelines.** Every one branches inside one pipeline.

**What exists in Comeni:**

- `Measurement.per_sample` lets a profile carry a list, one value per sample. A rule comparing a
  list is refused (`MD0312`), and `derives:` can fold a list with `aggregate: {over: cohort,
  using: max|min|mean}`.
- `Channel.scope` is `run` or `sample`. Two or more sample-scoped channels make a samplesheet:
  `sample` plus one column per file, every channel a projection of one `splitCsv`
  (`emit._from_samplesheet`). A blank cell is refused (`emit.py`, "#466").
- A measurement with `describes:` and `meta_key:` joins the input channel's `meta` as a constant
  (`Channel.meta`). `paired` becomes `meta.single_end` this way.
- Part 4: a pipeline measurer's fact joins each sample's `meta` in the run, and a `param`
  decision waiting on exactly one such fact becomes a Groovy lookup over `meta`
  (`mendel_resolver/at_run.py`, `mendel_compiler/groovy_lookup.py`). Implementation and
  presence decisions are never decided in the run.
- `InputPort.cardinality` is `1` or `*` (fan-in with `.collect()`). A shared slot joins two
  per-sample ports `by_sample` or combines a run-scoped one.
- Wiener's browser composes a samplesheet from rows (`runs.py`, `launcher.py`), and Mendel never
  sees its values (invariant 15).
- The upload keeps two files: one sample (`sample_upload.read_heads(keep=2)`).

## The idea

**The build plans for a population of samples, not for one.** A rule over a per-sample fact is
evaluated per sample. The build knows some values (a person stated them for the whole study) and
not others (a samplesheet cell, a measurement in the run). It **evaluates what it knows and keeps
the rest**: a rule whose outcome is settled by known facts folds to a constant; otherwise every
outcome its rows can reach over the fact's declared values goes into the pipeline, and each
sample takes its own in the run. Part 4's run-time lookup is the first case of this. One
evaluator serves both times, as #463 says.

## Goals

### A. Grain

Every channel item and every fact has a **grain**, from a closed set:

| Grain | One item per | Example |
|---|---|---|
| `study` | the analysis | a reference genome, a MultiQC report, the counts matrix |
| `group` | samples sharing a key | a co-assembly group, a patient's tumour and normal |
| `sample` | sample | its reads, its BAM |
| `unit` | lane or run of a sample, before they are merged | one row of a multi-lane sample |
| `part` | piece of an item, split to run in parallel | one chromosome's calls |

- `Scope` (`run`/`sample`) and `Cardinality` (`1`/`*`) are replaced by grain. A port reading
  `*` today reads `study`. No aliases (no users before v0.1.0).
- A port declares the grain it reads; its default is its type's. An output has its input's grain
  unless it **fans out** (`fans_out: part`) or **gathers** (it reads a coarser grain).
- When a producer's grain is finer than a consumer's, the router coarsens it. If the consumer
  takes a list (`many: true` at that grain), it gathers with `groupTuple` keyed on the coarser
  identity and sized by `groupKey`. That way one sample's parts or lanes move on as soon as they
  are all done, and do not wait for the study. Otherwise the router places a **merging** step for
  that type (a role, e.g. cat/fastq for reads, samtools merge for BAMs). If no such step exists,
  the build refuses and names the type.
- A sample never waits for the rest of the study unless a step reads `study` grain.

### B. Fact scope and sources

- A measurement declares `scope: study | sample`, replacing `per_sample`. Every sample-scoped fact
  also says which input it `describes`, as now.
- A sample's value comes from the first of these that has one:
  1. **the samplesheet cell** the lab filled in;
  2. **a measurement in the pipeline**, when a pipeline measurer exists (`auto` or a blank cell);
  3. **the fallback**: the setting's default, the tool's own value, or a value or tool the person
     chose when asked at build time (below).
- **A sample-scoped fact may be settled for the whole study.** It then folds at build time: no
  column, and any branch it rules out is not built. This is the only thing that prunes.
- **Asking, in the conversation** (operator, 11-11). *The same for every sample, or does it vary?*
  is an ordinary question in the chat, like every other. The model reads what the uploads show,
  across several files (H), and proposes an answer with its reasons: "your four uploads all read
  150 bp; build for that?". The person confirms or changes it, and the answer records who gave it
  and on what evidence. An upload's values alone never prune: the proposal does nothing until it
  is accepted (operator, 11-11). A fact with a measurer that the person settles for the study is
  still measured in the run, and a sample that disagrees is flagged as part 4 flags an estimate.
- "It varies" makes a column: required when the fact has no measurer, optional (`auto`) when it
  has one. A measured fact nobody settles is not asked about at all.
- The fallback question (D) is an ordinary question too: the model may propose, the person sees
  and can change it, and a model's answer is flagged for review like every tier-4 answer.
- **Several inputs of the same sample.** A fact belongs to a sample's input: mag's short and long
  reads each have a read length. Where a sample has one input of a type, the fact uses the
  module's `meta_key` (`single_end`). Where it has two, each step sees the facts of the input it
  reads, under the module's names, mapped at the call.
- **Only samples that need it are measured** (my call). A sample whose cell states the fact goes
  past the measuring step; one whose cell is blank or `auto` goes through it. A branch before the
  measurer does this, so a stated sample never waits on a measurement it does not use. A cell is
  a person's statement and is not checked against a measurement.

### C. The samplesheet is generated

The pipeline's design table follows from what it needs:

- `sample`, then `unit` where lanes or runs are merged (A);
- one column per file of each sample-scoped input, as now; a file column may be **blank** where
  the contract allows the input to be absent for that sample (G);
- one column per **sample-scoped fact the lab may state** (B), with its allowed values, plus
  `auto` when a measurer exists;
- one column per **key** that relates samples (E), and per **role** fact that tells them apart.

The pipeline checks every cell when it starts: the allowed values, a key column's format, a
blank only where allowed. It stops naming the row and the column. `pipeline.yml` records the
columns, with their kind, allowed values, whether they are required and why each exists. Wiener's
samplesheet editor reads them from there. A single-sample pipeline with no fact columns keeps
direct inputs.

### D. Everything a per-sample fact can change, through one evaluator

A decision's grain is the finest grain of the facts it reads. A decision at `sample` or `group`
grain whose outcome is not folded compiles into the pipeline:

- **A setting** (`param`): part 4's lookup, generalised. Its `when` may read any number of
  per-sample facts. `hit: first` is evaluated in row order. `hit: unique` is checked at build
  over every combination of declared values: an overlap is refused at load, so the run never
  meets one. The result for each sample is recorded in `decided/<step>.<setting>.tsv` with the
  source of every fact it read.
- **A tool rule** (#460 constraints: `requires`, `forbids`, `produced_when`, groups) whose `when`
  reads a per-sample fact is evaluated per sample. fastp's `save_merged` is set only for paired
  samples, because the contract says merging requires paired input. A sample that breaks a rule
  stops the run before its process starts, naming the sample and the rule. Study-wide rules stay
  in `_run_guards` as now.
- **Which tool a sample goes through** (`implementation`). Every tool the rows can reach is
  routed, with what it needs (STAR needs its index, HISAT2 its own). A `.branch` on `meta` sends
  each sample to its tool, and a `.mix` rejoins them where the next step reads the produced type.
  The branches must produce the same type and states at the rejoin; otherwise the build refuses.
  A step that only feeds one branch, such as building a STAR index, starts only when that branch
  gets its first sample. With no STAR samples, no STAR index is built.
- **Whether a sample goes through a step** (`presence`): the same branch, where one side skips the
  step. Only a step whose output has its input's type can be skipped. Otherwise it is a question
  at build time, as today.
- **A sample no row covers.** At build time, the evaluator works out whether the rows cover every
  value the facts can take, and *undetermined* (a measurement that could not decide) is always one
  of them. A fact's values are its closed list for `boolean` and `enum`. For `integer` and
  `number` they are the number line within the measurement's `minimum` and `maximum`, and rows
  are compared as intervals over the closed comparisons (my call: no schema change). The same
  interval check finds overlaps for `hit: unique`.
- **The fallback for what the rows leave uncovered** (my call), in this order:
  1. a setting's declared default, or the tool's own value for a setting it can do without, as in
     part 4;
  2. otherwise, for a setting with neither or for a tool choice, the person is asked once: a value
     or tool, or "stop the run and name the sample".
  Either way the fallback is listed on the step card before the run and recorded per sample, so
  no sample takes it unseen. No model runs at run time.

Part 4's limits go: a run-time setting may wait on several facts, and implementation and presence
decisions may be made per sample. The graph is still fixed at build time; it now holds branches.

### E. Relations between samples

- **Keys** are a new measurement kind, `key`: a string compared only for equality, such as
  `patient`, `group`, `antibody` or `run`. They are sample-scoped, come from a column, and are
  never measured.
- **Merge.** Rows sharing `sample` with distinct `unit` values are units of one sample (A).
  Duplicate `sample` ids without a unit column stay refused, as today.
- **Group.** A port reading `grain: group` names its key (`by: patient`). Items gather by that key,
  and the step runs once per group.
- **Pair and role.** A port may select members by a fact (`select: {status: tumor}`), and a
  shared slot joins ports **by a key** (`join: by_key, key: patient`), as it joins `by_sample`
  today. Sarek's Mutect2 call is a tumour and a normal port from one channel, joined on
  `patient`. - **A reference to another sample** is a key of its own kind, `sample_ref`: its value is another
  row's `sample` (and `unit` or replicate, where that row has one). A ChIP sample's `control`
  names its input sample. The join takes the referenced sample's item, which may feed several
  samples, so a control is read once and used by each sample that names it. A reference to a row
  that does not exist stops the run naming both rows.
  A group whose members do not fit stops the run naming the group, for example a patient with two
  normals for a port that takes one.
- **Folding samples into one value.** `aggregate` gains `all`, `any`, `agree`, `count` and
  `distinct` beside `max`, `min` and `mean`, over `study` or a group's key. `agree` gives the value
  when every member has the same one, and *undetermined* otherwise. At build time it folds from
  known values. In the run, a reduction step collects the members' facts and its value joins
  every item's `meta`, so the same lookup reads it. A decision that is genuinely study-wide, such
  as one joint caller, uses `agree`. A disagreement there is the fallback or a stop, decided at
  build time.

### F. Fan-out

- **Many items from one.** A sample's item fans out to its parts when its consumer can run on
  parts and the registry has a splitter and a merger for that type. The build does this whenever
  it can, says why, and lets the person turn it off. Parts carry `meta.part`, and the gather is
  grain coarsening (A).
- **One output to many steps** already works: a channel feeds every consumer. Branches (D) are the
  filtered form.
- **Several sample inputs.** A goal may have several sample-scoped inputs: short and long reads,
  reads and a per-sample annotation. They are columns of one row. Either may be blank where the
  contracts allow (G), and steps join them `by_sample`.
- **A second table.** A run input may be a table of items of its own, such as taxprofiler's
  databases, with each row's files and facts. A step reading one sample and one item runs on
  every pair (`.combine`), with the item's facts in `meta` under the table's name. A tool rule
  over both sides filters the pairs; Bracken is not run on Nanopore samples. Wiener's editor
  composes this table like the samplesheet.

### G. Which inputs a sample has

- A file column may be blank where every step reading it allows the input to be absent for a
  sample (an optional port, #460, or one of a pair). An empty `fastq_2` gives single-end.
- A fact may be **read off the row** (`by: sheet`): `paired` is whether `fastq_2` is filled in.
  This is a measurer that reads which columns are present, never a file name, and it runs where
  the row is parsed.
- The per-row placeholder for an absent file is the contract's `absent` value, as for optional
  run inputs now.

### H. Several uploads (#218 step 1)

The model needs to see more than one file (operator, 11-11). The upload takes several samples,
each a file or a pair, up to a limit. Each is measured on the server separately, and its facts
carry which upload they came from. The conversation shows each fact's values across them ("read
length 150 in 3 of 4 uploads, 75 in one"), and the model's characterisation and proposals read
all of them, under the protection level that already governs what an upload may send. A
study-wide decision folds from their `agree` as an estimate (`coverage: head`) once the person
accepts it, and the pipeline confirms it in the run as part 4 does.

### I. Showing it

- **Step cards** list each per-sample outcome with its rows: "samples with read length ≥ 70 →
  STAR; < 70 → HISAT2; neither (undetermined) → stop the run". A per-sample setting lists every
  value it can take, as part 4's does.
- **The graph** draws branches and where they rejoin, groups and pairs, a second table's cross,
  and parts.
- **The run sheet** is the generated samplesheet: columns, allowed values, and why each exists.
- **The run page** shows, per sample, the path it took, the values used and their source (cell,
  measured, fallback), and any disagreement. It reads `decided/` and a new `routed/<decision>.tsv`
  (sample, outcome, rows matched).
- **The forge** can draft the new contract fields (grain, `fans_out`, `select`, `join: by_key`,
  `many`) for an imported tool, through the same checked drafting it uses for constraints. Its
  prompts and checks learn them stage by stage. Drafting measurers stays part 5.1 (#487).

## Non-goals

- Separate pipelines per group of samples (#218's step 3). Branching does it in one pipeline; the
  issue closes with that reason.
- Reading a samplesheet's values at build time. Invariant 15 holds: Mendel never sees cells.
- An SDRF or other design-table importer (quantms). The generated samplesheet is the format. A
  mapping from another table's columns to facts is later work.
- Statistical designs: contrasts, formulas, batch (differentialabundance). They are a second table
  without files and fit F later; not built here.
- Choosing a fact's value with a model at run time.

## Anti-goals

- A sample dropped silently. No route, no match or a broken rule stops the run and names it.
- A branch, value or pair the pipeline can take that is not listed before the run.
- Pairing or grouping by file name. Relations come from key columns.
- A sample waiting for the study when no step needs the study.
- Two evaluators. Build-time folding and the run-time lookup are one evaluator's two modes, and
  they agree case by case (part 4's agreement tests extend to several facts).

## Constraints

- The same goal and recorded decisions give the same pipeline. Branches are ordered by row order,
  columns by a declared order, and unordered sets are sorted before serialising.
- Every run-time value is computed by the closed operations in Groovy, as in part 4.
- Grain, keys, roles and joins are declared in contracts and the vocabulary, and are checked at
  load with coded diagnostics (`diagnostics.yml`, through `coded()`), next codes after `MD0330`.
- `pipeline.yml` changes go with a `SCHEMA_VERSION` bump and an identity migration where stored
  shapes change, as in part 4.
- Registry additions (a merging step such as nf-core cat/fastq) go on the `measurers` branch of
  comeni-registry with `approved_by: unreviewed`.

## The demo (my call)

The shipped RNA-seq example, given a mixed study:

- a samplesheet with three samples: two paired at 150 bp (one over two lanes), one single-end at
  50 bp, each with its own `strandedness` cell;
- the lanes merge with cat/fastq. `paired` is read off the row, `read_length` is measured in the
  run, and the 50 bp sample goes to HISAT2 while the others go to STAR. Both indexes are built
  because both branches have samples, and featureCounts reads each sample's strandedness;
- the run page shows the three paths and where each value came from.

Pairs, groups, a second table and parts have no tool in the shipped registry. They are proven
with fixture contracts in tests, run under Nextflow.

## Stages

Each stage is usable on its own and gets its own plan.

1. **Grain, scope and sources.** Grain replaces scope and cardinality; measurement `scope`;
   sample-scoped facts; the generated samplesheet's fact columns and their checks; the order of
   sources; the "same for every sample?" question; partial evaluation with lookups over several
   facts; tool rules per sample; coverage of the rows and the fallback question.
2. **Several uploads and the conversation.** Several samples uploaded and measured; the model
   reads all of them; the "same for every sample?" question proposed in the chat and confirmed.
   Early, because every later stage is shown through it (operator, 11-11).
3. **Which inputs a sample has.** Blank cells, `by: sheet` facts, mixed single-end and paired-end,
   and several inputs per sample with facts per input.
4. **Branches.** Implementation and presence per sample, the rejoin, steps that start only when
   their branch has a sample, `routed/`, step cards, the graph and the run page.
5. **Relations and folding.** Units and merging steps, keys, groups, pairs and roles, `join:
   by_key`, the new aggregates over the study or a group, at build time and in the run.
6. **Fan-out.** Parts with splitters and mergers, on by default where possible; a second table
   crossed with the samples.

The forge's drafting of new contract fields lands in the stage that adds them.

## Proof

- Per stage, pure tests of the evaluator, router and emitter, and a Nextflow test of the
  emitted pipeline on a small samplesheet that shows the stage's case.
- The evaluator's build-time and run-time answers agree on every combination of declared values
  for the shipped rules and the fixtures.
- The demo runs for real under Docker: three samples, the paths above, `decided/` and `routed/`
  as expected.
- Each new diagnostic is triggered by a test.

## Left to the builder

- The names of IR and artifact fields, and how branch guards and grain are carried in the IR.
- The Groovy of branches, gathers and crosses, as long as gathers are sized with `groupKey`.
- The upload limit in H.
- How the graph draws branches, groups and parts, before the browser check.

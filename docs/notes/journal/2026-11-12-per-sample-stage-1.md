# 2026-11-12: per-sample facts, stage 1 (#466)

[The plan](../../superpowers/plans/2026-11-11-per-sample-stage-1.md), from
[the design](../../superpowers/specs/2026-11-11-per-sample-design.md). Part 5 of #463, stage 1 of
six.

## Where things stand

- **The worked case is strandedness that differs between samples.** Said to vary, it becomes a
  samplesheet column with its three values; each row's cell is checked before any sample is
  processed and reaches that sample's `meta`, so featureCounts reads each sample's own.
- **Built:**
  - grain (study, sample) for channels, types and ports, replacing scope and cardinality;
  - a fact's scope from the type it describes;
  - *it differs between samples* as an answer in the conversation (`constraints.varies`);
  - a rule's cases with *undetermined*, its gaps and overlaps (`mendel_resolver.cases`); a
    `unique` rule over a per-sample fact may not overlap (operator, 11-11);
  - run-time lookups over several facts, each from a cell, a measurement, or a cell measured
    where blank; a fallback that may stop the run naming the sample, asked as its own question;
  - samplesheet fact columns, measuring only blank rows, the decided record with each fact's
    source;
  - tool rules over `fact.<measurement>`, settled per sample;
  - the run sheet, the step card and the run page showing all of it.
- **Reviewed** after every task by a fresh reviewer; each review found real bugs, fixed with a
  test that failed first. Rulings and deferred minors are in the plan's ledger and the minors
  issue.
- **Operator, 11-12:** finish the whole part 5 plan, then 5.1, then part 6, for the full loop;
  only then tune how much responsibility the AI takes.

## Next

Stage 2 of the per-sample design: several uploads and the conversation (brainstormed in the
design already; plan, then build).

## Stage 2: several uploads (same day)

[The plan](../../superpowers/plans/2026-11-12-per-sample-stage-2.md). An upload takes any number
of files (operator: 400–500 genomes is ordinary; keep it simple, one request); mates pair by name;
each sample is measured and kept with the session under its name (operator: stored with the
session). Agreement is recorded; a spread is asked, with a proposal the person confirms. The
model sees spreads, never names. The builder lists every sample with its measurements.

## Stage 3: which inputs a sample has (same day)

[The plan](../../superpowers/plans/2026-11-12-per-sample-stage-3.md). A study can mix paired and
single-end samples: a blank second reads cell makes a sample single-end, and `paired` is read off
the row with no column of its own. The run sheet lets that cell stay blank. Two inputs of one type
per sample wait for a tool that needs them (#489).

## Stage 4: branches (same day)

[The plan](../../superpowers/plans/2026-11-12-per-sample-stage-4.md). A tool chosen from a fact
said to vary is chosen per sample: the build routes once per tool and merges the routes, each
branch guarded by the rows that send samples its way. Read length said to vary gives STAR and
HISAT2 in one pipeline; a stub run sends each sample down its own, never starts an index nobody
needs, and records each sample's tool. One branch point per pipeline for now.

## Stage 5: relations and folding (same day)

[The plan](../../superpowers/plans/2026-11-12-per-sample-stage-5.md). Part A, which the demo uses:
an input may span several rows per sample, and nf-core/cat/fastq merges each sample's lanes before
anything reads them (a one-lane sample passes straight on); a fact folds over the study with
`agree`, `all`, `any`, `count` and `distinct`, at build time and in the run, the two agreeing case
by case. Part B, proven with fixture contracts under Nextflow: keys and groups, a tumour and a
normal paired on a patient, and a sample reading the control it names.


## Stage 6: fan-out (11-13)

[The plan](../../superpowers/plans/2026-11-13-per-sample-stage-6.md). Part A: a step whose port
can run on parts is split before it and merged after it whenever the registry has a splitter
(role `splitting`) and a merger for each output read, and its only per-sample input is the split
one. Each sample's parts merge as soon as they are done, and a person can keep the step whole
(a `whole` decision). Part B: a study input may be a table of several items, and a step reading
a sample and the table runs on every pair, each published under its own name. Both are proven
with fixture contracts under Nextflow; no shipped tool splits or reads a table yet.

# 2026-11-11: measurers and run-time decisions (#465, #217)

[The plan](../../superpowers/plans/2026-11-10-measurers.md), from
[the design](../../superpowers/specs/2026-11-10-measurers-design.md). Part 4 of #463. The forge
drafting measurers is part 5.1, #487 (operator, 11-10).

## Where things stand

- **The worked case is STAR's genome index, decided in the run.** With no genome length stated,
  the build adds samtools faidx and a parser of its `.fai`. The length joins the genome's `meta`,
  and STAR's `--genomeSAindexNbases` is a lookup over it. A real run on nf-core's test genome
  (230,218 bp) gave 8, and recorded it under `decided/`. With 29,903 bp stated, the build still
  decides 6. The shipped RNA-seq example now measures its genome this way.
- **Built:**
  - one `measurer` kind, by our code or by a tool and a parser, with where it runs
    (`registry/measurers/`, replacing `inspectors/` and `profilers/`; `mendel profile` is
    removed);
  - a stdlib inspection core, so a measure runs in a pipeline step on a plain Python image;
  - coverage on every fact (head or all), and a decision may require all of the data;
  - generated measuring steps, routed like any other (`Layers.routing`);
  - run-time decisions: a lookup in Groovy over the closed operations, agreeing with the
    resolver case by case under Nextflow;
  - estimates measured again over all the data, with Wiener reading the run's facts back and
    the run page flagging a disagreement with the decisions built on it;
  - the step card listing every value a run-time setting can take.
- **The registry change** is on a local `measurers` branch of `comeni-registry` (worktree
  `../comeni-registry-measurers`); the submodule points at it. Nothing is pushed. The faidx
  contract says `approved_by: unreviewed` until the operator reviews it.
- **Reviewed** after every task, by a fresh reviewer. Rulings and deferred minors are in the
  plan's *Deviations* and in the minors issue. Three review findings were real bugs: a cut gzip
  read as complete, a join that dropped samples with exit 0, and decided values that were never
  read.
- **To check in the browser at the end of parts 2–5:**
  - the conversation now offers samtools faidx and the measuring step as steps of their own;
  - the step card's run-time block;
  - the run page's "Measured in this run".

## Next

Part 5, per-sample facts and decisions (#466, #218): brainstorm, design, plan.

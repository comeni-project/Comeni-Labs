# Per-sample stage 6: fan-out — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** One sample's work may run in parallel parts. A step that can run on parts is split
before it and merged after it, by default whenever the registry has a splitter and a merger, and
the person can turn this off. A run input may also be a second table, such as several reference
databases: a step reading one sample and one row of that table runs on every pair.

**Architecture:**
- **Part A, parts:**
  - A consumer port declares that it can run on parts (`parts: true`). A splitter is a contract
    with role `splitting` whose output of the same type fans out (`fans_out: part`). The merger
    is the existing `merging` role.
  - After routing, `resolve._with_parts` inserts `split_<step>` before the step and
    `merge_<step>_<port>` after each output something reads, the same kind of IR rewrite as
    stage 5's `_with_units`.
  - In the run, the split output is spread with `flatMap` into items carrying `meta.part` and
    `meta.comeni_parts`. The merger gathers them with `groupKey(meta.id, meta.comeni_parts)`, so
    each sample's parts merge as soon as they are done.
  - `constraints.whole` lists the tools a person keeps whole.
- **Part B, a second table:**
  - `constraints.tables` lists the study-grain inputs a person supplies as a table of several
    items. Their parameter becomes a CSV with a `name` column, one column per file and one per
    item fact a port reads.
  - A step with a sample port and a table port runs on every pair: `.combine`, then `multiMap`
    into its two arguments, with the item's `meta` under the table's name.
  - A port's `select` filters either side before the pairs are made. Wiener's run form composes
    the table as it composes the samplesheet.

**Tech Stack:** Python 3.12, Nextflow DSL2, React + TypeScript.

**Spec:** `docs/superpowers/specs/2026-11-11-per-sample-design.md`: stage 6, Goals A (`part`)
and F.

## Global Constraints

- **Keep it simple** (operator, 11-12):
  - parts and tables are IR or channel rewrites after routing, not new routing concepts;
  - a split goes only where it is plainly safe (below), and everywhere else the step stays whole
    without asking.
- **A split is possible** when all of the following hold:
  - the step's only sample-grain input is the `parts: true` port;
  - the step has no branch guard, and that port has no `select` or `by`;
  - the registry has a splitter for the port's type;
  - every output something reads has a merger.
  When a split is not possible, the step runs whole and nothing is recorded.
- **Every gather is sized with `groupKey`.** A sample never waits for the study unless a step
  reads `study`.
- **Invariant 15 holds:** Mendel never reads cells or table rows. The run checks the table's names
  and files, naming the row.
- **Parts and pairs never overwrite each other's results:**
  - a split step sets `ext.prefix` to `${meta.id}.part${meta.part}`;
  - a crossed step sets it to `${meta.id}_${meta.<table>.id}`.
- **Fixtures, not shipped tools:** no tool in the shipped registry splits, profiles against a
  table or merges parts. Fixture contracts prove them under Nextflow, as stage 5 did. Registry
  (`measurers` branch, `approved_by: unreviewed`): only the role `vocabulary/roles/splitting.yml`.
- **Diagnostics and schema:**
  - new diagnostics start at `MD0346`;
  - `SCHEMA_VERSION` stays 9 (unreleased), with `SERIALISED_SHAPE` updated;
  - shape bumps and migrations where stored shapes change.
- **Process:**
  - per task, targeted tests only, and full checks at the end of each part;
  - commit trailer `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Review Focus

1. **A splitter that makes one part.** Nextflow emits a path, not a list, and the sample still
   flows and merges. Pinned in Task 3.
2. **Two samples with different part counts (1 and 3).** Each merges as soon as its own parts are
   done, and parts never cross samples. Pinned in Task 3 (slow).
3. **Turning parts off.** It rebuilds the pipeline with no split or merge, identical to today's.
   Pinned in Task 2.
4. **Two databases for one sample.** Both results are published under distinct names. Pinned in
   Task 7 (slow).
5. **A table row with a blank or repeated name, or a file that does not exist.** The run stops
   naming the row. Pinned in Task 6.

---

## Part A — parts

### Task 1: Parts declared in contracts

**Files:**
- Modify: `packages/comeni-core/src/comeni_core/plan/tiers.py`: `Grain.PART`, "a piece of one
  sample's item, split to run in parallel".
  - A type's vocabulary grain may not be `part`; that is checked where grains load.
- Modify: `packages/comeni-core/src/comeni_core/declared/contract.py`:
  - `InputPort.parts: bool = False` (excluded when false): the step may run once per part of this
    port's item.
  - `OutputPort.fans_out: Grain | None = None` (excluded when None): only `part` is accepted.
- Modify: `packages/mendel-resolver/src/mendel_resolver/layers.py`: `_check_parts`, at load.
  - **MD0346:** a `fans_out` output on a contract without role `splitting`.
  - **MD0346:** a splitter whose fanned-out output's type is not its one consumed type.
  - **MD0346:** `parts: true` on a port with `many`, `by`, `select` or grain `study`.
- Modify: `packages/comeni-core/src/comeni_core/diagnostics.yml`: MD0346, and regenerate the
  diagnostics doc.
- Test: `packages/mendel-resolver/tests/test_parts.py` (new)
- Fixture: `tests/emit/fixtures/parts.py` (new), a layer with:
  - role `splitting`, role `searching`, type `hits.tsv`;
  - `lab/split_reads@1.0.0`: splitting, `fastq.reads` in, `fastq.reads` out with `fans_out: part`;
  - `lab/search@1.0.0`: searching, reads `parts: true` plus a study `genome.fasta`, `hits.tsv` out;
  - `lab/merge_hits@1.0.0`: merging, `hits.tsv` `many: true` in, `hits.tsv` out;
  - the three Nextflow modules, in the style of `relations.py`.

- [x] **Step 1: Write the failing tests:**
  - the fixture layer loads;
  - each MD0346 case above is refused with its code;
  - a contract round-trips with `parts` and `fans_out`, and one without them serialises as
    before (digests unchanged: compare against a shipped contract's digest).
- [x] **Step 2: Run them.** Expected: FAIL (unknown fields).
- [x] **Step 3: Implement.**
- [x] **Step 4: Run them.** Expected: PASS. Also run `uv run pytest packages/mendel-resolver/tests -q -x`.
- [x] **Step 5: Commit** `feat: a step may run on parts of a sample (#466)`.

### Task 2: The split and the merge placed

**Files:**
- Modify: `packages/comeni-core/src/comeni_core/goal/asked.py`:
  `Constraints.whole: list[ContractId]`, the tools a person keeps whole. Sorted, and excluded
  when empty.
- Modify: `packages/comeni-core/src/comeni_core/plan/ir.py`: `IRNode.parts: Parts | None`
  (excluded when None), with:
  - `on: bool`;
  - `splitter: ContractId`;
  - `mergers: dict[PortName, ContractId]`;
  - `because: str`.
  It is recorded on every step that can be split, on or off, so the step card can offer the
  switch both ways.
- Modify: `packages/mendel-resolver/src/mendel_resolver/resolve.py`:
  - `_with_parts(ir, goal, registry)`, run after `_with_units`;
  - for each node where a split is possible (Global Constraints), pick the splitter and mergers
    by `(-priority, id)`, as `_with_units` does;
  - when the tool is not in `whole`, insert `split_<node>` before the node, rewire the port's
    edge through it, and insert `merge_<node>_<port>` after each output something reads, rewiring
    those readers;
  - the reason reads "<tool> can run on parts of <type>: <splitter> splits each sample and
    <merger> merges the results";
  - the splitter and merger roles are never chosen as producers by routing. Verify with a test,
    and exclude them in `router` only if the test fails.
- Test: `packages/mendel-resolver/tests/test_parts.py`

- [x] **Step 1: Write the failing tests:**
  - the fixture goal (`fastq.reads` and `genome.fasta` → `hits.tsv`) has the node order
    `split_search` → `search` → `merge_search_hits`, with `search.parts.on` and its reason;
  - with `whole: [lab/search@1.0.0]`, the IR equals the IR built without the splitter layer,
    except for `search.parts` with `on: false` (Review Focus 3);
  - with no merger for `hits.tsv`, or with a second per-sample input, there is no split and no
    `parts` record;
  - building twice gives byte-identical IR;
  - the shipped RNA-seq goal is unchanged.
- [x] **Step 2: Run them.** Expected: FAIL.
- [x] **Step 3: Implement.**
- [x] **Step 4: Run them, and the resolver suite.** Expected: PASS.
- [x] **Step 5: Commit** `feat: steps that can run on parts are split and merged (#466)`.

### Task 3: Parts in the run

**Files:**
- Modify: `packages/comeni-core/src/comeni_core/artifact/pipeline.py`:
  - `StepInput.parts: PartsWiring | None`, where `PartsWiring` is `spread` (reads a splitter's
    output) or `gather` (a merger reading one sample's parts);
  - `Step.parts` carries the IR record;
  - validators: `spread` only from a step whose contract fans out, and `gather` only on a
    `many: true` port;
  - add the new fields to `SERIALISED_SHAPE`.
- Modify: `packages/comeni-core/src/comeni_core/artifact/materialise.py`: set both wirings from
  the IR.
- Modify: `packages/mendel-compiler/src/mendel_compiler/emit.py`, in `_port_expression`:
  - `spread`: `.flatMap { meta, parts -> def list = parts instanceof List ? parts : [parts];
    list.withIndex().collect { f, i -> [ meta + [part: i, comeni_parts: list.size()], f ] } }`;
  - `gather`: `.map { meta, f -> [ groupKey(meta.id, meta.comeni_parts), meta, f ] }
    .groupTuple().map { k, metas, files -> [ metas[0].findAll { it.key !in ['part',
    'comeni_parts'] }, files.flatten() ] }`;
  - `_ext_scope` writes `ext.prefix = { "${meta.id}.part${meta.part}" }` for a step with
    `parts.on`.
- Modify: `packages/mendel-compiler/src/mendel_compiler/cli/__init__.py`: the new models in the
  models list, if that list needs them.
- Test: `tests/emit/test_parts.py` (new, pure) and `tests/emit/test_parts_run.py` (new,
  `@pytest.mark.slow`, under Nextflow).

- [x] **Step 1: Write the failing pure tests:**
  - the emitted `SPLIT_READS` output feeds `SEARCH` through the `flatMap`;
  - `MERGE_HITS` reads the `groupKey` gather;
  - downstream reads `MERGE_HITS.out.hits`;
  - the `ext.prefix` line is present;
  - `pipeline.yml` round-trips;
  - a sample rule on `search` is still emitted on the split call.
- [x] **Step 2: Write the failing slow test.** Two samples: the fixture splitter makes 1 part of
  one and 3 of the other.
  - each sample's merged `hits` lists exactly its own parts (Review Focus 1 and 2);
  - the published search outputs have 4 distinct names.
- [x] **Step 3: Run them.** Expected: FAIL.
- [x] **Step 4: Implement.**
- [x] **Step 5: Run them.** Expected: PASS, including `uv run pytest tests/emit -q -m slow -k parts`.
- [x] **Step 6: Commit** `feat: parts run in parallel and merge per sample (#466)`.

### Task 4: The switch, in the builder

**Files:**
- Modify: `packages/mendel-api/src/mendel_api/services/build.py`: `StepView.parts: PartsView |
  None`, with `on`, `splitter`, `mergers` and `because`.
- Modify: `packages/mendel-api/src/mendel_api/services/changes.py`, `decisions.py`,
  `decision_models.py`:
  - a `whole` DecisionChange (contract id, on or off), stored as stage 5 stored `units`;
  - a migration for the stored column;
  - shape bumps in `shape_versions.py`.
- Modify: `packages/mendel-authoring/src/mendel_authoring/payloads.py`, `decisions.py`: the
  `whole` change kind.
- Modify: `frontend/src/build/Settings.tsx`: a "Runs in parts" block with the reason and a
  "Run each sample whole" checkbox that sends the change.
- Run `make client`.
- Registry (`measurers` branch): `vocabulary/roles/splitting.yml`, then commit there and fetch
  into the submodule.
- Test:
  - `packages/mendel-api/tests/pipelines/test_parts_view.py` (new);
  - a `Settings.test.tsx` case;
  - `make test-db` after the migration.

- [x] **Step 1: Write the failing tests:**
  - the view carries `parts` for the fixture build;
  - the `whole` change rebuilds without the split, and turning it back on restores it;
  - the checkbox sends `{kind: "whole", ...}`.
- [x] **Step 2: Run them.** Expected: FAIL.
- [x] **Step 3: Implement.**
- [x] **Step 4: Run them.** Expected: PASS.
- [x] **Step 5: Commit** `feat: a person can keep a step whole (#466)`.

### Task 5: Part A docs and checks

- [x] **Step 1:**
  - `contract-schema.md`: `parts` and `fans_out`;
  - `goal-schema.md`: `whole`;
  - `pipeline-schema.md`: `StepInput.parts` and `Step.parts`;
  - `CHANGELOG.md`.
- [x] **Step 2:** `make check`, `make guards`, slow, `npx vitest run`, `npx tsc -b`, each run
  separately. Expected: all green.
- [x] **Step 3: Commit** `docs: parts (#466)`.

---

## Part B — a second table

### Task 6: A table input

**Files:**
- Modify: `packages/comeni-core/src/comeni_core/goal/asked.py`: `Constraints.tables:
  list[TypeId]`. Sorted, and excluded when empty.
- Modify: `packages/mendel-resolver/src/mendel_resolver/resolve.py`: `_check_tables`.
  - **MD0347:** a type the goal does not have.
  - **MD0347:** a type whose grain is not `study`.
  - **MD0347:** a type that is also in `units`.
- Modify: `packages/comeni-core/src/comeni_core/artifact/pipeline.py`: `Channel.table:
  TableShape | None`, with:
  - `columns: list[PortName]`, the file columns;
  - `facts: list[MeasurementId]`, the item facts a port's `select` reads. They are sorted, and
    each describes this type.
  The table's parameter is the channel's own param, and `SERIALISED_SHAPE` is updated.
- Modify: `packages/comeni-core/src/comeni_core/artifact/materialise.py`: build `Channel.table`
  for each type in `tables`.
- Modify: `packages/mendel-compiler/src/mendel_compiler/emit.py`, `_table(channel)`:
  - `Channel.fromPath(params.<p>, checkIfExists: true).splitCsv(header: true)`;
  - a check that stops the run on a blank or repeated `name`, naming the row;
  - files resolved with `file(..., checkIfExists: true)`;
  - mapped to `[ [id: row.name, <facts>], files... ]`;
  - `test_samplesheet`'s companion writes a two-row test table.
- Modify: `packages/comeni-core/src/comeni_core/diagnostics.yml`: MD0347.
- Fixture: `tests/emit/fixtures/tables.py` (new), with:
  - type `database.index` (study), and a measurement `db_type` (enum `short`, `long`) that
    describes it;
  - type `profile.tsv`;
  - `lab/profile@1.0.0`: `reads` (sample) and `db` (`database.index`) in, `profile.tsv` out;
  - its module.
- Test: `packages/mendel-resolver/tests/test_tables.py` (new), `tests/emit/test_tables.py` (new).

- [x] **Step 1: Write the failing tests:**
  - each MD0347 case;
  - the channel's `table` columns and facts;
  - the emitted table channel and its checks, including a blank name, a repeated name and a
    missing file (Review Focus 5) in a slow test with a two-row table;
  - without `tables`, the pipeline is today's exactly.
- [x] **Step 2: Run them.** Expected: FAIL.
- [x] **Step 3: Implement.**
- [x] **Step 4: Run them.** Expected: PASS.
- [x] **Step 5: Commit** `feat: a run input may be a table of several items (#466)`.

### Task 7: Every sample against every row

**Files:**
- Modify: `packages/mendel-compiler/src/mendel_compiler/emit.py`, `_crossed(pipeline, step)`:
  - for a step reading a sample port and a table port, emit
    `ch_cross_<step> = <sample>.combine(<table>).multiMap { ... }` with
    `sample: [ meta + [<table>: tmeta], a... ]` and the table argument in the shape its `NfInput`
    takes;
  - a port's `select` filters its own side before the combine;
  - `ext.prefix = { "${meta.id}_${meta.<table>.id}" }`;
  - a check that each sample meets at least one row, which stops the run naming the sample
    rather than dropping it.
- Modify: `packages/comeni-core/src/comeni_core/artifact/materialise.py`: **MD0348** refuses a
  step that joins a crossed output with another channel by sample, because it would pair with
  only one row. Gathering to the study and reading the output alone stay allowed.
- Modify: `packages/comeni-core/src/comeni_core/diagnostics.yml`: MD0348.
- Test: `tests/emit/test_tables.py`, `tests/emit/test_tables_run.py` (new, slow).

- [x] **Step 1: Write the failing tests:**
  - pure: the combine, the `multiMap`, the meta key, the `select` on `db_type` filtering items
    and the prefix;
  - MD0348 for a by-sample join downstream;
  - slow: 2 samples × 2 databases give 4 profiles with distinct published names
    (Review Focus 4);
  - slow: a `select: {db_type: short}` leaves 2;
  - slow: a sample left with no row stops the run naming it.
- [x] **Step 2: Run them.** Expected: FAIL.
- [x] **Step 3: Implement.**
- [x] **Step 4: Run them.** Expected: PASS.
- [x] **Step 5: Commit** `feat: a step crosses each sample with each row of a table (#466)`.

### Task 8: The table in the builder and the run form

**Files:**
- Modify: `packages/mendel-api/...`:
  - a `tables` DecisionChange on the input revision, stored as `units` is;
  - a migration and shape bumps.
- Modify: `packages/mendel-authoring/...`: the `tables` change kind.
- Modify: `frontend/src/build/CurrentFacts.tsx`: a "Several of these (a table)" checkbox on a
  study input, threaded the way `onUnits` is.
- Modify: `packages/wiener-api/src/wiener_api/services/artifacts.py`: `input_tables(artifact_id)`
  returns each table's param, columns (`name`, then file columns, then facts) and the facts'
  allowed values.
- Modify: `packages/wiener-api/src/wiener_api/routes/runs.py`: the view's `tables` field. The
  launcher already writes any row-list parameter as a CSV.
- Modify: `frontend/src/build/Samplesheet.tsx`: its first column becomes a prop (`sample` or
  `name`), so `Submit.tsx` renders one editor per table under its parameter.
- Run `make client`.
- Test: an API test, Wiener `input_tables` and route tests, and `CurrentFacts`, `Submit` and
  `Samplesheet` vitest cases.

- [x] **Step 1: Write the failing tests.**
- [x] **Step 2: Run them.** Expected: FAIL.
- [x] **Step 3: Implement.**
- [x] **Step 4: Run them.** Expected: PASS.
- [x] **Step 5: Commit** `feat: a second table in the builder and the run form (#466)`.

### Task 9: Docs, checks and review

- [x] **Step 1: Docs:**
  - `goal-schema.md`: `tables`;
  - `pipeline-schema.md`: `Channel.table`;
  - `run.md`: the table editor;
  - `CHANGELOG.md`;
  - the journal note.
- [x] **Step 2:** the full checks, each run separately. Expected: all green.
- [x] **Step 3:** a fresh opus reviewer on the stage, with this Review Focus.
  - Fix the Critical and Important findings with tests that fail first.
  - Post the minors to #489.
- [x] **Step 4:** tick this plan, and record the deviations.

---

## Deviations

- **Splitters and mergers are never routed** (Task 3). Routed, the fixture merger became the
  wanted output's producer and gathered the study into one, so `Registry.producers_of` excludes
  the `splitting` and `merging` roles.
- **The switch is on the living builder's step sheet** (Task 4), not `Settings.tsx`: that is
  the card the builder opens, beside the optional-input switches. `whole` is its own decision
  family (`pipeline_whole`), and drafts moved to shape 4 because `Grain` gained `part`.
- **`Parts` uses declared shapes** (Task 5): mergers are a list of `PartsMerger` records and the
  reason is a `Line`, because a pipeline is a model payload.
- **Tasks 6 and 7 landed as one commit.** A table's items sit on `meta` under the type's family
  (`database`), not the channel name. Item facts are table columns, not samplesheet columns, so
  `_relations` and the pipeline validator skip them. MD0344 lets a port select on its own type's
  fact.
- **The builder's checkboxes read each input's grain** from the built channels (Task 8): lanes
  only on per-sample inputs, which fixes a stage 5 minor, and a table only on study inputs.
  Wiener's view separates a table's file `columns` from its optional `facts`.
- **Final review fixes** (`ce5ba542`):
  - the cross is a pass over finished calls, so a branch's filter, a tool rule or measured facts
    wrap the sample input before the pairs are made;
  - every step after a cross is named per pair until a gather, and a join, group or parts
    gather there is refused (MD0348), as is a step reading two tables;
  - a select on a study input that is not a table is refused (MD0347);
  - a step crossing a table, or after one, is never split;
  - a contract's own prefix is suffixed, not dropped;
  - parts gather on the sample's whole `meta` and merge in part order;
  - a splitter making no parts stops the run.
  The minors are on #489.

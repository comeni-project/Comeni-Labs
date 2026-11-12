# Per-sample stage 5: relations and folding — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Samples relate to each other. A sample may span several lanes, which are merged before
anything reads it. Samples may share a key (a patient, a group), and a step may run once per group
or take a tumour and a normal of one patient together. A sample may name another as its control.
A fact may be folded over the study or a group (`agree`, `all`, `any`, `count`, `distinct`), both
at build time and in the run.

**Architecture:**
- **Part A, what the demo uses:** units, merging and folding.
  - A goal says which input may span several rows per sample (`constraints.units`).
  - The build then inserts the type's merging step (a role, `merging`) between the input and
    everything reading it. In the run, rows are grouped by sample with `groupKey` sized from the
    samplesheet: a one-row sample passes straight on, and a sample with several rows is merged.
  - The new aggregates fold known values at build time. In the run, a reduction over the study's
    or a group's items joins its value into each item's `meta`, so the existing lookup reads it.
- **Part B, relations proven with fixtures:**
  - A new measurement kind `key`, from a column and never measured. A port reads
    `grain: group, by: <key>`, and items gather per key, sized by the samplesheet.
  - A port selects members by a fact (`select`), and an input joins ports on a key
    (`join: by_key`).
  - A `sample_ref` kind names another row's sample; the run joins that sample's item and stops
    naming both rows when it does not exist.

**Tech Stack:** Python 3.12, Nextflow DSL2, React + TypeScript.

**Spec:** `docs/superpowers/specs/2026-11-11-per-sample-design.md`: stage 5, Goals A (`unit`,
`group`) and E.

## Global Constraints

- Keep it simple (operator, 11-12):
  - units are an IR rewrite after routing (one merging node per declared type), not a new
    routing concept;
  - groups and pairs are port declarations the emitter reads.
- Every gather is sized with `groupKey`, from counts the projection computes off the samplesheet
  rows. A sample never waits for the study unless a step reads `study`.
- Invariant 15 holds: Mendel never reads cells. Sizes, keys and references are checked by the run,
  naming the rows.
- Registry additions (`nf-core/cat/fastq`, the `merging` role) go on the `measurers` branch with
  `approved_by: unreviewed`.
- New diagnostics from `MD0340`. `SCHEMA_VERSION` bump to 10 for `pipeline.yml`; shape bumps with
  migrations where stored shapes change.
- Per task: targeted tests. Full checks at the end of each part. Commit trailer
  `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Review Focus

1. **A sample with one lane beside one with three.** The first passes straight on and the second is merged; neither waits for the other. Pinned in Task 2 (slow).
2. **Lanes of one sample that disagree** (one paired, one single-end). The run stops naming the sample. Pinned in Task 2.
3. **`agree` over samples that disagree.** It is undetermined, so the lookup's fallback or a stop applies, never the first sample's value. Pinned in Task 3.
4. **A patient with two normals** for a port that takes one. The run stops naming the patient. Pinned in Task 5 (slow).
5. **A control that names no row.** The run stops naming both rows. Pinned in Task 6.

---

## Part A — units, merging and folding

### Task 1: Units declared, and the merging step placed

**Files:**
- Modify: `packages/comeni-core/src/comeni_core/plan/tiers.py`: `Grain.UNIT`.
- Modify: `packages/comeni-core/src/comeni_core/goal/asked.py`: `Constraints.units: list[TypeId]`, the inputs whose rows may repeat a sample. Valid only for a goal input at `sample` grain (MD0340).
- Modify: `packages/mendel-resolver/src/mendel_resolver/resolve.py`: `_merged_units(ir, goal, registry)`, run after routing.
  - For each type in `units`, place the contract filling role `merging` that consumes and produces that type, as node `merge_<type>`. Its presence reason is "a sample may span several rows of <type>".
  - Rewire every edge-less consumer of that input to read the merging node.
  - No merging contract for the type is MD0341, naming the type.
- Modify: `artifact/materialise.py`: the input channel's grain is `unit`.
- Registry (`measurers` branch): `tools/nf-core/cat/fastq/contract.yml` (role `merging`, `fastq.reads` in, grain `sample`, `many: true`; out `fastq.reads`), and the role in `vocabulary/roles.yml`.
- Test: `packages/mendel-resolver/tests/test_units.py` (new)

- [x] **Step 1: Write the failing tests:**
  - with `units: [fastq.reads]`, the RNA-seq goal has `merge_fastq_reads` (cat/fastq) feeding trimming, with its reason;
  - without, the pipeline is today's exactly;
  - `units` on a study input is MD0340;
  - a type with no merging contract is MD0341.
- [x] **Step 2: Run them.** Expected: FAIL.
- [x] **Step 3: Implement.**
- [x] **Step 4: Run** the resolver, core and registry tests. Expected: pass.
- [x] **Step 5: Commit** `feat: an input may span several rows per sample; its merging step is placed (#466)`.

### Task 2: Lanes merged in the run

**Files:**
- Modify: `packages/mendel-compiler/src/mendel_compiler/emit.py`:
  - the projection of a `unit`-grain channel keeps one item per row, with `meta.id` the sample and `meta.unit` the row's `unit` cell;
  - the merge input is `groupTuple` on `groupKey(meta, n)`, where `n` is that sample's row count from the sheet;
  - one-row samples skip the merging step, and the two streams `mix`;
  - the duplicate-id check refuses a repeated `(sample, unit)` and allows repeated samples;
  - units of one sample that differ in `single_end` stop the run naming the sample.
- Modify: `test_samplesheet` (two rows for one sample) and Wiener's run form (`unit` column).
- Test: `tests/emit/test_units.py` (new: pure, and slow with S1 over three lanes and S2 over one)

- [x] **Step 1: Write the failing tests** (Review Focus 1 and 2).
- [x] **Step 2: Run them.** Expected: FAIL.
- [x] **Step 3: Implement.**
- [x] **Step 4: Run** the pure tests, then the slow ones. Expected: pass.
- [x] **Step 5: Commit** `feat: a sample's lanes are merged in the run, one-lane samples pass straight on (#466)`.

### Task 3: Folding a fact over the study

**Files:**
- Modify: `packages/mendel-resolver/src/mendel_resolver/rules/format.py`: `Aggregate.using` gains `all`, `any`, `agree`, `count` and `distinct`.
  - `over` is `study`, or a key `group: <key>` (Part B).
  - `agree` gives the shared value, or undetermined when members differ.
- Modify: `premises.py` `_REDUCERS`: the same folds at build time over known values.
- Modify:
  - `at_run.py`: a derived aggregate over a varying fact is decided in the run (`_bases` already follows `aggregate`);
  - `comeni_core/plan/at_run.py`: `MetaAtRun.folded: Literal[...] | None`, a fact the run folds;
  - `emit.py`: a reduction `ch.map { it[0].<fact> }.toList().map { <fold> }` combined into every item's `meta`, before any lookup reads it.
- Test: `packages/mendel-resolver/tests/test_folding.py` (new), and extend `tests/emit/test_at_run_agreement.py` so every fold agrees at build time and in the run on every case (Review Focus 3).

- [x] **Step 1: Write the failing tests:**
  - `agree` over 150, 150 is 150; over 150, 75 it is undetermined;
  - `count` and `distinct` count;
  - a rule reading `agree(read_length)` with read length varying is decided in the run, and its lookup reads the folded value;
  - build time and run time agree on every case.
- [x] **Step 2: Run them.** Expected: FAIL.
- [x] **Step 3: Implement.**
- [x] **Step 4: Run** the resolver tests and the agreement tests (slow). Expected: pass.
- [x] **Step 5: Commit** `feat: a fact folds over the study at build time and in the run (#466)`.

### Task 4: Shown, and the end of Part A

**Files:**
- Modify:
  - the inputs card in `frontend/src/build/living/`: *a sample may span several rows*, a toggle that sets `units`;
  - `Samplesheet.tsx`: a `unit` column when the input has units;
  - the step card: the merging step's reason, and a folded fact as `agree(read_length) over the study`.
- `make client`. Docs:
  - the goal schema's `units`;
  - the rule schema's aggregates;
  - the run how-to's lanes.

  `CHANGELOG.md`.
- [x] **Step 1: Write the failing tests:** the toggle sets `units`; the editor adds a `unit` column and allows a repeated sample.
- [x] **Step 2: Implement.** Run `npx vitest run` and `npx tsc -b`.
- [x] **Step 3:** Run `make check`, `make guards`, `make slow`, separately. Expected: pass.
- [x] **Step 4: Commit** `feat: lanes and folded facts in the builder (#466)`.

## Part B — keys, groups, pairs and references (fixture contracts)

### Task 5: Keys and groups

**Files:**
- Modify: `declared/measurement.py`: `MeasurementKind.KEY`, an identifier compared for equality, at sample grain, never measured (a measurer for a key is MD0342).
- Modify: `declared/contract.py`: a port's `by: <key>` with `grain: group` (MD0343 when `by` names no key, or appears without `grain: group`).
- Modify: `emit.py`:
  - a key is a sheet column checked as an identifier;
  - the projection puts each group's size on `meta.comeni_size.<key>`;
  - a `group` port reads `groupTuple` on `groupKey([<key>: value], size)`.
- Test: `tests/emit/test_groups.py`, with the fixture `fixtures/constraints/coassemble.yml` (one run per `group`). Slow: two groups of two and one samples.

- [ ] **Step 1–5:** failing tests, implement, run, commit `feat: samples sharing a key run together as a group (#466)`.

### Task 6: Pairs, roles and references

**Files:**
- Modify: `declared/contract.py`:
  - a port's `select: {<fact>: <value>}`;
  - `NfInput.join: by_key` with `key: <key>` (MD0344 when the key is not one);
  - `MeasurementKind.SAMPLE_REF`.
- Modify: `emit.py`:
  - each selecting port filters its channel;
  - `by_key` joins on `meta.<key>` with `failOnDuplicate` and `failOnMismatch`, so a patient with two normals stops the run naming the patient;
  - a `sample_ref` port joins the referenced sample's item, which may feed several samples;
  - a reference to no row stops the run naming both rows, checked in the projection.
- Test: `tests/emit/test_pairs.py`, with the fixtures `mutect_like.yml` (tumour and normal on `patient`) and `chip_like.yml` (`control`). Slow: Review Focus 4 and 5.

- [ ] **Step 1–5:** failing tests, implement, run, commit `feat: tumour and normal pair on a key; a sample may name its control (#466)`.

### Task 7: Docs and the end of the part

- [ ] **Step 1:** Docs:
  - the measurement schema's `key` and `sample_ref`;
  - the contract schema's `grain: group`, `by`, `select` and `join: by_key`;
  - the samplesheet's key columns in the run how-to.

  `CHANGELOG.md`, the journal. Tick this plan; record its deviations.
- [ ] **Step 2:** Run `make check`, `make guards`, `make slow`, `npx vitest run` and `npx tsc -b`, separately. Expected: pass.
- [ ] **Step 3: Commit** `docs: relations between samples (#466)`.

## Deviations

- **No `unit` grain.** The channel stays `sample` grain and says `units: true`, since a new
  grain would have to be taught to every per-sample check. The merge is emitted as a prelude, so
  the rest of the emitter sees one item per sample. `units` also makes the input a samplesheet
  (MD0340 otherwise).
- Lanes are gathered by sample id and must agree on every `meta` key; otherwise the run stops
  naming the sample. The `unit` column is optional on the run form.
- `aggregate.over` is `study` (was `cohort`), renamed rather than aliased. A fold is carried as a
  run-time fact (`source: folded`, `folds`, `using`), not a `MetaAtRun.folded`.
- `agree` with any member missing is undetermined. Build-time `all` and `any` count only `true`,
  as the run does; the agreement test found the mismatch.
- The lanes toggle is a checkbox on each held input in *What was understood*. The model does not
  yet propose `units`, and the toggle is also offered on study inputs, where the build refuses
  (#489).
- Registry tests that hard-coded the shipped contracts and tool pages now count the layer's files.

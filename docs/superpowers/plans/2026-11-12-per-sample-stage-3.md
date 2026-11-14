# Per-sample stage 3: which inputs a sample has — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A study can mix paired-end and single-end samples. A blank second reads cell makes a
sample single-end, and whether it is paired is read off the row, with no column of its own.
Each sample reaches every module with its own `single_end`.

**Architecture:**
- A type declares that its second column may be left blank (`second_may_be_blank`).
- A measurement may be read off the row (`row: second_file_present`).
- When such a fact is said to vary, it becomes a samplesheet fact with no column: the
  projection sets it from whether the row's second file is there, and passes one file or two.
- The run sheet lets that column stay blank.

**Tech Stack:** Python 3.12, Nextflow DSL2, React + TypeScript.

**Spec:** `docs/superpowers/specs/2026-11-11-per-sample-design.md`: stage 3, Goal G.

## Global Constraints

- Keep it simple (operator, 11-12): no new concept beyond the two declared fields; a fact read off the row reuses `SheetFact`.
- A sample with two inputs of one type (short and long reads, each with its own facts) is not built: no registry tool needs it yet (my call; the spec's G item waits for a tool).
- Registry edits go on the `measurers` branch of comeni-registry.
- Per task: targeted tests; full checks at the end of the part. Commit trailer `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Review Focus

1. **A study with one single-end sample among paired ones.** It runs; its tools see `single_end: true` and one file. Pinned in Task 2, slow.
2. **A blank second cell when pairing is stated for every sample.** The run stops naming the row; one file is never passed as a pair. Pinned in Task 2.
3. **The run sheet with pairing varying.** `reads_2` may be blank and nothing else may. Pinned in Task 3.

---

### Task 1: Declarations

**Files:**
- Modify: `packages/comeni-core/src/comeni_core/declared/vocabulary.py` (`TypeDeclaration.second_may_be_blank: bool = False`, carried as `Vocabulary.blank_second: set[TypeId]`)
- Modify: `packages/comeni-core/src/comeni_core/declared/measurement.py` (`Measurement.row: Literal["second_file_present"] | None = None`: the fact is read off the row, true when the second file is given; valid only for a boolean describing a type whose second column may be blank, checked at load as MD0338)
- Registry: `vocabulary/types/fastq.reads.yml` (`second_may_be_blank: true`), `vocabulary/measurements/paired.yml` (`row: second_file_present`)
- Docs: vocabulary and measurement schema pages
- Test: `tests/registry/test_row_facts.py` (new)

- [x] **Step 1: Write the failing tests:** `fastq.reads` may leave its second column blank; `paired` is read off the row; `row:` on a non-boolean, or on a type without a blank-able second column, is refused (MD0338).
- [x] **Step 2: Run them.** Expected: FAIL.
- [x] **Step 3: Implement.**
- [x] **Step 4: Run** `tests/registry` and `packages/comeni-core/tests`. Expected: pass.
- [x] **Step 5: Commit** `feat: a type's second column may be blank; a fact may be read off the row (#466)`.

### Task 2: The pipeline reads pairing off each row

**Files:**
- Modify: `packages/comeni-core/src/comeni_core/artifact/pipeline.py` (`SheetFact.from_row`: the row fact; then `column` is the type's second column and no column is added)
- Modify: `packages/comeni-core/src/comeni_core/artifact/materialise.py` (`_sheet_facts`: a varying fact with `row` gets no column of its own)
- Modify: `packages/mendel-compiler/src/mendel_compiler/emit.py`:
  - `_cells`: the row fact is `row.<second> != null && row.<second>.trim() != ''`;
  - the projection passes `[file(first)]` when the second is blank and both otherwise;
  - with pairing stated for every sample, a blank second cell stops the run naming the row.
- Modify: `test_samplesheet` (the test row keeps both files)
- Test: `tests/emit/test_row_facts.py` (new: pure, and one slow stub run with a single-end row)

- [x] **Step 1: Write the failing tests:**
  - with `varies: [paired]`, the pipeline has no `paired` column, and `meta.paired`/`single_end` come from the row;
  - the emitted projection passes one file for a blank second cell;
  - with `paired: true` stated, a blank second cell stops the run (`samplesheet row 2 (sample S2), column reads_2 is required: every sample is paired`);
  - slow: a stub run with one paired and one single-end row completes.
- [x] **Step 2: Run them.** Expected: FAIL.
- [x] **Step 3: Implement.**
- [x] **Step 4: Run** `tests/emit -m "not slow"`, then the slow test. Expected: pass.
- [x] **Step 5: Commit** `feat: a blank second reads cell makes a sample single-end (#466)`.

### Task 3: The run sheet

**Files:**
- Modify: `packages/wiener-api/src/wiener_api/services/artifacts.py` and `routes/runs.py` (`input_optional_columns`: the second columns a row may leave blank)
- Modify: `frontend/src/build/Samplesheet.tsx`, `useSubmit.ts` (`incomplete` skips them)
- `make client`
- Test: the Wiener samplesheet test, `Samplesheet.test.tsx`

- [x] **Step 1: Write the failing tests:** with pairing varying, `reads_2` is optional on the run form and in the editor; without, it is required.
- [x] **Step 2: Run them.** Expected: FAIL.
- [x] **Step 3: Implement.**
- [x] **Step 4: Run** the Wiener tests, `npx vitest run` and `npx tsc -b`. Expected: pass.
- [x] **Step 5: Commit** `feat: the run sheet lets a single-end sample leave its second file blank (#466)`.

### Task 4: Docs and the end of the part

- [x] **Step 1:** Docs (the run how-to, the schemas), `CHANGELOG.md`, the journal. Tick this plan and record its deviations.
- [x] **Step 2:** Run `make check`, `make guards`, `make slow`, `npx vitest run` and `npx tsc -b`, separately. Expected: pass.
- [x] **Step 3: Commit** `docs: mixed single-end and paired samples (#466)`.

## Deviations

- A sample with two inputs of one type (short and long reads, each with its own facts) was not
  built, as the constraints say: no registry tool needs it yet (#489).
- A blank file cell in the projection names the sample and the column, not the row number (#489).
- The end checks found three slips, fixed in ac7d8b77: `SheetFact.from_row` became a closed
  vocabulary (`RowFact`) for the egress guard; two overlay fixtures that redeclare `fastq.reads`
  now keep `second_may_be_blank`; the forge constructors fixture was regenerated.

# Per-sample stage 2: several uploads and the conversation — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A person uploads several samples at once. Each is measured separately. Where the
samples agree, the value is recorded as today. Where they disagree, the conversation asks
*the same for every sample, or does it vary?*, or, for a fact that cannot vary yet, *which
should the pipeline be built for?*, with the measured split shown and an answer proposed for the
person to confirm. The model reads every uploaded file, not only the first.

**Architecture:** The upload route groups the files it keeps into samples (a file, or a pair by
mate naming). `inspect.inspect_samples` measures each sample with the existing runner.
`samples.record_inspection` records a fact the samples agree on, and turns a disagreement into
an open question on that fact. The question carries the split and a proposed answer, through the
existing suggestion that pre-fills a gap and waits for a click. The characterisation job gets one excerpt per file.

**Tech Stack:** Python 3.12 (FastAPI, pydantic), React + TypeScript.

**Spec:** `docs/superpowers/specs/2026-11-11-per-sample-design.md`: stage 2 of its Stages; Goals B
("Asking, in the conversation") and H.

## Global Constraints

- An upload never prunes on its own: a proposal derived from uploads does nothing until a person accepts it (operator, 11-11).
- Nothing about a sample is written to disk; only each file's first 4 MB is kept, in memory (14.7.6's ruling, `sample_upload`).
- The protection level governs what a file may send to a model (`protection.Crossing`). An excerpt reaches a model only where it does today.
- Each fact keeps which upload it came from (`Fact.sample`).
- Model calls use declared AI points and typed egress payloads; offered ids are validated where they are received.
- New diagnostics go in `diagnostics.yml` through `coded()`. Changed stored shapes get version bumps and a migration.
- Per task: targeted tests only. `make check`, guards and the slow runs run once at the end of the part (operator, 11-11).
- After each task, a fresh reviewer (opus) reviews it, and its findings are fixed before the next task.
- Commit trailer: `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Review Focus

1. **Files that do not pair** (an `_R1` without its `_R2`, three files called `a_1`, `a_2`, `b_1`). Each unpaired file is a sample of its own. The card says which files made each sample, and refuses nothing silently. Pinned in Task 1.
2. **Uploads that agree on one fact and disagree on another.** The agreeing fact is recorded and the disagreeing one is asked. Neither waits for the other. Pinned in Task 3.
3. **A disagreement on a fact the person already stated.** The person's word stands, and the split is reported as today's disagreement (`kept`/`disagreed`), never asked again. Pinned in Task 3.
4. **More files than the limit.** They are refused, naming the limit, before any file is inspected. Pinned in Task 1.
5. **One sample's file nothing reads, among others that are read.** The read ones are recorded. The unread one is named on the card, and only it goes to the model's reading. Pinned in Tasks 2 and 4.

---

### Task 1: Several samples in one upload

**Files:**
- Modify: `packages/mendel-api/src/mendel_api/services/sample_upload.py` (`MAX_FILES`, `samples_of`)
- Modify: `packages/mendel-api/src/mendel_api/routes/authoring.py` (`upload_sample`: the file count check)
- Modify: `packages/mendel-authoring/src/mendel_authoring/commands.py` (`UploadSample.files` grouped: a tuple of samples)
- Modify: `diagnostics.yml` (`MI0214` text)
- Test: `packages/mendel-api/tests/authoring/samples/test_upload_grouping.py` (new, pure)

**Interfaces:**
- Produces:
  - `MAX_FILES = 8`.
  - `samples_of(files: list[tuple[str, bytes]], sizes: tuple[int, ...]) -> list[Sample]`, where `Sample` is a frozen dataclass with `label: str`, `files: list[tuple[str, bytes]]` and `sizes: tuple[int, ...]`.
  - Two files pair when their names differ only in a mate token (`_R1`/`_R2`, `_1`/`_2`, `.1`/`.2`, before the extension). The label is the shared stem. Every other file is a sample of its own, labelled by its stem.
  - Order follows the upload. Duplicate labels get `#2`, `#3`.
  - `UploadSample.samples: tuple[Sample, ...]` replaces `files`.

- [ ] **Step 1: Write the failing tests:**
  - `test_two_mates_are_one_sample`: `a_R1.fq.gz` and `a_R2.fq.gz` give one sample, `a`, with both files.
  - `test_unpaired_files_are_samples_of_their_own`: `a_1.fq`, `a_2.fq` and `b_1.fq` give `a` (two files) and `b_1` (one).
  - `test_four_pairs_are_four_samples`: eight files.
  - `test_too_many_files_are_refused`: nine files raise `MI0214` naming 8.
  - `test_sizes_follow_their_files` across a regrouping.
- [ ] **Step 2: Run them.** Expected: FAIL.
- [ ] **Step 3: Implement.** The route keeps `MAX_FILES` heads (`read_heads(keep=MAX_FILES)`) and refuses more before inspecting. The command carries samples. `_upload` loops over them (Task 2).
- [ ] **Step 4: Run** the new tests and `packages/mendel-api/tests/authoring/samples`. Expected: pass.
- [ ] **Step 5: Commit** `feat: an upload may hold several samples (#466, #218)`.

### Task 2: Each sample measured on its own

**Files:**
- Modify: `packages/mendel-api/src/mendel_api/services/inspect.py` (`inspect_samples`)
- Modify: `packages/mendel-api/src/mendel_api/stages/samples.py` (`_upload` loops; `Uploaded` carries one inspection per sample)
- Modify: the `SampleInspected` route view: per-sample outcomes, with the files that made each
- Test: `packages/mendel-api/tests/authoring/samples/test_several_samples.py` (new, DB)

**Interfaces:**
- Consumes: `Sample` (Task 1).
- Produces:
  - `inspect_samples(samples: list[Sample], stack, claimed: str | None) -> list[tuple[str, Inspection]]`: one `inspect_sample` per sample, in order, each never raising.
  - `SampleInspected.samples: list[SampleOutcomeView]`, each with `label`, `files`, `outcome`, `type_id` and `reason`.

- [ ] **Step 1: Write the failing tests.** The fixtures are FASTQ heads, as the existing upload tests write them (`grep -rn "def _fastq" packages/mendel-api/tests`).
  - `test_two_samples_are_each_measured`: two pairs, read lengths 150 and 150, give two `measured` outcomes, each with its own facts.
  - `test_a_sample_nothing_reads_is_named_and_the_others_kept`: a FASTQ pair plus a `.bam` give one `measured` and one `no_inspector`, labelled.
- [ ] **Step 2: Run them.** Expected: FAIL.
- [ ] **Step 3: Implement.** One sample keeps today's path exactly.
- [ ] **Step 4: Run** `packages/mendel-api/tests/authoring/samples`. Expected: pass.
- [ ] **Step 5: Commit** `feat: each uploaded sample is measured on its own (#466)`.

### Task 3: Agreeing samples record a fact; disagreeing ones ask

**Files:**
- Modify: `packages/mendel-api/src/mendel_api/stages/samples.py` (`record_inspection` over several inspections; `_record_found`)
- Modify: `packages/mendel-api/src/mendel_api/stages/gathering.py` (`_gap_options` and the question: the split, and the proposal)
- Modify: `packages/mendel-api/src/mendel_api/services/suggestions.py` (a suggestion the engine makes from measured samples, `by: measured`)
- Modify: `diagnostics.yml` if a refusal is new
- Test: `packages/mendel-api/tests/authoring/samples/test_several_samples.py` (extend)

**Interfaces:**
- Consumes: Task 2's inspections; `gaps.can_vary` (stage 1).
- Produces:
  - **Agreement:** every sample that decided the fact gives the same value. It is recorded as today (`MEASURED`). Its evidence says how many samples it was read on (`Evidence.samples: int`, a new field, excluded when absent).
  - **Disagreement:** no value is recorded. The fact's gap stays, or opens, with `split: list[{value, samples}]`, and a proposed answer:
    - `varies` where `can_vary`, said as *"Your uploads differ: 150 bp in 3, 75 bp in 1. It differs between samples?"*;
    - otherwise the question becomes *which should the pipeline be built for?*, with options the observed values and the proposal the majority's (the first in the upload's order on a tie). It is said as *"Your uploads differ: … The aligner is chosen once for the whole pipeline. Build for 150 bp?"*.
  - The proposal is a suggestion (`suggestions`), made by the engine from measurements, never by a model. It pre-fills the gap and waits for the person's click, as a model's suggestion does today (operator, 11-11).
  - A fact the person already stated is never asked again. The split is reported in `disagreed` as today.

- [ ] **Step 1: Write the failing tests:**
  - `test_samples_that_agree_record_the_fact`: two samples at 150 give `read_length = 150`, with `samples: 2` in its evidence.
  - `test_samples_that_differ_on_a_fact_that_can_vary_propose_varies`: paired and single-end uploads give no recorded value. The `paired` gap pending carries a split of `true: 1, false: 1` and a suggested option `varies`, and nothing changes until the person answers.
  - `test_samples_that_differ_on_the_aligners_fact_ask_which_to_build_for`: 150 and 75, `read_length` asked with options `150` and `75`, and `150` proposed (majority, or the first on a tie).
  - `test_agreeing_and_disagreeing_facts_do_not_wait_for_each_other` (Review Focus 2).
  - `test_a_stated_fact_is_not_asked_again` (Review Focus 3).
- [ ] **Step 2: Run them.** Expected: FAIL.
- [ ] **Step 3: Implement.** Order: record agreements; then, for each disagreement, open or update its gap, in the measurement id order.
- [ ] **Step 4: Run** `packages/mendel-api/tests/authoring`. Expected: pass.
- [ ] **Step 5: Commit** `feat: samples that disagree are asked, with the split and a proposal (#466, #218)`.

### Task 4: The model reads every file

**Files:**
- Modify: `packages/mendel-api/src/mendel_api/services/characterise.py` (`excerpts`: one per file not read by an inspector, up to the upload's limit)
- Modify: the characterisation egress payload in `packages/comeni-core/src/comeni_core/egress/` (`grep -rn "class .*Excerpt\|excerpt" packages/comeni-core/src/comeni_core/egress`): `excerpts: list[...]`, each with its file's label
- Modify: `packages/mendel-api/src/mendel_api/stages/samples.py` (queue one job with every unread file's excerpt), the prompt part that reads excerpts (new version)
- Test: the characterisation tests (`grep -rln "characterise" packages/mendel-api/tests`), with recorded replies

**Interfaces:**
- Produces: the job's payload holds one excerpt per unread file, labelled with its sample. The reply names one type per sample, and each is validated against the registry's types where it is received. Two samples the model reads as different types are reported, not merged.

- [ ] **Step 1: Write the failing tests:**
  - `test_every_unread_file_reaches_the_reading`: two `.bam` heads give two labelled excerpts in one payload.
  - `test_a_read_file_is_not_sent` (Review Focus 5): only the unread sample's excerpt is sent.
  - `test_a_reply_naming_two_types_is_reported_per_sample`, from a recorded reply.
- [ ] **Step 2: Run them.** Expected: FAIL.
- [ ] **Step 3: Implement**, with the protection level asked as today, once per upload.
- [ ] **Step 4: Run** the characterisation tests and `make guards`. Expected: pass. The egress guards hold.
- [ ] **Step 5: Commit** `feat: the model reads every uploaded file nothing measures (#466)`.

### Task 5: The upload and the question show the samples

**Files:**
- Modify: the upload control in `frontend/src/build/living/` (`grep -rn "uploadAuthoringSample" frontend/src`): `multiple`, and the files sent in one request
- Modify: the gap question card (`grep -rln "question-card\|QuestionCard" frontend/src/build/living`): the split line, and the proposed answer pre-selected
- Modify: the upload result: each sample's label, its files, and what was found or why not
- `make client`
- Test: the matching `*.test.tsx`

- [ ] **Step 1: Write the failing tests:**
  - "several files go in one upload";
  - "the split is said in words: 150 bp in 3 of 4 uploads, 75 bp in 1";
  - "a proposed answer is selected and waits for the click";
  - "each sample says which files made it".
- [ ] **Step 2: Run** `cd frontend && npx vitest run`. Expected: FAIL.
- [ ] **Step 3: Implement** with the design tokens, following the documentation style guide for the words.
- [ ] **Step 4: Run** `npx vitest run` and `npx tsc -b`. Expected: pass.
- [ ] **Step 5: Commit** `feat: the conversation shows each uploaded sample and how they differ (#466)`.

### Task 6: Docs and the end of the part

**Files:** the samples how-to and explanation pages (`grep -rln "upload a sample" docs`), `CHANGELOG.md`, the journal, `docs/notes/now.md`.

- [ ] **Step 1:** Write the docs. Tick this plan and record its deviations.
- [ ] **Step 2:** Run `make check`, `make guards`, `make slow`, `npx vitest run` and `npx tsc -b`, separately. Expected: pass.
- [ ] **Step 3: Commit** `docs: several uploads (#466)`.

## Deviations

(Recorded during execution.)

# Per-sample stage 2: several uploads and the conversation — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A person uploads any number of samples at once, hundreds included. Each is measured,
and kept with the session under its name and with its measurements. Where the samples agree,
the value is recorded. Where they disagree, the conversation shows the split, and proposes using
one value or splitting by the fact. The person confirms. The builder shows every sample with its
measurements, and lets the person choose one value or a split for each fact.

**Architecture:** The upload route keeps every file's head (no cap), pairs mates by name, and
measures each sample with the existing runner. A new JSON column on the authoring session holds
the samples: name, files and facts. `samples.record_inspection` records what every sample
agrees on. For a disagreement it opens the fact's gap with the split and a proposed answer: the
existing suggestion that pre-fills a gap and waits for a click. The model sees a summary of each
fact's spread in its memory of the session, and a few excerpts for files nothing measures.

**Tech Stack:** Python 3.12 (FastAPI, pydantic, SQLAlchemy/alembic), React + TypeScript.

**Spec:** `docs/superpowers/specs/2026-11-11-per-sample-design.md`: stage 2; Goals B ("Asking, in
the conversation") and H.

## Global Constraints

- No cap on the number of files or samples (operator, 11-12). Each file's first 4 MB is kept in memory for the request; nothing is written to disk but the facts.
- An upload never prunes on its own: a proposal does nothing until a person accepts it (operator, 11-11).
- Sample names live in the session's sample column only: never in a goal's profile, `pipeline.yml`, a model payload, or a log line. They are deleted with the session (operator, 11-12).
- The model sees summaries: values with counts, and a number's range and its groups. Never a list of every sample.
- Model calls use declared AI points and typed egress payloads.
- Per task: targeted tests only; the full checks and slow runs at the end of the part. A fresh reviewer (opus) after each task.
- Commit trailer: `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Review Focus

1. **Files that do not pair** (an `_R1` without its `_R2`). Each is a sample of its own, said so on the card. Pinned in Task 1.
2. **500 samples.** Measured in one request, recorded, and summarised in a few lines for the model and the card. Pinned in Tasks 2 and 3 (a 500-sample fixture of tiny heads).
3. **Agreeing on one fact, disagreeing on another.** The first is recorded and the second asked. Neither waits. Pinned in Task 2.
4. **A fact the person already stated.** Never asked again; the split is reported as today's disagreement. Pinned in Task 2.
5. **Deleting the session deletes the sample names.** Pinned in Task 1.

---

### Task 1: Every sample in one upload, kept with the session

**Files:**
- Modify: `packages/mendel-api/src/mendel_api/services/sample_upload.py` (no cap; `samples_of`)
- Modify: `packages/mendel-api/src/mendel_api/routes/authoring.py` (`upload_sample`)
- Modify: `packages/mendel-api/src/mendel_api/models.py` (`PipelineAuthoringSession.samples`, JSON), its shape version and golden, and a migration
- Modify: `packages/mendel-api/src/mendel_api/services/inspect.py` (`inspect_samples`)
- Modify: `packages/mendel-api/src/mendel_api/stages/samples.py` (`_upload` measures each sample and stores it)
- Modify: `packages/mendel-api/src/mendel_api/services/deletion.py`, if the session's row is not already deleted whole
- Test: `packages/mendel-api/tests/authoring/samples/test_many_samples.py` (new)

**Interfaces:**
- Produces:
  - `samples_of(files, sizes) -> list[Sample]` (`Sample`: `name`, `files`, `sizes`). Two files are mates when their names differ only in `_R1`/`_R2`, `_1`/`_2` or `.1`/`.2` before the extension; the sample's name is the shared stem. Any other file is a sample of its own. Duplicate names get `#2`, `#3`.
  - `inspect_samples(samples, stack, claimed) -> list[tuple[Sample, Inspection]]`.
  - The session's `samples`: a list of `{name, files, outcome, facts: [{measurement, value, coverage}]}`, in upload order. A new upload replaces it.

- [x] **Step 1: Write the failing tests:**
  - mates pair (`a_R1`, `a_R2`), and unpaired files stand alone;
  - 500 pairs of tiny FASTQ heads in one upload give 500 stored samples, each with its facts;
  - deleting the session leaves no sample name behind (`grep -rn "def delete" packages/mendel-api/src/mendel_api/services/deletion.py`).
- [x] **Step 2: Run them.** Expected: FAIL.
- [x] **Step 3: Implement.** One upload of one sample keeps today's behaviour.
- [x] **Step 4: Run** `packages/mendel-api/tests/authoring/samples` and the shape tests. Expected: pass.
- [x] **Step 5: Commit** `feat: an upload holds every sample, each kept with its measurements (#466, #218)`.

### Task 2: Agreement is recorded; a split is asked, with a proposal

**Files:**
- Modify: `packages/mendel-api/src/mendel_api/stages/samples.py` (`record_inspection` over the samples)
- Modify: `packages/mendel-api/src/mendel_api/stages/gathering.py` (the gap's split and options), `services/suggestions.py` (a proposal the engine makes from measured samples)
- Test: `packages/mendel-api/tests/authoring/samples/test_many_samples.py` (extend)

**Interfaces:**
- Produces:
  - `spread(samples, measurement) -> list[{value, count}]` for an enum or boolean, sorted by count, and a number's values grouped where equal.
  - **Every sample agrees:** the value is recorded (`MEASURED`), with `Evidence.samples = n`, a new field excluded when absent.
  - **They disagree:** no value is recorded. The fact's gap opens or stays with the spread, and a proposal:
    - where `gaps.can_vary`, *it differs between samples*;
    - otherwise the question is *which should the pipeline be built for?*, with the observed values as options, proposing the most common.

    The proposal waits for the person's click.
  - A fact the person stated is not asked again; the spread goes to `disagreed`, as today.

- [x] **Step 1: Write the failing tests:**
  - agreement records the value with `samples: 500`;
  - paired and single-end samples propose *varies* and record nothing until the click;
  - 480 at 150 bp and 20 at 75 bp make `read_length` ask which to build for, proposing 150;
  - agreeing and disagreeing facts in one upload (Review Focus 3);
  - a stated fact is not asked again (Review Focus 4).
- [x] **Step 2: Run them.** Expected: FAIL.
- [x] **Step 3: Implement.**
- [x] **Step 4: Run** `packages/mendel-api/tests/authoring`. Expected: pass.
- [x] **Step 5: Commit** `feat: samples that disagree are asked, with the spread and a proposal (#466, #218)`.

### Task 3: The model sees the spread, and reads a few files nothing measures

**Files:**
- Modify: `packages/mendel-api/src/mendel_api/services/known.py` and `mendel_authoring/memory.py` (each fact's spread, in a line)
- Modify: `packages/mendel-api/src/mendel_api/services/characterise.py` and its egress payload (up to three labelled excerpts, by sample position, never by name), with a new prompt version
- Test: the memory and characterisation tests, with recorded replies

- [x] **Step 1: Write the failing tests:**
  - the memory says *read length: 150 in 480 samples, 75 in 20* and holds no sample name;
  - three unread files give three excerpts, never more, and no names.
- [x] **Step 2: Run them.** Expected: FAIL.
- [x] **Step 3: Implement.**
- [x] **Step 4: Run** the tests and `make guards`. Expected: pass.
- [x] **Step 5: Commit** `feat: the model sees how the samples spread, never their names (#466)`.

### Task 4: The builder shows the samples, and each fact's choice

**Files:**
- Modify: the session view in `mendel-api` (the samples, from the session) and `make client`
- Modify: the upload control in `frontend/src/build/living/` (`multiple`, every file in one request) and the gap card (the spread, with the proposed answer selected)
- Create: `frontend/src/build/living/Samples.tsx`: a table of every sample with its measurements, sortable, filtered by text, and grouped by a fact. Each fact that differs offers *use one value* or *split by it*, which answer its gap.
- Test: `Samples.test.tsx`, the gap card's test

- [x] **Step 1: Write the failing tests:**
  - the table lists every sample with each measurement;
  - grouping by `paired` shows two groups with their counts;
  - *split by it* answers the gap with *varies*, and *use one value* with the chosen value;
  - 500 rows render (paged, or virtualised).
- [x] **Step 2: Run** `npx vitest run`. Expected: FAIL.
- [x] **Step 3: Implement** with the design tokens.
- [x] **Step 4: Run** `npx vitest run` and `npx tsc -b`. Expected: pass.
- [x] **Step 5: Commit** `feat: the builder shows every sample and lets a fact be one value or split (#466)`.

### Task 5: Docs and the end of the part

- [x] **Step 1:** Docs: the samples how-to and explanation, `CHANGELOG.md`, the journal, `now.md`, the privacy note on sample names. Tick this plan and record its deviations.
- [x] **Step 2:** Run `make check`, `make guards`, `make slow`, `npx vitest run` and `npx tsc -b`, separately. Expected: pass.
- [x] **Step 3: Commit** `docs: several uploads (#466)`.

## Deviations

- Grouping happens in the upload stage; the command still carries the flat file list.
- The spread and the proposal ride on the gap question (its `why_open`, and a pre-filled option
  noted "proposed from your uploads"), not on a new suggestion record.
- `Evidence.samples` was not added; a stated fact the samples disagree with is not reported as
  a disagreement (deferred).
- A file nothing measures still reaches the model as one excerpt for the upload.
- Choosing one value or a split happens on the gap card; the samples table only shows.
- Per-task reviews were not run (the reviewer hit a usage limit); one whole-stage review instead.

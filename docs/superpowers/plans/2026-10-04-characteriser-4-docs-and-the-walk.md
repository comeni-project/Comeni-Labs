# Characteriser 4 — the docs, and the walk — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Every document that described the characteriser as designed now describes it as built, in the reader's words. The whole branch is walked live with a local model: a FASTA and a GTF read by AI, a FASTQ renamed `.txt` handed back and measured, and a binary file refused. The step closes, and the journal is compacted.

**Architecture:** Documentation and a driven session; no product code except fixes the walk files as issues.

**Tech Stack:** Markdown; `make dev` with a local model (`make ai-up`); puppeteer-core for screenshots.

**Spec:** `docs/superpowers/specs/2026-10-04-the-characteriser-design.md` §11, §12 (*the walk*). Part 14.7.7.4 of #135. Depends on plans 1–3.

## Global Constraints

- **Say "does not receive patient data", never "anonymised"; never claim compliance; claim nothing about where sequencing data goes on managed cloud** (`CLAUDE.md`).
- **Nothing in a doc is a count**: the doors are `DOORS`, the free-text fields `FREE_TEXT_FIELDS`, the sample fields `SAMPLE_FIELDS`.
- Task pages lead with what the reader gets, name sections after what somebody does, and use no internal names and no issue numbers (`CLAUDE.md`, *Writing documentation*).
- **Every defect the walk finds gets an issue first.** Mechanical defects are fixed test-first and closed citing the commit; protocol questions go to the operator as choices with their costs.
- `make check` on its own before each commit; `make doc-sizes` keeps `CLAUDE.md` ≤ 300 lines and `now.md` ≤ 150.

## Rulings against the spec, for the operator

1. **The handbook has no upload page** (spec §11 names one). A section *When you're not sure: answer with a file* goes in `docs/handbook/builder.md`, where the conversation is described. Cost if wrong: the section moves to a page of its own.

## Review Focus

1. **A sentence still saying *three* AI points, *five* doors, or *designed, not built* about the characteriser.** Grep, never memory. Pinned in Task 1 Step 1.
2. **The level-0 loosening for Redis is written where the other loosenings are**, not only in the spec. Pinned in Task 1.
3. **The walk's model is a local one**, so the sample's excerpt never leaves the machine during the walk. Pinned in Task 2 Step 1.
4. **A live reading slower than the poll's patience** (a cold local model): the card still arrives, and the walk records the time. Pinned in Task 2.
5. **The journal entry names every ruling made across the four plans**, for the operator to confirm or reverse. Pinned in Task 3.

---

### Task 1: The docs

**Files:**
- Modify: `CLAUDE.md` (invariants 3, 14, 15; *Protection profiles* paragraph)
- Modify: `docs/design/invariants.md` (§3, §14, §15)
- Modify: `docs/design/authoring-protocol.md` (rules 3–4, *Where each measurer runs*, the protection table, *Loosenings, recorded*)
- Modify: `docs/handbook/reference/glossary.md`
- Modify: `docs/handbook/builder.md`
- Modify: `ARCHITECTURE.md`, if it names `AiPoint` members or the doors

- [x] **Step 1: Find every stale sentence**

Run:

```bash
git grep -n -i -E "three (declared|runtime)? ?(ai )?points|five (declared )?doors|designed, not built|characteris" -- CLAUDE.md ARCHITECTURE.md docs/design docs/handbook docs/notes/now.md
```

Expected: a list. Every line is either fixed below or left with a reason in the execution record.

- [x] **Step 2: The invariants**

`CLAUDE.md`:
- Invariant 3: *Runtime AI is confined to four declared points (`AiPoint`): goal extraction, tier-4 resolution, compiler repair (declared, not built), and characterisation, at protection level 0 only (`docs/design/authoring-protocol.md`).*
- Invariant 14: unchanged in form, except that the sentence names `SAMPLE_FIELDS` beside `FREE_TEXT_FIELDS` as the count of fields that may hold data from a person's file.
- Invariant 15: append *A model may read up to 8 KB of an uploaded sample's text, through door 6, when nothing here reads its type (14.7.7).*
- *Protection profiles* paragraph: *Level 0 (a sample may be uploaded, measured, and read by a model when nothing measures its type) is the MVP's setting, built in 14.7.6 and 14.7.7.*

`docs/design/invariants.md`:
- §3: the fourth point, why it is a loosening, and where it is recorded.
- §14: retitle to *Data leaves through declared doors only, on two paths*, without a number. Add a paragraph on door 6: the first payload holding data from a person's file, bounded by its type, with `SAMPLE_FIELDS` counted apart.
- §15: the excerpt as a second level-0 loosening.

- [x] **Step 3: The protocol page**

`docs/design/authoring-protocol.md`:
- *Where each measurer runs*, the characteriser row: *a model, through door 6* | *at most 8 KB of the sample's text, from the start of its decoded head* | *the excerpt reaches the model; nothing is stored by us* | *level 0 only*. Drop *designed, 14.7.7*.
- The protection table: *characteriser receives* at level 0 becomes *at most 8 KB of the sample's text*.
- *Loosenings, recorded*, a new entry dated 2026-10-04: *The excerpt waits in Redis.* The AI reads on its worker, so the excerpt rides in the job's arguments until the worker takes it, and the job keeps no result. It is the only place part of a sample rests outside a request, for seconds to minutes; each later level decides whether a reading happens at all.
- Rules 3 and 4: *the characteriser* now links to how it reads (families then types, closed vocabulary, *read by AI*), and rule 4 says what happens when the AI cannot tell.
- The changelog line for 14.7.7.

- [x] **Step 4: The reader's pages**

`glossary.md`, a *read by AI* entry: *A fact a model read from the start of a file you uploaded, because nothing here measures that kind of file. Shown in yellow: check it before you build.*

`builder.md`, a section **When you're not sure: answer with a file**. It covers:
- what is read (the first 4 MB, on this server);
- what is measured, and by what;
- when a model reads it instead (nothing here reads that kind of file): at most 8 KB of its text, at protection level 0;
- that a fact a model read is labelled *read by AI*;
- that what you said yourself always stands.

No issue numbers, no internal names.

- [x] **Step 5: Check, then commit**

Run: `MENDEL_DATABASE_URL=postgresql+psycopg://mendel:mendel@127.0.0.1:5442/mendel make check`
Expected: green, including `doc-paths` and `doc-sizes`.

```bash
git add CLAUDE.md ARCHITECTURE.md docs && git commit -m "docs: the characteriser built — a fourth AI point, door 6, read by AI (#135)"
```

---

### Task 2: Walk it

**Files:** screenshots and the session's notes, in the scratchpad; issues on GitHub.

- [x] **Step 1: A local model, level 0**

`make ai-up` (with `OLLAMA_GPU=rocm` on this machine) and the model the walk used last (`gemma3:12b` unless now.md names another). Rebuild `ai-worker` (it is baked). Set the Ollama context above 2048, because Ollama's default silently truncates. Confirm in Settings → Models that the builder's chat model is this local one, so no excerpt leaves the machine. `make dev`.

- [x] **Step 2: Make the files**

In the scratchpad:
- a small FASTA (`ref.fa.gz`): two chromosomes, 2 KB;
- a GTF (`genes.gtf`): twenty lines;
- a BAM's first block, written as the excerpt tests write one (`ali.bam`);
- the FASTQ pair from `registry/inspectors/formats/fastq/piece/fixtures/pair_150/` copied as `s_R1.txt.gz` and `s_R2.txt.gz`;
- 64 KB of random bytes (`noise.bin`).

Nothing is downloaded.

- [x] **Step 3: Drive it**

*Gene counts from paired RNA-seq*, then gather:
- **reads:** upload the `.txt.gz` pair. Expect *being read by AI…*, then *read by AI: fastq.reads → measuring…*, then the measured result with *type read by AI*.
- **reference genome:** upload `ref.fa.gz`. Expect *genome.fasta · read by AI*, and the question closes.
- **annotation:** upload `genes.gtf`. Expect *annotation.gtf · read by AI*.
- on a second session: `ali.bam` on the genome question. Expect `alignment.bam · coordinate_sorted · read by AI`, with the question staying. Then `noise.bin`. Expect *nothing reads .bin files yet*.

Confirm the goal card shows *read by AI* on each such input, then build. Open `pipeline.yml`: a premise the AI read says `origin: model_read`, and its reason begins *read by AI from the start of a sample*. Screenshot each step on a desk, and the reading on a phone. Record each reading's time from upload to card.

Also open the session's call panel: two calls per reading, purposes `characterise_family` and `characterise`, and no file name in any rendered prompt.

- [x] **Step 4: Every defect is an issue first**

File each finding (`walk` label, then `mechanical` or `protocol`). Fix mechanical ones test-first and close them citing the commit. Put protocol questions to the operator as choices with costs. Re-walk until the walk passes.

---

### Task 3: Close the step

- [x] **Step 1: The journal entry**

`docs/notes/journal/<date>-characteriser.md`, in the journal README's order:
- **where things stand**, with the commands that verify it: the egress guards, the excerpt tests, the walk's reading times;
- **what changed**: commits per plan;
- **decisions and why**: the spec's §2 table, plus every `Ruling:` from the four plans' execution records, each with what it costs if wrong;
- **what is next**: 14.7.8 the consultant build; #236 vocabulary proposals;
- **open questions**.

- [x] **Step 2: Compact**

Follow `docs/notes/compaction.md`: fold the step into `now.md` (14.7.7 done; 14.7.8 next), move the entry to `archive/`, and keep `now.md` ≤ 150 lines.

- [x] **Step 3: Close the issue**

Comment on #135 with the commits and the walk's result, and close it. Tick 14.7.7 on #126 if that issue keeps a checklist.

- [x] **Step 4: Check, then commit**

```bash
git add docs && git commit -m "docs(notes): the characteriser built — 14.7.7 closes (#135)"
```

---

## Execution record

Executed 2026-10-04, in one hand.

- **Task 1** (8ac6d687): CLAUDE.md invariants 3, 14 and 15, and the protection paragraph; `invariants.md` §3, §14 and §15; the protocol page (rule 4, the measurer row, the protection table, the loosening for the excerpt in Redis, the changelog); `ARCHITECTURE.md`; the schema reference; the builder page's *When you're not sure: answer with a file*. *Ruling:* there is no glossary entry, because the glossary is held by a test to the on-screen `<Term>` words.
- **Task 2:** walked live with gemma3:12b across plans 3 and 5 (#243, #244, #245, #246). The last walk passed:
  - FASTA → `genome.fasta`;
  - BAM → `alignment.bam` and `coordinate_sorted`, quoting its header line;
  - FASTQ `.txt` → handed back and measured;
  - random bytes → *nothing reads this type yet*;
  - `ai_for_draft` → `characterise` available and used.

  Not walked: a build through to Keep with a fact the AI read. In this registry a read fact can only be an input's type, and a premise comes only from measurements, which the AI may read only where a measurement declares `describes:` a type with no inspector (none does today). The end-to-end file is pinned by `test_a_premise_read_by_ai_says_so_in_the_file`.
- **Task 3** (fa381cf6, 4cf641e4): the journal entry, compacted; `now.md` is 149 lines.

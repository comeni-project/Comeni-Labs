# Now: what is true, and what is next

The consolidated state of the project. **Read this first**; then any entry still in
[the journal](journal/), since those are not compacted yet. How this page is kept:
[the compaction rules](compaction.md). Each line cites the entry it came from; the long form of any
line is in [the archive](journal/archive/).

**Compacted through: 2026-10-18.** `CLAUDE.md` as it stood before 2026-09-28, with its
plan-by-plan history (Plans 1–6, 3A–3E, Wiener W1/W2, the audit rounds), is kept verbatim in
`tests/fixtures/claude-md-2026-09-28.md`.

## Where the work is

- **Task 14 of the living pipeline, step 14.7: walking it with a real model.** The tree is GitHub
  issue #119 (Task 14 → steps → substeps → tasks, each a sub-issue). (2026-09-28)
- **14.7.8.3d Parts A–H are implemented** (#285–#292). Part I (#293): I.1 explain the inputs is
  done; **Part I.0** (#307) Plan A is done, and four walks (#321, #348, #354) now meet #338's bar.
  Plan B (the save file) is built (`plan-b-save-file`). **Next: I.2 (what was narrowed) and
  I.3 (a conversation); opening a saved file is #357.** Undo: #302. (2026-10-18)

## How work is done now

- **Every defect gets a GitHub issue first.** Mechanical ones are fixed test-first and closed citing
  the commit; a rule or protocol question is brainstormed, the operator chooses, the choice is
  commented on the issue, then implemented. (2026-09-28)
- **The simplest change that obeys the existing rules**: derive rather than declare, and say why
  any new concept is needed. (2026-10-16)

## The living pipeline (describe → build)

- A researcher types a sentence (an empty home, or the describe bar above the work) and builds
  beside a conversation at `/build?session=<id>`; `/build?draft=<id>` is the manual builder.
  (2026-09-13, 2026-10-03)
- **The authoring protocol** is `docs/design/authoring-protocol.md`: the engine decides what is
  missing, a model only phrases and reads answers, nothing is guessed, an open measurement falls
  to tier 4, and stage ④ (the consultant build) is knowingly optimistic. (2026-09-28)
- **The diagram runs the engine:** protocol, interpreter and commands are the pure
  `mendel-authoring`; a session moves only by a drawn arrow, one command in one transaction through
  `mendel_api/services/session.py`, one module per stage. One build; tier 4 always stops. (2026-10-05, 10-06)
- **Protection level 0** (everything open) is the MVP; invariant 15 does not hold at level 0 and
  characterisation is a fourth AI point, both recorded loosenings. (2026-09-28, 2026-10-04)
- **The want is two calls:** `builder.family.v4` answers `fits`, then `builder.goal.v9` reads the
  chosen families (also the one-step path); a want nothing makes asks the person. (2026-09-30)
- **The model phrases and returns grounded changes:** `ask.v3` words each gap, `readback.v2` reads
  the goal back, `chat.v7` reads typed words. A change quoting the turn being answered is *heard*:
  recorded before the goal is confirmed, offered after; others are offered. (2026-10-13, 10-18)
- **One writer for every change** (`mendel_api/services/changes.py`); the decision rows are the only home of
  the want, confirmation is recorded, and every prompt is shown *what is known*. (2026-10-13)
- **Whatever a chosen tool reads comes from somewhere, or is tier 4** (#338): derived from the
  module's code (`conformance.facts_read`); strandedness stops once, on the step card. (2026-10-16)
- **A value against a measured one is asked about, then followed** (#345); a not-offered request is
  a note that changes nothing (#347, #355); `measurement.*` types reach no builder door (#346). (10-18)
- **Every data question explains itself:** *What is this?* (the registry's curated `name` and
  `explain`) and why it is asked (the engine's). The voice is `docs/design/voice.md`. (2026-10-13)
- **Replies are enforced formats** (`comeni_ai/formats.py`, one per provider), so a shape is never
  refused; a raw JSON Schema in the prompt made models echo it. (2026-09-29)
- **Current decisions are retained rows**, one pointer per subject; corrections cascade reviews,
  truthful unbuildable answers stay, manual work forks to a linked draft. (2026-10-11)
- **The canvas is the session's frame**, read from recorded rows and never re-resolved; progress
  counts the plan (*Step 4 of 5*); an alternative previews as the whole saved pipeline. (2026-10-12)
- **Legacy conversion is frozen**; old snapshots are historical only. (2026-10-11)
- **Open:** `MD0225` does not cover step selections; the `comeni-core` version bump for goal pins,
  missing-premise records and provenance. (2026-09-13, 2026-10-06, 2026-10-07)

## Samples (protection level 0)

- **A gap can be answered with a sample**, one file or a pair: each file's first 4 MB, measured in
  memory by a child process with no secrets and hard limits; facts are kept, never bytes. A
  disagreement asks keep, use, correct or unknown. (2026-10-03, 2026-10-04)
- **A sample nothing reads is read by the AI** (door 6): up to 8 KB; a family, then a type; each
  property **quotes its line**, checked, then *read by AI*. Open: #238, #239. (2026-10-04)
- **Inspectors are composed pieces** in `registry/inspectors/` (codecs, formats, measures), run
  only from trusted layers, one pass over the head; FASTQ measures read length, pairing and quality
  encoding (0.21 s for 4 MB). Below a threshold a measure says *undetermined*. (2026-10-03)
- **A measured fact is `MEASURED`**, naming its pieces and evidence (*measured · fastq 1.1.0 ·
  from 1 sample*). Adding a piece: `registry/inspectors/README.md`. (2026-10-03)
- **The registry is one folder per tool**; the path is the id. (2026-10-03)

## Settings (Settings → behind the gear)

- **Per installation; `.env` is a lock, not a seed.** Each value says where it came from; one
  declaration per setting in `comeni_core/settings/`; the API and menu are generic. (2026-10-01)
- **A model per purpose** (`model_access(agent, purpose)`); `.env`'s `COMENI_AI_*` still work; keys
  typed in the menu are sealed with `COMENI_SETTINGS_KEY`. (2026-10-01)
- **On the RX 7600 (8 GiB):** gemma3:4b and qwen2.5:7b fit (0.5–3 s a call); gemma3:12b spills
  36% to the CPU (3–7 s, about 20 s a chat reply) and is what the walks run. (2026-09-29, 10-18)
- Pacing is live; tier 4 by a model, protection levels and k8s/awsbatch remain designed. (10-01)

## The look (designed, not built)

- **Labs takes the hybrid identity it shares with Comeni Code** (Lexend and Geist Mono,
  light-first, one meaning per colour, metro lines): 13 artboards in `.design/hybrid/`, unbuilt.
  Order: tokens → shell → Home/Describe → Build → files → runs → registry. (2026-09-17)
- **Labs stays on FastAPI**; accounts would come as one OIDC sign-in shared with Code, provider
  undecided. (2026-09-17)

## The forge (where declared data comes from)

- **The old forge is gone** (#361, forge MVP part 0, on `forge-0-remove-old`): package, API,
  worker jobs, tables, `/forge` screens and its `MF`/`MI01xx` codes. The new forge is designed
  from scratch in `docs/superpowers/specs/2026-10-19-forge-mvp-design.md`; part 0 merges to
  `main` only together with part 1 (#362), so `main` never lacks a Registry. (2026-10-19)
- **Until then registry data is written by hand.** `ai_invocation` keeps its `forge` rows, and
  the vocabulary lives in `mendel_api/invocations.py`. (2026-10-19)

## Wiener (run → watch)

- `/runs` is a board and `/runs/{id}` a page of bands; **cancel** is the only verb. No
  memory-over-time curve; the failure panel shows the record and explains nothing. (2026-09-01)
- **The AI monitor is deferred:** not a Mendel door, automatic briefs redacted, the console tail
  never crosses. (2026-08-29)
- **Open:** `ABORTED` counts as failed in `wiener_core/graph.py`; `submitted_by` is hardcoded
  `"operator"`, so *who* filters nothing. (2026-08-25, 2026-08-29)

## The emitted pipeline

- **The v1 criterion:** from a prompt and a test dataset, Nextflow that runs green on the nf-core
  test profile and produces a counts matrix (`tests/emit/test_counts.py`). The spine has 10
  processes, not the criterion's 15–20; whether that clause survives is #11. (2026-09-28)
- **`pipeline.yml` v7**: `intent`, `facts`, `source: said`, layer `source`/`commit`; a starter is
  its top half (`mendel build`). Only v7 is read: no compatibility before v0.1.0. (2026-10-18)
- A `RUN`-scoped channel emits as a value channel; an aggregator gets `.collect()`. A samplesheet
  pipeline runs under `--gate test`, but `DraftChannel.scope` has no canvas control. (2026-09-01)

## Decided, and not to reopen

- The canvas flows **left to right** (`dag-core` serves both); **absence is absence**: a region
  with nothing to say is not drawn. (2026-08-29, 2026-08-30)
- Motion: five movements, one curve; numbers never tween. (2026-08-29)
- A model server's keep-alive and slots are the deployment's business. (2026-09-29)

## Known traps

- **The stack:** `api` and `worker` mount `./packages` (`api` reloads); `ai-worker`, `wiener-api`
  and `web` run **baked**: rebuild after a change. The stack reads a registry clone `make dev`
  makes, not `registry/`. (2026-09-01, 2026-09-29, 2026-10-01)
- **Ports here:** other projects hold 5432 and 8000: `API_HOST_PORT=8020 DB_HOST_PORT=5433 make
  dev`, then `make ai-up OLLAMA_GPU=rocm`. `.env` points host tools at 5432; name the test
  database for them. (2026-10-18)
- **Measure a model fix before and after, as rates** (`tools/measure_prompts.py`): one walk reply
  is a sample; a fix that passed `make check` once took refusals from 4/18 to 12/12. (2026-10-18)
- **On Ollama `cached` reads 0**; the first call after a rebuild is a ~70 s cold load; a hidden
  Chrome tab does not poll. (2026-09-29, 2026-09-30)
- **Python 3.14 loses truncated-gzip evidence** (#303); CI's 3.12 and 3.13 pass. (2026-10-11)
- **Headless Chrome** freezes `settle` at its first frame; it stands in when the extension is not
  connected (throwaway `--user-data-dir`). (2026-09-13, 2026-10-01)
- `pkill -f <pattern>` kills its own shell (exit 144); `#307` in a frontend test name fails
  `tokens.test.ts`: write *issue 307*. (2026-10-13)

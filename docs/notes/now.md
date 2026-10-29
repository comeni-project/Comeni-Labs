# Now: what is true, and what is next

The consolidated state of the project. **Read this first**, then any entry still in
[the journal](journal/). How this page is kept: [the compaction rules](compaction.md). Each line
cites its entry; the long form is in [the archive](journal/archive/).

**Compacted through: 2026-10-26.** The pre-2026-09-28 `CLAUDE.md`, with its plan-by-plan
history, is kept verbatim in `tests/fixtures/claude-md-2026-09-28.md`.

## Where the work is

- **Task 14, step 14.7: walking the living pipeline with a real model.** The tree is #119.
- **Part I (#293) of 14.7.8.3d** (Parts A–H done): I.0 (#307, the walks and the save file) and
  I.1 (explain the inputs) are done; **I.2, say what was narrowed or already known** (#268's DE
  and paired-end items, #306) is open; I.3, a conversation, became one builder plan 3. (10-26)
- **One builder (#395):** plans 1 (structural intent) and 2 (no fork) are done. **Next is plan
  3**, the chat as one stream and Describe: #392's protocol question first (what typed words may
  change while the goal is gathered), then #391 and #399's findings. Plans 4 (the hand-over,
  #393) and 5 (the file, #394) follow; 3 and 5 take mockups first. Also #357, #302. (10-22, 10-26)
- **All of it is on `main`** (PR #402, with a behaviour-preserving refactoring campaign). Left for
  an authorised behaviour pass: `SampleUpload.tsx`'s hook warning, Node under Vite's floor. (10-26)

## How work is done now

- **Every defect gets a GitHub issue first.** Mechanical ones are fixed test-first and closed citing
  the commit; a rule or protocol question is brainstormed, the operator chooses, the choice is
  commented on the issue, then implemented. (2026-09-28)
- **The simplest change that obeys the existing rules**: derive rather than declare, and say why
  any new concept is needed. (2026-10-16)

## The living pipeline (describe → build)

- A researcher types a sentence and builds beside a conversation at `/build?session=<id>`;
  `/build?draft=<id>` and a bare `/build` open one too: every pipeline has one. (09-13, 10-22)
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
  truthful unbuildable answers stay. (2026-10-11)
- **A hand edit is read, not saved** (`read_edit`): readings the engine words, applied on *Yes*,
  kept as structural intent (`absent_roles`, `exclusions`, `sources`; `MD0319`–`MD0321`). No
  fork. A drawn pipeline's first reading gathers its inputs (#399). (2026-10-22)
- **An unanswered tier-4 setting is optional** when its route leaves the tool its own behaviour
  (`OMITTABLE`: `ext`, `directive`): still flagged, it stops nothing; `positional` and `meta`
  still need the person (#384). Tier 3 is never called *measured* (#387, #397). (2026-10-22)
- **The canvas is the session's frame**, read from recorded rows and never re-resolved; progress
  counts the plan (*Step 4 of 5*); an alternative previews as the whole saved pipeline. (2026-10-12)
- **Open:** `MD0225` does not cover step selections; the `comeni-core` version bump for goal pins,
  missing-premise records and provenance. (2026-09-13, 2026-10-06, 2026-10-07)

## Samples (protection level 0)

- **A gap can be answered with a sample**, one file or a pair: each file's first 4 MB, measured in
  memory by a child process with no secrets and hard limits; facts are kept, never bytes. A
  disagreement asks keep, use, correct or unknown. (2026-10-03, 2026-10-04)
- **A sample nothing reads is read by the AI** (door 6): up to 8 KB; a family, then a type; each
  property **quotes its line**, checked, then *read by AI*. Open: #238, #239. (2026-10-04)
- **Inspectors are composed pieces** in `registry/inspectors/` (codecs, formats, measures), run
  only from trusted layers in one pass; below a threshold a measure says *undetermined*. (10-03)
- **A measured fact is `MEASURED`**, naming its pieces and evidence. Adding a piece:
  `registry/inspectors/README.md`. The registry is one folder per tool; the path is the id. (10-03)

## Settings (Settings → behind the gear)

- **Per installation; `.env` is a lock, not a seed.** Each value says where it came from; one
  declaration per setting in `comeni_core/settings/`; the API and menu are generic. (2026-10-01)
- **A model per purpose** (`model_access(agent, purpose)`); `.env`'s `COMENI_AI_*` still work; keys
  typed in the menu are sealed with `COMENI_SETTINGS_KEY`. (2026-10-01)
- **On the RX 7600 (8 GiB):** gemma3:4b and qwen2.5:7b fit (0.5–3 s a call); gemma3:12b spills
  36% to the CPU (3–7 s, about 20 s a chat reply) and is what the walks run. (2026-09-29, 10-18)
- Pacing is live; tier 4 by a model, protection levels and k8s/awsbatch remain designed. (10-01)

## The screens

- **The hybrid identity shared with Comeni Code is built** (#370, `.design/hybrid/`), each screen
  matched to its board at 1400 and 390 px and in dark; what a board shows without data is not
  drawn. A step has no *Skip*; tier words are served (`useTiers`). (2026-10-20, 2026-10-21)
- **Labs stays on FastAPI**; accounts would be one OIDC sign-in shared with Code. (2026-09-17)

## The forge (where declared data comes from)

- **Part 1 (#362, with #363's tool page) is on `forge-1-catalogue`**: `/registry` lists nf-core
  against the loaded registry; `/registry/tools/<id>`. A module needs a contract (`MD0025`,
  #410, comeni-registry#22). Next: forging #364, tests #365, pull requests #366, releases #367
  (+ #381). Design: `docs/superpowers/specs/2026-10-19-forge-mvp-design.md`. (2026-10-29)

## Wiener (run → watch)

- `/runs` is a board by pipeline under outcome tabs; a run opens on its failure; **cancel** is
  the only verb. The failure panel shows the record and explains nothing. (2026-09-01, 10-20)
- **The AI monitor is deferred**: not a Mendel door; the console tail never crosses. (2026-08-29)
- **Open:** `ABORTED` counts as failed in `wiener_core/graph.py`; `submitted_by` is hardcoded
  `"operator"`, so *who* filters nothing. (2026-08-25, 2026-08-29)

## The emitted pipeline

- **The v1 criterion:** from a prompt and a test dataset, Nextflow that runs green on the nf-core
  test profile and produces a counts matrix (`tests/emit/test_counts.py`). (2026-09-28)
- **`pipeline.yml` v8**: `intent` (with structural intent), `facts`, layer `source`/`commit`; a
  starter is its top half. Only v8 is read: no compatibility before v0.1.0. (10-18, 10-22)
- A `RUN`-scoped channel emits as a value channel; an aggregator gets `.collect()`. A samplesheet
  pipeline runs under `--gate test`, but `DraftChannel.scope` has no canvas control. (2026-09-01)

## Decided, and not to reopen

- The canvas flows **left to right** (`dag-core` serves both); **absence is absence**: a region
  with nothing to say is not drawn. (2026-08-29, 2026-08-30)
- Motion: five movements, one curve; numbers never tween. A model server's keep-alive and slots
  are the deployment's business. (2026-08-29, 2026-09-29)

## Known traps

- **The stack:** `api` and `worker` mount `./packages` (`api` reloads); `ai-worker`, `wiener-api`
  and `web` run **baked**: rebuild after a change. The stack reads a registry clone `make dev`
  makes, not `registry/`. After a stored-shape change restart every writer, then migrate; a new
  migration needs `make test-db` again. (2026-09-01, 2026-09-29, 2026-10-01, 2026-10-22)
- **One pytest run at a time:** two share the test database and truncate each other. (10-22)
- **CSS:** `.living`/`.tbl` beat same-specificity Tailwind utilities; `px-4` is the custom
  10 px scale, so a page gutter is `px-[16px]`. (2026-10-20, 2026-10-21)
- **Ports here:** other projects hold 5432 and 8000: `API_HOST_PORT=8020 DB_HOST_PORT=5433 make
  dev`, then `make ai-up OLLAMA_GPU=rocm`. `.env` points host tools at 5432; name the test
  database for them. (2026-10-18)
- **Measure a model fix before and after, as rates** (`tools/measure_prompts.py`): one walk reply
  is a sample; a fix that passed `make check` once took refusals from 4/18 to 12/12. (2026-10-18)
- **On Ollama `cached` reads 0**; the first call after a rebuild is a ~70 s cold load; a hidden
  Chrome tab does not poll. (2026-09-29, 2026-09-30)
- **Python 3.14 loses truncated-gzip evidence** (#303); CI's 3.12 and 3.13 pass. (2026-10-11)
- **Headless Chrome** (a throwaway `--user-data-dir`) freezes `settle` at its first frame. (10-01)
- `pkill -f <pattern>` kills its own shell (exit 144); `#` and hex digits anywhere in frontend
  source fail `tokens.test.ts` as a colour: write *issue 307*. (2026-10-13, 2026-10-22)

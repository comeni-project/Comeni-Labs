# Now: what is true, and what is next

The consolidated state of the project. **Read this first**; then any entry still in
[the journal](journal/), since those are not compacted yet. How this page is kept:
[the compaction rules](compaction.md). Each line cites the entry it came from; the long form of any
line is in [the archive](journal/archive/).

**Compacted through: 2026-10-01.** `CLAUDE.md` as it stood before that day, with its plan-by-plan
history (Plans 1–6, 3A–3E, Wiener W1/W2, the audit rounds), is kept verbatim in
`tests/fixtures/claude-md-2026-09-28.md`.

## Where the work is

- **Task 14 of the living pipeline, step 14.7: walking it with a real model.** The tree is GitHub
  issue #119 (Task 14 → steps → substeps → tasks, each a sub-issue). Round 1 of the walk found
  and fixed #106–#116. (2026-09-28)
- **Order of work, in #119's own order** (renumbered 2026-09-28 so the tree reads as done):
  14.7.3 gathering, 14.7.4 the consultant's words and 14.7.5 settings are **done** →
  **14.7.6** samples (#134, next) → **14.7.7** the characteriser → **14.7.8** the consultant build
  (it also reads pacing, #117) → **14.7.9** tune what the walks found (#210) → **14.7.10** the nine
  scenarios. **MVP first, then tune:** a defect found on the way joins #210 unless it blocks the
  loop. (2026-09-28, 2026-09-30, 2026-10-01)
- **Scenario 1 builds end to end with `gemma3:12b`** after gathering; the aligner is tier 3 with a
  read length, tier 4 without. (2026-09-28)

## How work is done now

- **Every defect gets a GitHub issue first.** Mechanical ones are fixed test-first and closed citing
  the commit; a rule or protocol question is brainstormed, the operator chooses, the choice is
  commented on the issue, then implemented. (2026-09-28)
- **Rules are tuned, never forced.** The thesis under test is the balance between flexibility and
  restraint: loosen what is too strict to function, tighten what is too loose. (2026-09-28)
- **Walk it, and look at it:** every driven session found defects no suite could; compare a
  screen to its artboard (`.design/_compare.html`), never by reading markup. (2026-09-01, 2026-09-28)

## The living pipeline (describe → build)

- A researcher types a sentence, chooses Build or Spawn, and builds beside a conversation at
  `/build?session=<id>`; `/build` and `/build?draft=<id>` are still the manual builder, which also
  offers the conversation from its Assistant tab. (2026-09-13, 2026-09-28)
- **The authoring protocol** is `docs/design/authoring-protocol.md`: the engine decides what is
  missing, a model only phrases and reads answers, nothing is guessed, an open measurement falls
  to tier 4, and stage ④ (the consultant build) is knowingly optimistic. (2026-09-28)
- **Protection level 0** (everything open) is the MVP; invariant 15 does not hold at level 0 and
  characterisation becomes a fourth AI point, both recorded loosenings. (2026-09-28)
- **The want is two calls:** `builder.family.v3` answers `fits` first, then `builder.goal.v7`
  reads the chosen families whole; `goal.v6` is the one-step path (`MENDEL_FAMILY_STEP_FROM`). A
  want nothing can make asks the person instead of failing (`WANT_UNREACHABLE`). (2026-09-29,
  2026-09-30)
- **The model only phrases:** `builder.ask.v1` words each gap (prefetched), `builder.readback.v1`
  reads the goal back; a fact the person stated wins over the model's guess. Prompts are sent as a
  fixed system part and a per-call part. A prompt change is always a new version file. (2026-09-29)
- **Replies are enforced formats** (`comeni_ai/formats.py`, one per provider; Ollama on), so a
  shape is never refused: 0 of 27 calls against 4 of 18 when the schema sat in the prompt. Showing
  a model a raw JSON Schema is what made it echo the schema. (2026-09-29)
- A resolve that fails for a missing input is **MI0207** in the conversation. (2026-09-28)
- **Open:** `MD0225` does not cover step selections (the keep route closes it for the product);
  whether `comeni-core` needs a version bump for `DraftProvenance`, MI0207 and door 1's payload.
  (2026-09-13, 2026-09-28)

## Settings (Settings → behind the gear)

- **Per installation; `.env` is a lock, not a seed.** Each value says where it came from;
  greyed rows say why, from a closed list (pinned, designed, needs, read-only here). One
  declaration per setting in `comeni_core/settings/`; the API and menu are generic. (2026-10-01)
- **A model per purpose over connections:** every builder and forge call names its purpose
  (`model_access(agent, purpose)`); `.env`'s `COMENI_AI_*`, old names included, still work.
  Keys typed in the menu are sealed with `COMENI_SETTINGS_KEY`. (2026-10-01)
- **On the RX 7600 (8 GiB):** gemma3:4b and qwen2.5:7b fit (100% GPU, 0.5–3 s a call);
  gemma3:12b spills 36% to the CPU (3–7 s). Set: talk and read-back on gemma3:4b, the rest on the
  default gemma3:12b until #198 measures accuracy. (2026-09-29, 2026-10-01)
- Pacing, tier 4 by a model, protection levels and k8s/awsbatch are shown greyed as designed.
  Running is reported by Wiener itself. (2026-10-01)

## The forge (where declared data comes from)

- **The Forge MVP is complete** and runs end to end: catalogue sync (2,062 nf-core tools, 2 requests,
  ~10 s), scaffold, AI worker, local model, validation ladder, review. (2026-09-06)
- **The review chat is door 5** (`DoorPath.FORGE`); a model may propose a vocabulary entry,
  never land it. (2026-09-05, 2026-09-06)
- **Never run:** approve → land → `mendel build` on a fully answered candidate; a second revision;
  the review chat; pegi3s (needs a Docker Hub credential). (2026-09-06)
- `make forge-rework` lists every `FORGE-REWORK` marker left where Plan 5A invalidated forge code;
  add a marker rather than repointing a forge fixture. (CLAUDE.md, 2026-09-28)
- **Open:** `forge_revision.registry_digest` is `String(64)`, too short for a `sha256:` digest
  (checked 2026-09-28). (2026-09-13)

## Wiener (run → watch)

- `/runs` is a board and `/runs/{id}` a page of bands; **cancel** is the first verb (a
  `run_intent`). No memory-over-time curve at any fidelity; the failure panel shows the record and
  explains nothing. (2026-08-25, 2026-08-29, 2026-09-01)
- **The AI monitor is deferred**, and three things were settled: it is not a Mendel door, automatic
  briefs always run redacted, and the console tail never crosses. (2026-08-29)
- **Open:** `ABORTED` counts as failed in `wiener_core/graph.py` (a meaning decision in a pure
  package); `submitted_by` is hardcoded `"operator"`, so *who* filters nothing (checked
  2026-09-28). (2026-08-25, 2026-08-29)

## The emitted pipeline

- **The v1 criterion:** from a plain-language prompt and a test dataset, emit Nextflow that runs
  green on the nf-core test profile and produces a counts matrix, on the RNA-seq spine. The spine
  runs and is asserted by `tests/emit/test_counts.py`; it has 10 processes, not the 15–20 the
  criterion names, and whether that clause survives is #11, undecided. (CLAUDE.md, 2026-09-28)
- A `RUN`-scoped channel emits as a value channel and an aggregator gets `.collect()`: the
  24-samples-run-once defect is fixed. A samplesheet pipeline runs under `--gate test`. (2026-09-01)
- **Open:** `DraftChannel.scope` has no control on the canvas, so the samplesheet is reachable by
  API and not by browser (checked 2026-09-28). (2026-09-01)

## Decided, and not to reopen

- The canvas flows **left to right** (`dag-core` serves both); **absence is absence**: a region
  with nothing to say is not drawn. (2026-08-29, 2026-08-30)
- Motion: five movements, one curve; numbers never tween; `grow-x` is first paint only.
  (2026-08-29)
- The forge's durable state lives in `mendel-api`, namespaced `forge_*`. (2026-09-04)
- `Comeni-Code` is a separate repository; nothing here grows toward it. (2026-09-01)
- What a model server does (keep-alive, slots) is the deployment's business, not the app's.
  (2026-09-29)

## Known traps

- **The stack:** the mendel `api` and `worker` mount `./packages` (and `api` reloads); `ai-worker`,
  `wiener-api` and `web` (nginx's config) run **baked**: rebuild them after a change, and
  `docker compose up -d` after a compose change. The stack reads `.run/registry`, a clone, not
  `registry/`. (2026-09-01, 2026-09-29, 2026-10-01)
- **Measure a model fix on the same sentences before and after:** a fix that passed `make check`
  made phrasing refusals go from 4 of 18 to 12 of 12. (2026-09-29)
- **On Ollama `cached` reads 0** (reuse shows only as speed); the first call after a rebuild is a
  ~70 s cold load; a hidden Chrome tab does not poll. (2026-09-29, 2026-09-30)
- **A `grep` at the end of an `&&` chain hides a failing test.** Run the suite alone, then commit.
  (2026-10-01)
- **Ollama's default context is 2048 tokens and truncates silently**; the goal prompt is ~4,300.
  Set `OLLAMA_CONTEXT_LENGTH` in `.env`. (2026-09-28)
- **Database tests need their own Postgres**: the Makefile `-include`s `.env`, which beats the
  environment, and the authoring fixtures truncate. Use a throwaway on `127.0.0.1:5442`, with the URL
  on make's command line. (2026-09-13)
- **Five tests fail on this branch's base:** `test_forge_jobs.py` ×4 (`MF0001`) and
  `test_full_cycle.py::test_the_loop_closes` (`MF0008`). (2026-09-13)
- **`npx tsc -b` is the typecheck**, not `tsc --noEmit`. (2026-08-25, 2026-09-13)
- **Layout bugs are invisible to jsdom:** `flex-1` with no flex parent, Tailwind classes built by
  concatenation, `position: fixed` inside a `transform`. Screenshot the page. (2026-08-25)
- **An unmapped Tailwind colour generates no CSS**; `tokens.test.ts` refuses one. Frontend comments
  cite issues as *issue 110*, since `#110` reads as a hex colour. (2026-09-13, 2026-09-28)
- **Headless Chrome** freezes `settle` at its first frame (`--force-prefers-reduced-motion`), and
  stands in when the extension is not connected (throwaway `--user-data-dir`). (2026-09-13, 2026-10-01)
- **Never `git submodule deinit` inside a worktree:** the config is shared, and it de-initialises
  the main checkout's `registry`. (2026-09-28)
- **Defence in depth is usually one mechanism and one decoration:** delete each half and watch
  what fails. (2026-09-04)

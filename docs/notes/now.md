# Now: what is true, and what is next

The consolidated state of the project. **Read this first**; then any entry still in
[the journal](journal/), since those are not compacted yet. How this page is kept:
[the compaction rules](compaction.md). Each line cites the entry it came from; the long form of any
line is in [the archive](journal/archive/).

**Compacted through: 2026-09-28.**

## Where the work is

- **Task 14 of the living pipeline, step 14.7: walking it with a real model.** The tree is GitHub
  issue #119 (Task 14 → steps → substeps → tasks, each a sub-issue). Round 1 of the walk found
  and fixed #106–#116. (2026-09-28)
- **Next: substeps 14.7.2–14.7.4**, the consultant's gathering stage, planned in
  `docs/superpowers/plans/2026-09-28-the-consultant-gathering.md` (#132–#134). Scenario 1 is
  blocked until 14.7.3 lands: nobody asks for the genome (#114), and paired-end has nowhere to go
  (#105). (2026-09-28)
- **Docs compaction (#118)** is in progress: `CLAUDE.md` to a ≤ 300-line brief, this page, and two
  checks in `make check`. (2026-09-28)

## How work is done now

- **Every defect gets a GitHub issue first.** Mechanical ones are fixed test-first and closed citing
  the commit; a rule or protocol question is brainstormed, the operator chooses, the choice is
  commented on the issue, then implemented. (2026-09-28)
- **Rules are tuned, never forced.** The thesis under test is the balance between flexibility and
  restraint: loosen what is too strict to function, tighten what is too loose. (2026-09-28)
- **Walk it, and look at it.** Every driven session found defects no suite could: 9 in the forge's
  first run, 14 in the first builder walk, 10 in the living pipeline's first hour. (2026-08-29,
  2026-09-06, 2026-09-28)
- **Reading finds wrong strings, not wrong pictures.** Compare a screen to its artboard in one
  viewport (`.design/_compare.html`), never by reading markup. (2026-09-01)

## The living pipeline (describe → build)

- A researcher types a sentence, chooses Build or Spawn, and builds beside a conversation at
  `/build?session=<id>`; `/build` and `/build?draft=<id>` are still the manual builder, which also
  offers the conversation from its Assistant tab. (2026-09-13, 2026-09-28)
- **The authoring protocol** is `docs/design/authoring-protocol.md`: the engine decides what is
  missing, a model only phrases and reads answers, nothing is guessed, an open measurement falls
  to tier 4, and stage ④ (the consultant build) is knowingly optimistic. (2026-09-28)
- **Protection level 0** (everything open) is the MVP; invariant 15 does not hold at level 0 and
  characterisation becomes a fourth AI point, both recorded loosenings. (2026-09-28)
- The goal prompt is `builder.goal.v2`; `v1` stays loadable as `prompts.RETIRED`. A prompt change
  is always a new version file. (2026-09-28)
- A resolve that fails for a missing input is **MI0207** in the conversation. (2026-09-28)
- **Open:** `MD0225` does not cover step selections (the keep route closes it for the product);
  whether `comeni-core` needs a version bump for `DraftProvenance`, MI0207 and door 1's payload.
  (2026-09-13, 2026-09-28)

## The forge (where declared data comes from)

- **The Forge MVP is complete** and runs end to end: catalogue sync (2,062 nf-core tools, 2 requests,
  ~10 s), scaffold, AI worker, local model, validation ladder, review. (2026-09-06)
- **The model is the weak link, not the loop:** `gemma3:12b` degrades as hole count grows; a
  stronger provider is a configuration change (invariant 13). (2026-09-06)
- **The review chat is door 5**, on `DoorPath.FORGE`; generating a proposal is not a door. A model
  may propose a vocabulary entry as a typed value, never land it. (2026-09-05, 2026-09-06)
- **Archiving is legal from any state a worker does not hold**; `failed` and `archived` answer
  different questions. (2026-09-04)
- **Never run:** approve → land → `mendel build` on a fully answered candidate; a second revision;
  the review chat; pegi3s (needs a Docker Hub credential). (2026-09-06)
- **Open:** `forge_revision.registry_digest` is `String(64)`, too short for a `sha256:` digest
  (checked 2026-09-28). (2026-09-13)

## Wiener (run → watch)

- `/runs` is a board and `/runs/{id}` a page of bands; **cancel** is the first verb, recorded as a
  `run_intent`. (2026-08-25, 2026-09-01)
- **No memory-over-time curve at any fidelity:** a reservation is exact, a total is area-true and
  drawn stepped, and a peak does not distribute. `137` is glossed as `SIGKILL` and nothing more.
  (2026-08-29)
- The failure panel shows the record (`errorReport`) and explains nothing. (2026-08-29)
- **The AI monitor is deferred**, and three things were settled: it is not a Mendel door, automatic
  briefs always run redacted, and the console tail never crosses. (2026-08-29)
- **Open:** `ABORTED` counts as failed in `wiener_core/graph.py` (a meaning decision in a pure
  package); `submitted_by` is hardcoded `"operator"`, so *who* filters nothing (checked
  2026-09-28). (2026-08-25, 2026-08-29)

## The emitted pipeline

- A `RUN`-scoped channel emits as a value channel and an aggregator gets `.collect()`: the
  24-samples-run-once defect is fixed. A samplesheet pipeline runs under `--gate test`. (2026-09-01)
- **Open:** `DraftChannel.scope` has no control on the canvas, so the samplesheet is reachable by
  API and not by browser (checked 2026-09-28). (2026-09-01)
- The `test` profile is all-or-nothing, and that refusal is correct. (2026-09-01)

## Decided, and not to reopen

- The canvas flows **left to right**; one layout (`dag-core`) serves both canvases. (2026-08-30)
- **Absence is absence:** a region with nothing to say is not drawn, and nothing is dropped to fit.
  (2026-08-29, 2026-08-30)
- Motion: five movements, one curve; numbers never tween; `grow-x` is first paint only.
  (2026-08-29)
- The forge's durable state lives in `mendel-api`, namespaced `forge_*`. (2026-09-04)
- `Comeni-Code` is a separate repository; nothing here grows toward it. (2026-09-01)
- A settings menu (pacing, protection level, prompts) is deferred: #117. (2026-09-28)

## Known traps

- **The stack:** the mendel `api` and `worker` mount `./packages` (and `api` reloads); `ai-worker`
  and `wiener-api` run **baked**, so `docker compose up -d --build ai-worker wiener-api` after a
  backend change (checked 2026-09-28). (2026-09-01)
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
- **Headless Chrome freezes `settle` at its first frame**; capture with
  `--force-prefers-reduced-motion`. (2026-09-13)
- **Never `git submodule deinit` inside a worktree:** the config is shared, and it de-initialises
  the main checkout's `registry`. (2026-09-28)
- **Two mechanisms presented as defence in depth are usually one mechanism and one decoration.**
  Delete each half and watch what fails. (2026-09-04)

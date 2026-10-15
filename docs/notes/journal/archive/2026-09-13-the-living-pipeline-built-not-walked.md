# 2026-09-13 — the living pipeline, built and not yet walked

**Thirteen of fourteen tasks are complete, and the fourteenth is the one that matters.** The plan
is [`2026-09-07-the-living-pipeline.md`](../../superpowers/plans/2026-09-07-the-living-pipeline.md):
106 of its 115 steps are ticked, each task carries an execution record, and every record says what
was watched failing. **What has not happened is a person describing an analysis in a browser with a
real model behind it** — and the plan's own completion criteria say it is not done until that has.

This entry is a handoff. It was written on a machine that cannot run a local model, for an agent
continuing on one that can. Read *What to do next* first if that is you.

**This is also the day the Forge MVP reached `main`.** `origin/main` had nothing of the forge's
4–6 September commits; they and the living pipeline's 7–13 September commits went up together as
one fast-forward, so read
[`2026-09-06-the-forge-runs.md`](2026-09-06-the-forge-runs.md) as well if the forge is new to you.

---

## What exists now

A researcher types a sentence on the first-run screen, chooses **Build** or **Spawn**, and lands on
`/build?session=<id>`: a canvas beside a conversation, over **one draft**.

| Part | Where | What it does |
|---|---|---|
| typed door 1 | `mendel_api/authoring/` | `AuthoringRequest` carries the bounded transcript tail and the option ids a model must answer with; a reply names an option or it is refused |
| durable sessions | `services/authoring.py`, migration `f7a2c9b41d05` | sessions, turns and proposals in Postgres; a reload restores a pending turn without duplicating it |
| per-decision provenance | `DraftProvenance` | resolver, model and person are recorded per step and per setting, and survive into `pipeline.yml` |
| prompts | `authoring/prompts/builder.{goal,chat,tier4}.v1.md` | versioned files; every call writes an `ai_invocation` row |
| blueprint engine | `services/blueprint.py` | resolves the whole pipeline once, orders it by `dag-core` rank, and offers it one step at a time with registry-backed alternatives |
| Spawn | `authoring.spawn_forward` | a loop over Build's own commit: accepts resolver-settled and model-chosen tier-4 steps, stops on anything else and leaves Build's card |
| API | `routes/authoring.py` | begin, read, say, decide, retry, preview, edit, vocabulary |
| the page | `frontend/src/build/living/` | `useAuthoringSession` (TanStack Query) + a pure reducer; canvas, decision log, cards, composer, artifact drawer |
| collections | `CollectionChannel.tsx` | one stroke, a three-strand ribbon, or a converging ribbon — N is on the source, never as copies of a node |
| motion | `main.css` `living-*` | driven by domain events, off under reduced motion, a Spawn reveal that plays once per tab |
| preview | `drafts.preview` | the canonical serializer, in memory: `ready`, `empty`, `illegal` with `MD05xx` findings, or `unavailable` — never half a document |
| Keep / Run | `useKeep(graph, { draftId })` | keeps the session's own draft without creating a second, then the existing lint → run sheet |
| first run | `home/First.tsx`, `app/BuildRoute.tsx` | live only when `/health/ai` says a model is configured; otherwise disabled with the reason and *draw it yourself* |

**Routes.** `/build?session=<id>` is the living builder. `/build` and `/build?draft=<id>` are still
the **manual builder, unchanged** — an old draft has no session, and the living shell would show it
as a canvas with nothing behind it. `/build/living?fake=1`, `?fake=guided` and `?fake=collect` are
static sessions for looking at every state without a model.

**Checkpoints that are met in tests:** Build and Spawn over the RNA-seq fixture end at one draft and
byte-identical YAML while their histories differ; over a tier-4 model choice, authorship differs at
that step and nowhere else; the kept file, the preview and the artifact reload are identical byte
for byte.

## What was found, and was not findable by the suite

1. **`text-ink-4` generated no CSS anywhere in the app.** `@theme` mapped `ink` to `ink-3` and
   stopped, so every dim label in ten files — `RunSheet`, `Settings`, `Rail`, `Run`, `Timeline`
   among them — rendered at full ink. Found by putting the first-run screen beside `LivingOpen`.
   `--color-ink-4` is added, which **changes how existing screens look**. A new guard in
   `tokens.test.ts` requires every palette token worn as a colour utility to be mapped, and on its
   first run it found a second one: `bg-node` in `ReviewGraph.tsx`, a card with no fill since
   `8bfaa23`.
2. **A debounce test was inert.** One long `act` flushed six revisions into one render, so it
   passed with the debounce deleted. It advances in short acts now.
3. **`tsc --noEmit -p .` checks nothing in this frontend.** The real typecheck is `npx tsc -b`.
   Earlier tasks were reported as typechecked on the wrong command; Task 10's record corrects it.
4. **`ai.available` was mode-dependent for three tasks**, which would have made Build and Spawn emit
   different YAML over one goal. It follows the installation now; `used` is where modes differ.
5. **Headless Chrome freezes `settle` at its first frame.** A capture that is missing cards the DOM
   holds is this; capture with `--force-prefers-reduced-motion`.

## Open, and not ours to close today

- **`MD0225` does not cover step selections.** It checks model-sourced *settings*; which contract
  fills a step is not one, so a draft kept by a path that passes no AI points records
  `available: []` beside a model's decision and nothing refuses it. The keep route closes it for the
  product. `test_authoring_keep.py` says so in its docstring.
- **`forge_revision.registry_digest` is `String(64)`**, too short for the `sha256:`-prefixed digest.
  The authoring session's column was widened to 80 in `f7a2c9b41d05`; the forge's was not.
- **`make check` silently skips every database test on a machine whose `.env` points elsewhere** —
  the Makefile `-include`s `.env`, which overrides `MENDEL_DATABASE_URL`. The authoring tests were
  run against a throwaway Postgres on `127.0.0.1:5442` for that reason.
- **Failing on this branch's base, not caused by it:** four in `test_forge_jobs.py`
  (`MF0001: 'fake' is not a catalogue source`) and `test_full_cycle.py::test_the_loop_closes`
  (`MF0008: no stored scaffold`). Confirmed by stashing the day's changes.
- **Whether `comeni-core` needs a version bump** for `DraftProvenance` and the widened door-1
  payload was not judged. `docs/guides/releasing.md` is the rule.

## What to do next

**Task 14's remaining nine steps**, in the plan's order. Steps 1–3 need no model; 4–9 do.

1. **Preserve the manual builder's actions** that still matter — module browsing, settings,
   swapping, validation, artifact, Run — and remove `Rail.Assistant`'s placeholder only once the
   living path is reachable from the home page, which it now is.
2. **Keep the old builder mountable** through the walk. Deleting it is a separate change, after its
   requirements are tests; `Restored.test.tsx`'s assertions move, they are not erased.
3. **Run the ladder narrowest first:** focused Python tests, `npx vitest run`, `make client`,
   `npx tsc -b`, lint, `make check`, `make guards`, `make verify`. Check `make check` actually ran
   the database tests — see above.
4. **Bring up the real stack with a model.** `git submodule update --init`, `uv sync`,
   `npm ci` in `frontend/`, then `make migrate` — three migrations arrive with this push. The APIs
   run from a **baked image**, so `docker compose up -d --build` the API and the AI worker. Set
   `COMENI_AI_MODEL` (and `COMENI_AI_BASE_URL=http://ollama:11434` for the local lane); on an AMD
   card, `docker-compose.ollama-rocm.yml` with `OLLAMA_IMAGE=ollama/ollama:<version>-rocm`.
   `gemma3:12b` is what the forge ran on 2026-09-06, and that entry records its structured output
   degrading with hole count — a stronger model is a configuration change, and worth it here.
   `GET /api/health/ai` should say `configured: true` and `worker_available: true` before starting.
5. **Walk it in a browser**, the plan's nine: Build *paired-end RNA-seq → gene counts*; Spawn, the
   same request; many FASTA/FASTQ items with an ambiguous grouping answer; one alternative module;
   one parameter correction; a *why?* follow-up; reload while a turn is pending; a refusal and the
   no-model state; Keep → lint → run sheet on the completed draft.
6. **Put the page beside the artboards** at the designed widths — `.design/living-pipeline/*.dc.html`
   — and exercise reduced motion, keyboard only, touch-like input, long content and a 15-module
   graph. Render; do not read.
7. **Confirm from `ai_invocation` rows and logs** that only declared calls happened, and from the
   final `pipeline.yml` that resolver, model and person are recorded per decision.
8. **Update the handbook from what was observed** — `your-first-pipeline.md`, `builder.md`,
   `product-loop.md`, `core-words.md` — and nothing that was not.
9. **Write the journal entry for the walk**, naming the model, and move `CLAUDE.md`'s pointer to it
   in the same commit.

**Expect the walk to find defects the 512 frontend and 574 API tests did not.** The forge's first
driven day found nine. The places most likely to break are the ones only a model exercises: a goal
reply that does not admit, a tier-4 answer outside its options, and a turn that is still pending
when the page reloads.

## Decisions taken

- **An old draft opens in the manual builder**, not the living shell. Task 1's design did not
  address it; the argument is above, under *Routes*.
- **Only a count is stored for the Spawn reveal**, in `sessionStorage` — never transcript content.
- **Run is disabled wherever nothing is connected to it**, including every `?fake=` page.
- **The home prompt's mutation is a hook** (`home/useBegin.ts`), because `reported.test.ts` holds
  that a mutation is reported by returning it; that scan was corrected to stop counting a hook's
  own file as its caller.

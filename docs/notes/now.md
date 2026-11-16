# Now: what is true, and what is next

The consolidated state of the project. **Read this first**, then any entry still in
[the journal](journal/). How this page is kept: [the compaction rules](compaction.md). Each line
cites its entry; the long form is in [the archive](journal/archive/).

**Compacted through: 2026-10-26.** Earlier `CLAUDE.md` history: `tests/fixtures/claude-md-2026-09-28.md`.

## Where the work is

- **Task 14, step 14.7: walking the living pipeline with a real model.** The tree is #119.
- **One builder (#395) plans 1–5 and Part I.2 (#293) are built** (journal 10-27, 10-28, not yet
  compacted); their browser checks are #404. Also #357, #302. (10-22, 10-28)
- **#463 push:** on the branch: phases 1–2 (#460 merged, #464), rules v2 (#461), measurers
  (#465, #217), per-sample 1–6 (#466), forge measurers (#487), learned rules (#462); registry
  on local `measurers`. Next: browser checks, the QUAST walk, tuning the AI (`MIN_CASES`).
  After merge, bump the registry's `ENGINE_REF` (no MD0027 in its CI until then). (11-14)
- **Walks run on GPT** through the ChatGPT subscription (#457), not local models. (11-10)
- **All of it is on `main`** (PR #402, with a behaviour-preserving refactoring campaign). Left for
  an authorised behaviour pass: Node under Vite's floor. (10-26)

## How work is done now

- **Every defect gets a GitHub issue first.** Mechanical ones are fixed test-first and closed citing
  the commit; a rule or protocol question is brainstormed, the operator chooses, the choice is
  commented on the issue, then implemented. (2026-09-28)
- **The simplest change that obeys the existing rules**: derive rather than declare, and say why
  any new concept is needed. (2026-10-16)

## The living pipeline (describe → build)

- **The builder is an agent** (#463, on the builder-agent branch): it reads, chooses through
  tools, builds and explains; the engine validates, routes, offers rules as advice and emits.
  How it works: `docs/explanation/builder-agent.md`; design:
  `docs/superpowers/specs/2026-11-14-builder-agent-design.md`; plan:
  `docs/superpowers/plans/2026-11-14-builder-agent.md`.
  The scripted walk (stages, proposals, suggestions, pacing, the protocol) is deleted. (11-15)
- A researcher types a sentence and builds beside a conversation at `/build?session=<id>`;
  `/build?draft=<id>` and a bare `/build` open one too: every pipeline has one. (09-13, 10-22)
- **Every AI choice is the AI's**: tier 4, source model, with its `because`, and any rule it
  overrode beside it; flagged for review, never blocking. The person's direct actions go
  through the same writer (`mendel_api/services/changes.py`) and rebuild at once. (11-14)
- **The same tools over MCP** at `/api/mcp`, behind `MENDEL_MCP_TOKEN`; off without one. (11-14)
- **A hand edit is read as intent** (`read_edit`): applied as the person's change and kept as
  structural intent (`absent_roles`, `exclusions`, `sources`; `MD0319`–`MD0321`). (2026-10-22)
- **An unanswered tier-4 setting is optional** when its route leaves the tool its own behaviour
  (`OMITTABLE`: `ext`, `directive`): still flagged, it stops nothing (#384). Tier 3 is never
  called *measured* (#387, #397). (2026-10-22)
- **Current decisions are retained rows**, one pointer per subject; corrections cascade reviews,
  truthful unbuildable answers stay. (2026-10-11)
- **Open:** the frontend's agent thread (task 12); AI reading a file as a tool (#501); tier-4
  structure for the agent (#502); how samples differ, as a spread (#503); `MD0225` does not
  cover step selections. (2026-11-15)

## Samples

- **Data is ticked folders, read in place** (#511): each file's first 4 MB, measured by a child
  process with no secrets and hard limits; facts are derived from the analysis's data at every
  read, never logged. Upload, protection levels, characterisation (door 6) and shape versions were
  removed on 2026-11-16; AI reading an unrecognised file returns as an agent tool (#501).
- **Measurers are composed pieces** in `registry/measurers/` (codecs, formats, measurers), run
  only from trusted layers in one pass; below a threshold a measurer says *undetermined*. (11-10)
- **A measured fact is `MEASURED`**, naming its pieces and evidence. Adding a piece:
  `registry/measurers/README.md`. The registry is one folder per tool; the path is the id. (10-03)

## Settings (Settings → behind the gear)

- **Per installation; `.env` is a lock, not a seed.** Each value says where it came from; one
  declaration per setting in `comeni_core/settings/`; the API and menu are generic. (2026-10-01)
- **A model per purpose** (`model_access(agent, purpose)`); `.env`'s `COMENI_AI_*` still work; keys
  typed in the menu are sealed with `COMENI_SETTINGS_KEY`. (2026-10-01)
- **On the RX 7600 (8 GiB):** gemma3:4b and qwen2.5:7b fit (0.5–3 s a call); gemma3:12b spills
  36% to the CPU (3–7 s, about 20 s a chat reply) and is what the walks run. (2026-09-29, 10-18)
- Pacing is live; tier 4 by a model and k8s/awsbatch remain designed; a privacy posture is #71. (10-01)

## The screens

- **The hybrid identity shared with Comeni Code is built** (#370, `.design/hybrid/`), each screen
  matched to its board at 1400 and 390 px and in dark; what a board shows without data is not
  drawn. A step has no *Skip*; tier words are served (`useTiers`). (2026-10-20, 2026-10-21)
- **Labs stays on FastAPI**; accounts would be one OIDC sign-in shared with Code. (2026-09-17)

## The forge (where declared data comes from)

- **MVPs 1–6 are on `main` (#415); comeni-registry v0.5.0 is its first release.** #365–#367 stay
  open. **The [live walk](../how-to/development/forge-live-walk.md) (#412) stopped at step 4;**
  findings are #420–#432. Redesign slices 1–6 landed (#445); #428/#431 have approved decisions
  and implemented fixes. #441 adds explicit, approved Family declarations in Vocabulary.
  **Next:** resume live step 4, on GPT. No redesign slice 7 is planned; MVPs 4–6 already have implementations. (11-03)

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

# Now: what is true, and what is next

The consolidated state of the project. **Read this first**; then any entry still in
[the journal](journal/), since those are not compacted yet. How this page is kept:
[the compaction rules](compaction.md). Each line cites the entry it came from; the long form of any
line is in [the archive](journal/archive/).

**Compacted through: 2026-10-03.** `CLAUDE.md` as it stood before that day, with its plan-by-plan
history (Plans 1–6, 3A–3E, Wiener W1/W2, the audit rounds), is kept verbatim in
`tests/fixtures/claude-md-2026-09-28.md`.

## Where the work is

- **Task 14 of the living pipeline, step 14.7: walking it with a real model.** The tree is GitHub
  issue #119 (Task 14 → steps → substeps → tasks, each a sub-issue). Round 1 of the walk found
  and fixed #106–#116. (2026-09-28)
- **Order of work, in #119's own order** (renumbered 2026-09-28 so the tree reads as done):
  14.7.3 gathering, 14.7.4 the consultant's words, 14.7.5 settings and 14.7.6 samples are
  **done** → **14.7.7** the characteriser (#135, next) → **14.7.8** the consultant build
  (it also reads pacing, #117) → **14.7.9** tune what the walks found (#210) → **14.7.10** the nine
  scenarios. **MVP first, then tune:** a defect found on the way joins #210 unless it blocks the
  loop. (2026-09-28, 2026-09-30, 2026-10-01, 2026-10-03)
- **Scenario 1 builds end to end with `gemma3:12b`**, started from home and answered by uploading
  the real pair SRR6357070; the aligner is tier 3 with a read length, tier 4 without, and its reason
  names what measured it. (2026-09-28, 2026-10-03)

## How work is done now

- **Every defect gets a GitHub issue first.** Mechanical ones are fixed test-first and closed citing
  the commit; a rule or protocol question is brainstormed, the operator chooses, the choice is
  commented on the issue, then implemented. (2026-09-28)
- **Rules are tuned, never forced.** The thesis under test is the balance between flexibility and
  restraint: loosen what is too strict to function, tighten what is too loose. (2026-09-28)
- **Walk it, and look at it:** every driven session found defects no suite could; compare a
  screen to its artboard (`.design/_compare.html`), never by reading markup. (2026-09-01, 2026-09-28)

## The living pipeline (describe → build)

- A researcher types a sentence (on an empty home, or the describe bar above the work once there is
  some), chooses Build or Spawn, and builds beside a conversation at `/build?session=<id>`;
  `/build` and `/build?draft=<id>` are the manual builder. (2026-09-13, 2026-09-28, 2026-10-03)
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

## Samples (protection level 0)

- **A gap can be answered with a sample**, one file or a pair: the browser sends each file's first
  4 MB, the server holds it in memory, measures it in a child process with no secrets and hard
  limits, and keeps facts, never bytes. Upload is offered only where a trusted format reads one of
  the person's inputs; the person's word always stands over a sample's. (2026-10-03)
- **Inspectors are composed pieces** in the registry (`registry/inspectors/`: codecs, formats, measures,
  code beside each), run only from trusted layers (`MENDEL_TRUSTED_LAYERS`), one pass over the
  head; below a threshold a measure says *undetermined* and why. FASTQ measures read length,
  pairing and quality encoding (0.21 s for a 4 MB head, budget 1 s). (2026-10-03)
- **A measured fact is `MEASURED`**, naming its pieces and evidence (*measured · fastq 1.1.0 ·
  from 1 sample*). Adding a piece: `registry/inspectors/README.md`. (2026-10-03)
- **The registry is one folder per tool**, the path is the id; a request's registry time fell
  from 10.69 to 1.55 ms. Its inspectors merged to the registry's `main` (PR 15). (2026-10-03)

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
- Motion: five movements, one curve; numbers never tween. (2026-08-29)
- The forge's durable state lives in `mendel-api`, namespaced `forge_*`. (2026-09-04)
- A model server's keep-alive and slots are the deployment's business. (2026-09-29)

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
- **Headless Chrome** freezes `settle` at its first frame (`--force-prefers-reduced-motion`), and
  stands in when the extension is not connected (throwaway `--user-data-dir`). (2026-09-13, 2026-10-01)

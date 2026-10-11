# 2026-10-07 — 3c walked in a browser, and an audit of where data lives

## Where things stand

- **3c has been walked once in a browser**, on the operator's main PC (gemma3:12b on Ollama,
  ROCm), at `0a086e98` on `stage-four-the-consultant-build`. Issue 262 holds the findings.
  - Pacing *together*, telling the read length on STAR's card: passes. The canvas becomes
    HISAT2 with its own index and no STAR step is left.
  - Pacing *together*, choosing HISAT2 on STAR's card: passes. The next card is HISAT2's index,
    and the wrap-up credits the person (tier 4, by human).
  - Pacing *stop only where needed*: **blocked** after its first card (issue 263, `MI0202`).
  - *Ask me every time*, and Dev mode: not walked. No Dev mode card was offered in any walk
    (issue 264).
- **`make slow` passes** on this branch (the router change), run against a throwaway database
  URL so its fixtures could not reach the dev database.
- **An audit of data storage and flow** across both services and Redis is issue 270, with
  sub-issues. Its design-level findings are folded into issue 269.

## What changed

No code. Issues 262–281, a comment on 269 folding in the audit's design findings, and a
comment on 263 with its cause.

## Decisions made, and why

- **A fact can always be changed, and what a person decides is kept as rows** (operator,
  issue 269). Today a step's card offers only the facts a rule *lacks*, so a told read length or
  strandedness cannot be corrected during the walk. Proposed rule: what a person decides gets
  rows (facts, the goal's parts, the reviewed steps); what the engine computes stays a blob
  (the blueprint, which is `resolve(goal)`). To be brainstormed, then specced.
- **Strandedness is not measured, for now** (operator). A FASTQ does not record strand; it is
  seen only after alignment (RSeQC `infer_experiment`, Salmon's auto-detection). That is a
  profiler that aligns reads, and it is not in the MVP. Asking the person stays.
- **The explanations' wording improves through the forge and prompt tuning** (operator), not by
  hand-editing each one. The upload copy in `SampleUpload.tsx` is hand-written and is issue 267.
- **Inspector measurements do reach the router.** An uploaded sample's measurements become
  session facts marked `measured`; `compose_goal` writes them into the goal's profile as
  `ValueSource.MEASURED`; every change re-resolves from the goal. Only what an inspector
  measures is carried, and a value the person already stated is never overwritten.

## The audit

Four questions: one source of truth for each thing; state passed through methods as untyped
plumbing rather than typed classes or rows; ordinary relational practice; anything only Redis
knows.

**Bugs now.**
- *The draft revision has several writers and no owner.* Settling a proposal, re-projecting
  after a change and a hand edit each move it, in three modules. `PUT /drafts/{id}` replaces the
  graph without checking or moving it and is not refused during the walk (272). Issue 263 is
  the same shape: a card proposed at the revision before the quiet steps were placed.
- *A rename is lost on reload* (271): the route stores the graph and echoes the name.
- *A run can launch twice* (273): no job id, and `launch` does not claim the run before spawning.
  A queued run's parameters exist only in the Redis job argument, and Redis is snapshot-only.
- *"Kept" is a file's existence* (277): nothing records which revision was kept, so an edited
  draft still lists the old artifact's digest and outputs.

**More than one source of truth** (folded into 269).
- The goal is on the session and on the draft. The session's `goal` column holds three shapes
  in turn: the want while gathering, a cache of the model's question wordings (`phrased`), then
  the confirmed `Goal`.
- `facts` stops being current at confirmation; later facts go only to `goal.profile`.
- The draft graph is meant to be a projection during the walk and can also be written by the
  browser; its provenance is computed in two code paths.

**Untyped plumbing** (275).
- A proposal's payload is an envelope dict; only its `block` is validated. The option mapping,
  amendments and edges are read by key across the stage modules.
- `Ctx.payload` in the dispatcher is a plain dict.
- The resolver's `_resolve_param` takes a contract parameter's fields one by one plus the
  resolution's context, and appends to a list it is handed.

**Relational practice** (274).
- No CHECK constraints in either database: every state, phase and kind is a free string, and
  the allowed values live only in Python enums.
- Wiener has no foreign keys, and each child row copies `lab_id` with nothing tying it to its
  parent's.
- `gate_run.draft_id` has no foreign key. Wiener's per-run Redis streams are never removed.

**Before real users** (276, the operator's to decide): a schema version on each JSON column,
`JSONB` where anything is queried, and durable run parameters.

**What is done well, and should be kept.**
- Mendel's foreign keys are all RESTRICT, held by a test, so a delete never takes history.
- Optimistic `row_version`; partial unique indexes (one pending card, one active adaptation)
  each held to its enum by a test; turns ordered by `seq`, not time.
- `ai_invocation` keeps every field an evaluation aggregates as a column.
- Wiener's `run_event` is the record; `run` and `run_task` are projections with a replay test.
- Mendel's jobs carry ids only, so Postgres stays the truth; job ids are derived from the work,
  so a duplicate is a no-op; a sweep reclaims lost jobs.
- The frontend keeps server data in its query cache and only UI state in its reducer.
- There is one `Goal` type, re-exported where needed.

### A targeted second pass

Four areas the first pass did not reach, with a stop rule: stop when a pass finds nothing above
minor. This one did not meet it.

- **Transaction boundaries.** Authoring is sound: `perform` runs one command in one
  `transaction()`, nested scopes are savepoints, jobs are queued after the commit. The cause of
  263 is ordering, not transactions: `walk.step` offers the first card before it projects the
  quiet steps, so the card records the old revision and wires against the old graph (commented
  on 263). **Gates are not sound** (278): arq's default job timeout (300 s) is below the stub
  and test gates' own (900 s, 3600 s); the result is written in a second transaction that a
  cancelled job never reaches, and only `ValueError` is caught, so a gate can stay `running`
  forever. Latent: only lint gates have run through the worker here.
- **Models against migrations** (279). `alembic check` finds drift in both databases: two forge
  indexes the models do not declare, and `run_task.labels` nullable in Wiener's database. The
  migration test compares tables and columns, not indexes or nullability; Wiener has none.
- **Files as a second store.** Wiener's artifacts and run directories are keyed by their own ids
  and hold a digest: sound. The forge's candidate lives at one path per adaptation and is
  overwritten by each revision, while the revision row promises the superseded candidate
  survives (280).
- **What is never deleted.** Nothing, in either service (folded into 276 as retention). The
  sharpest case is privacy: the characteriser's sample excerpt waits in Redis inside job
  arguments, and Redis snapshots to a persistent volume, so the excerpt can reach disk although
  the level-0 table says files are held in memory and never stored (281).

## What is next

1. The operator chooses the order. Recommended: 263 (the walk cannot finish under one pacing;
   the cause is known), then 281 (a claim about where patient data goes), then 278, 271 and
   273 (mechanical), then the brainstorm for 269, since 272 and the goal's shapes are decided
   there.
2. Walk *ask me every time*, and look for Dev mode (264).
3. Compare the screens to the artboard (`.design/_compare.html`), which this walk did not do.

## Open questions

- Durable run parameters: Redis `appendonly`, or a home §7.1 allows (276).
- One decision table with a kind, or one table per kind (269).
- When a measured and a told value disagree and either may later change, which stands (269).

## Traps

- **`make slow` reaches the database fixtures**: give it `MENDEL_DATABASE_URL` for the
  throwaway on 5442 when `make dev` is up.
- **`gh issue create` failed with a GraphQL error** on one body and did not create the issue;
  `gh api -X POST repos/<owner>/<repo>/issues` created it. Check the issue list before retrying.

# 2026-08-30 — the floor, the results, and the front door

**Read this first if you are picking the project up. This is the newest entry.** It covers three
phases of Plan 4 executed in one day, on `worktree-plan-4-phase-0`.

The redesign of 2026-08-29 produced a canvas and nothing else — *"nothing in `packages/` or
`frontend/` changed in this session"*. This is the session where it started becoming code.

## Where things stand

**Plan 4 phases 0, 1 and 2 are complete.** The plans are in
[`../plans/`](../plans/), each with its steps ticked and an execution record naming every
deviation.

- **Phase 0 — the shared floor.** One easing curve where there were three, five named movements,
  two content breakpoints, and one answer to *a mutation failed*. The forge left the navigation
  and stayed in the router.
- **Phase 1 — `publishDir`.** The emitted pipeline publishes what it makes, and
  `GET /runs/{id}/results` lists it. Until now a finished run left its outputs in `work/<hash>/`
  under names nobody can read.
- **Phase 2 — the Overview.** `/` is the lab's work rather than the product's inventory, and the
  whole product moved to the **Observatory** palette on the way.

**`make verify` green at 1655; `make check` green at 1686 with a database up. Frontend: 284 tests
in 51 files, `tsc` clean, lint unchanged at its five pre-existing warnings.**

## The pattern, for the fourth time running

**Every defect that mattered was found by running the thing or by looking at it. None by a test
written to pass.** W1 found five that way, W2 six, the 2026-08-29 walk fourteen. This session:

- **`publishDir` shipped publishing NOTHING with all five processes green.** `enabled: { … }`
  hands Nextflow a closure where it expects a value and it is never called. The stub gate said
  PASS, `nextflow config` printed the directive correctly, the log said nothing at all. `ls
  results/` is what found it.
- **The first fix was also wrong**, and only a second run showed it. An expression `enabled` is
  evaluated while the `process {` scope is read, so it sees a **command-line** `--outdir` and not
  a **profile-set** one. The plan's own step put it in the two gate profiles; measured, that
  published nothing while `--outdir` published 41 files.
- **The provenance bar cried wolf.** Counting raw tier 4 reported *five* things needing a person
  on a pipeline where **one** did — because a hand-drawn graph records every step as `tier: 4,
  source: human`, and `source: human` is exactly what clears a review.
- **Three defects survived a green suite and died on sight**: the running bar's `flow` marker
  filled the whole remainder (saying *everything not yet done is running now*), the running row
  was titled by its run id rather than its pipeline, and the elapsed time was missing.

**The page was rendered and looked at**, against fixtures, in all three states. That is thirty
seconds of work and it is the step this project has skipped every time it later regretted
something.

## What the plans got wrong, and what that says

Nine findings changed a task. The instructive ones:

- **`tokens.test.ts` was already the guard phase 0 asked me to write.** It has walked every file
  and every `var()` since 2026-08-24. What was missing was the same guard one layer up — a
  motion *class* whose rule nobody wrote, which renders as *nothing moves* and looks exactly
  like reduced-motion working.
- **The silent-500 premise was wrong.** No mutation hook has ever swallowed an error. `useKeep`
  returned one, documented *"Shown, not swallowed"*, and `Builder.tsx` handed `Walk` a prop with
  no slot for it. **A `useMutation` wrapper would not have caught it.** The fix is a required
  prop, and `tsc` named all three forgetful call sites immediately.
- **An audit-by-grep invented a six-hook debt list that was fiction.** All six return the
  mutation whole, which carries `.error`. Caught only because a revert written to watch that
  guard fail **did not apply** — and the guard passed. That is question 3 of the guard ledger's
  own three, answered wrongly for a full cycle.
- **`pipeline_draft` DOES have an owner column.** The canvas annotation says it does not.
- **There was no `GET /drafts` at all**, which the canvas could not have seen because it was
  drawn against screens rather than routes. The Overview's entire *by pipeline* half had no query
  behind it.
- **`RunArtifact.pipeline_digest` was declared in W1 and never written** — the right type, the
  right nullability, no assignment anywhere. It is the join key the front door needs twice.

## Decisions taken

- **Observatory is the default palette**, and the light one is re-homed to `[data-theme="light"]`
  rather than deleted. `dashboard.md` §2 records what it supersedes: *deep botanical green as
  primary, Mendel's peas* does not survive, and `--pea` keeps its **name** so every call site and
  every sentence about tiers still reads.
- **The migration was cheap because no component names a colour** — no hex, no `rgba(`, no
  `bg-slate-700`, anywhere. It touched `tokens.css`, one `@theme` mirror and nothing else. That
  held by convention; it is a guard now.
- **The first-run prompt ships visibly disabled**, with the reason under it. It is **door 1**,
  declared by invariant 3 and implemented nowhere. The operator chose showing what is coming over
  omitting it; what must never happen is it appearing to work, or a model producing a pipeline
  rather than a goal.
- **`submitted_by` keeps its slot and ships no filter.** It is hardcoded `"operator"`, so the
  column renders as visibly not-yet-real and the `who` filter is not built — a filter that
  filters nothing is what `rn-board` and `ov-scope` both forbid.
- **`forge-review.md` §3's constraint is lifted, and recorded as lifted.** That document said an
  Overview page may not exist. The narrower rule survives and is enforced: `/` may render
  pipelines and runs, never a contract id, a question subject or a drift row.

## What is next

**Phase 3 — the builder**, in two parts. Its defects are all *feedback* defects and the canvas
already says what the feedback should be. It also inherits two known tensions from phase 0:
`breathe` and `animate-pulse` are a sixth and seventh movement, and retiring either is a visible
change to a screen phase 3 or 5 owns.

Then **phase 4** (runs projections — `series()` in `wiener-core`, attempt windows, per-attempt
resources) and **phase 5** (the runs screens).

**Deferred, named rather than forgotten:**

- **"Changed underneath you"** — `upgrade --dry-run` per pipeline on a worker schedule, a table
  and an endpoint. Its own phase after the runs screens, by the operator's decision.
- **The resource sentence** on the Overview. It needs reserved-vs-used aggregated across runs, and
  *reserved* lives in `run_task.attempts` as JSON rather than a column — the **same** projection
  phase 4 does for the envelope. It does not render, which is the absence rule working.
- **Results ready** on the Overview. Phase 1 built `GET /runs/{id}/results`, and the block needs a
  lab-wide listing rather than a per-run one. Small, and it belongs with the runs work.

## What a fresh reader gets wrong

- **"The Overview looks sparse."** It is. Three of the artboard's blocks are absent on purpose —
  two are blocked on a projection phase 4 does, one is deferred to its own phase — and *absence
  is absence* is the page's governing rule. An empty region is faster to read than a paragraph
  explaining that it is empty. Compare the `Overview` and `OverviewQuiet` artboards: the quiet
  one is not a different empty state, it is a shorter page.
- **"The palette migration was a big change."** It was a large *decision* and a small diff. Read
  `dashboard.md` §2 for what it supersedes before reopening it.
- **"`by_person` is a fourth band the design does not have."** Correct, and the design was drawn
  against resolver-built pipelines where it is always zero. See the ledger.
- **"Nobody has looked at these screens."** For the Overview, somebody has — all three states,
  rendered and read. The Builder and Runs screens still carry that debt.

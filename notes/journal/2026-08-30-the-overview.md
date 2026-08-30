# 2026-08-30 — the floor, the results, the front door, and the builder

**Read this first if you are picking the project up. This is the newest entry.** It covers five
phases of Plan 4 executed in one day, on `worktree-plan-4-phase-0`.

The redesign of 2026-08-29 produced a canvas and nothing else — *"nothing in `packages/` or
`frontend/` changed in this session"*. This is the session where it started becoming code.

## Where things stand

**Plan 4 phases 0, 1, 2, 3a and 3b are complete.** The plans are in
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
- **Phase 3a — the builder's shell.** Draw → Keep → Gate → Run is one **Run** action and a status
  line; the duplicated column is gone; the draft lifecycle is real for the first time.
- **Phase 3b — the builder's surfaces.** Click a port and get what fits, ranked by the resolver's
  own key; a browse overlay instead of a palette; swap that computes its consequences; the
  artifact as the canvas's second view.

**`make verify` green at 1655; `make check` green at 1686 with a database up. Frontend: 280 tests
in 51 files, `tsc` clean, lint unchanged at its five pre-existing warnings.** (The count moved
from 284 to 280 because `Walk.test.tsx` was deleted with `Walk`; its two live assertions moved to
`Status`.)

## The pattern, for the fifth time running

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

## Phase 3a, and the three comments that were true about code that did not run

The 2026-08-29 walk concluded that **the modelling is sound and the surface is not**, and phase
3a is the surface. What it found is a pattern worth naming: **three things had been written down
correctly, in comments, and nothing checked any of them.**

- **`useGraph` has taken a `save` callback since 3E and no caller ever passed one.** The 5-second
  autosave had never fired in production. `useKeep`'s own docstring said so. This is worse than a
  missing feature: the argument for collapsing four buttons into one *Run* is *drafts already
  autosave, so Keep is an implementation detail wearing a button* — and the premise was **false**
  until this phase made it true.
- **`useBuilder` has returned `settling` since 3E**, documented as *only for a quiet indicator*,
  and no surface ever rendered it. That is exactly the marker the walk found missing when the
  verdict described a deleted node for 2–3 seconds.
- **`/build?draft=<id>` was ignored.** `Builder` called `useExample()` unconditionally, so every
  link phase 2 put on the front door — one per row of the *by pipeline* table — opened the
  canonical spine instead of the pipeline you clicked.

**A comment is not a guard.** Each of these was accurate prose beside code that did not do it,
and the repository's habit of writing down *why* is what made them findable in an afternoon —
but only because somebody went looking. `CLAUDE.md` already says a number repeated in prose goes
stale; a *behaviour* described in prose does the same thing more quietly.

### A rename that would have deleted the pipeline

Caught while writing it. `PUT /drafts/{id}` writes `{graph, name}` as one document, and the first
`rename()` sent an empty graph because the hook had none to hand — **saving an empty graph while
appearing to relabel**. No test would have caught it; nobody writes a test asserting that
renaming does not delete.

### `freeSpot` was correct, and deleted anyway

The walk saw two steps land on identical coordinates and `freeSpot` looked guilty. It was not: it
was **guessing** a free cell before `dag-core` had seen the new node. The layout already places
the whole graph without overlap, so `addAt` stopped guessing rather than being handed better
arguments — `useBuilder`'s own header says layout stays in Python *so the canvas is as
deterministic as the emitted `.nf`*, and a client-side placement guess was the one thing on that
screen quietly contradicting it.

### Four more found by looking, at two widths

An empty pipeline reported **100% settled without judgement**. `1 to decide` was rendered twice,
eighteen characters from a status line saying the same thing. The **grid was permanent** —
`impl-geom` calls that the loudest hobby-editor signal there is. And stacked at 900px both panels
kept their desktop widths, leaving a 232px palette with 660px of dead space beside it, because
`Side` sets its width as an *inline* style and an inline style beats a class.

## Phase 3b, and a guard that fired on correct code

The picker is the phase's spine: **click a port, get only what fits, in the order `resolve()`
would consider them.** `GET /api/pipeline/candidates` exposes the `(surplus, -priority, id)` key
that `router.py` has always sorted by, so *the only producer of `alignment.bam[coordinate_sorted]`*
is arithmetic rather than a sentence typed beside an alphabetical list.

**A guard that fired on correct code drew a boundary that had lived only in prose.** The
invariant-15 check — *no control in the builder takes a filesystem path* — caught `Submit.tsx`
asking for one. That is legitimate: the run sheet is where a laboratory supplies **its own** data,
those values go to Wiener as a **run's** parameters, and they never enter the graph or
`pipeline.yml`. Invariant 15 is about what *Mendel* receives. The guard now carries an allowlist
of exactly one file with that reason attached, and the distinction is in the code instead of in
three design documents.

**`useCompatibility.ts` had asked for a guard, in prose, for a week.** Its header warns that a
line parsing a signature in the browser puts the rule in two places, and ends *"A test asserts the
absence."* No test asserted the absence. That is 3a's *three comments that were true about code
that did not run* arriving from the other side: **a comment claiming a guard exists is worse than
one that does not, because it stops the next person looking.**

**A claim of mine was wrong and the operator caught it.** I deferred the canvas's typed input
sockets as *the same class of work as the three-layer arc field*. Checked: the arc field is
decoration with no data behind it, and a socket says **what this pipeline requires of you** from
data already on the client — an input is entry-fed when it is `met` and no wire targets it, which
is a question about *edges*, not types. Ninety lines, no `dag-core` change, no endpoint.

What it replaced was worse than nothing: an entry channel drew a **wire stub running off the left
edge with a clipped label and no terminus**, so the only way to learn what a pipeline needed was
to press Run. And the first render put the sockets at **x = −200**, off-canvas — the same defect
in a better costume — fixed by moving the camera rather than the layout, because an entry channel
is not a node.

**Two more I got backwards, both caught by reading my own words back.** The consuming direction
of the candidates service was sorted so the vaguest match came first, against a docstring written
minutes earlier saying the opposite — found by printing the real registry's answer. And the
builder's grid still declared **five columns for three children**, leaving 335px of dead ground
beside the rail: the CSS fix had been written into a patch script that only opened `Builder.tsx`,
so it silently did nothing. **A `.replace` whose result is never asserted is a `.replace` that may
not have run** — the revert lesson, one layer along.

**`Restored.test.tsx` was restated for the third time.** It exists so four things the plan cut and
the operator put back cannot vanish quietly, and three of the four were about the left palette.
The overlay answers each better — every role rather than `roles[0]`, search, keyboard-first, the
type signature as the description — so the reversal is written **into the test that held them**,
with what each was protecting and where it lives now.

## What is next

**Phase 4 — the runs projections**: `series(state)` pure in `wiener-core`, attempt windows and
per-attempt resources projected. Then **phase 5**, the runs screens.

**What Plan 4 has not done, named rather than absorbed:**

- **The three-layer arc field** — decorative ambience, and the one canvas item still unbuilt.
  It was deferred alongside the typed input sockets on the claim that they were the same class of
  work. **They were not**: the sockets carried information a person needs and their data was
  already in the browser, so they are built. Sizing two things as equal because both were
  "not built" is a mistake worth remembering.
- **Two known tensions from phase 0**: `breathe` and `animate-pulse` are a sixth and seventh
  movement, and retiring either is a visible change to a screen phase 5 owns.
- **"Changed underneath you"** on the Overview, and the **resource sentence**, which needs the
  same projection phase 4 does.
- **Nothing in the builder has been driven by hand in a live stack.** The shell was rendered
  against fixtures and read — which found seven defects across 3a and 3b that green suites did
  not — but the picker, the overlay, swap and the artifact view have component tests and no
  browser pass, and a real keep, gate and run are unexercised.

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

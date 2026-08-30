# 2026-08-30 — the floor, the results, the front door, the builder, and the runs

**Read this first if you are picking the project up. This is the newest entry.** It covers seven
phases of Plan 4 executed in one day, on `worktree-plan-4-phase-0`.

The redesign of 2026-08-29 produced a canvas and nothing else — *"nothing in `packages/` or
`frontend/` changed in this session"*. This is the session where it started becoming code.

## Where things stand

**Plan 4 phases 0, 1, 2, 3a, 3b, 4 and 5 are complete.** The plans are in
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
- **Phase 4 — what a run cost.** A pure `series()` in `wiener-core` that draws only what the
  record can honestly support, one endpoint over the projection rather than the event stream,
  and the retry escalation finally readable.
- **Phase 5 — the runs screens.** The envelope drawn as the step function it is, the 36 → 48 →
  72 GB escalation on the failure banner, and `vs usual` on a board row where the median had
  been fetched and drawn nowhere since phase 2.

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

## Phase 4, and the guard that passed while proving nothing

Phase 4 has no pixels in it. It is three things the runs screens need and cannot compute for
themselves: a curve, an endpoint, and a retry history.

**`wiener_core/series.py` is a fourth pure module and it enforces one rule.** A scalar becomes an
honest curve or it does not, and which depends on **how it distributes over its window**. Wiener
has no samples — the trace gives one summary row per attempt — so everything is derived from task
windows, and there are three branches:

1. **A reservation is constant over its window → the series is exact.** `cpus` and `memory_bytes`
   are what Nextflow *held* for the whole task lifetime, so summing them over live attempts is
   the true reservation curve. Not synthetic at all. Same for anything countable.
2. **A total divides over its window → area-true, shape-false.** `read_bytes` is a total.
   Spreading it uniformly preserves the integral and **invents the shape**. Drawable, stepped,
   and labelled `derived` — smoothness is the visual grammar of *I measured this*.
3. **A peak does not distribute → it is a bound, not a series.** `peak_rss_bytes` is the highest
   value a task ever touched; summing peaks across live attempts describes an instant that never
   happened.

**`Kind` has two members and there is no third.** That is the design, not an omission: there is
nowhere in the type to put a curve whose shape cannot be trusted, which is stronger than a
comment asking nobody to try. It is also the tempting one — memory-over-time is the chart
everybody asks for, and every dashboard in this space draws it.

**Boundaries, not bins.** `+delta` at the start of an interval, `−delta` at its end, sort,
prefix-sum. Exact at every breakpoint, no bucketing artefacts, and 5,000 tasks is 10,000 events
rather than a scan per bin. `bin_ms` ships as a *suggestion for the renderer*, sized off the run's
own recorded span — a 40-second stub run gets sub-second bins where a constant picked for a
four-hour job would collapse it to one point.

**No clock, and it is load-bearing here.** *How long has this been running* is a question about
now, which makes a series the most tempting place in a pure package to read one. The window ends
at the last **recorded** boundary. A running attempt keeps its reservation to the right edge —
closing open intervals at a clock made the *exact* curve fall to zero at the edge, which is the
precise artefact the derived curve is hatched to avoid, arriving on the half that is supposed to
be trustworthy.

### The guard that passed while proving nothing

`test_the_series_never_folds_the_event_stream` patches `projection.state_of` to raise, then asks
the endpoint for a series. It exists because **both implementations return the same numbers** —
a route that quietly replayed 15,000 events would be green on every other assertion in the file.

It **passed against a route reverted to fold.** `runs.py` does `from …projection import state_of`,
so patching the attribute on the `projection` module binds past the name the route actually calls.
That gotcha has its own bullet in `CLAUDE.md` and its own explanatory comment in this
repository's conftest, and it still landed.

The part worth carrying is not the gotcha. **The revert was verified** — the folding line was
confirmed present inside `run_series` by slicing the function with `awk` and counting, which is
exactly the discipline added to this ledger after a `.replace` silently did nothing. Landing a
revert and watching a guard fail are **two different checks**, and only the first had a habit
behind it. A verified revert with a green guard is a finding; the run that says *passed* there is
the whole reason for doing it. Both spellings are patched now.

### The escalation was in the record and out of everyone's reach

`TaskOut.attempts` is a count, and a count cannot show **36 → 48 → 72 GB**. A retry that asked
for more memory is the entire reason retries are kept as history (§5.1), and it was sitting in a
JSON column that nothing projected. `history: list[AttemptOut]` exposes it, with what each try
**asked for** beside what it **touched** — `peak_rss_bytes` alone says a task reached 47 GB and
leaves *was that a lot?* to the reader.

It ships on single-attempt tasks too. Even one try carries asked-beside-touched, which no other
field on the row does, so dropping it for unretried tasks would make the common row the one that
cannot answer the question.

**And no verdict.** `137` is glossed as `SIGKILL` — the 128+n convention, arithmetic — and stops
there. *The OOM killer did it* is an inference: a preemption, a `kill -9` and a cgroup limit are
the same code, and §18.1 says nothing explains a failure until W3. `wiener_core/signals.py` holds
that line with a scan rather than with discipline, and the scan was watched rejecting the exact
sentence somebody will one day want to add.

**The first version of that scan forbade the word `because`** and caught the docstring explaining
the design it exists to protect. A scan broad enough to fire on its own rationale is a scan that
gets deleted rather than obeyed; it now names failure causes specifically.

## Phase 5, and a scan that had to be told what it may quote

Phase 4 decided *which* curves are honest and labelled them. Phase 5 is where that labelling
survives a renderer, and the failure mode is one word in somebody else's library:
**`curveMonotoneX` turns an area-true, shape-false curve into a picture of measurements nobody
took**, with no effect on the data and no test to notice. `curve.ts` builds the path and
`curve.test.ts` refuses a bezier command.

**The exact curves are steps too, and not as a house style.** A reservation genuinely *is* a step
function: four cpus are held, then twelve, then four. There is no instant at which six were
reserved, and a line sloping between the breakpoints draws one.

**Each curve gets its own y-axis and they share the x-axis.** `cpus`, `bytes` and `bytes/s` have
no shared scale, and the alternatives are a second axis nobody reads or a normalisation that makes
every curve the same height. Stacked rows share the thing that matters — time — so a spike in one
sits directly above a spike in another, which is what the artboard's overlay was for.

### The scan had to be told what it is allowed to quote

The failure banner's *authors no cause* guard first scanned the **whole banner** for cause-words.
The banner renders Nextflow's own `errorReport`, and the fixture for it reads *"an oom-kill event
was detected"* — so the scan fired on the record the panel exists to show.

**Quoting the record is what the banner is for. Authoring that sentence is what it must never
do.** A scan that could not tell those apart would have forced the panel to censor the record to
stay green, which is the opposite of the rule. It now excludes the report element and covers only
the panel's own words.

That is the **second time in two phases a scan fired on the thing it was protecting** — phase 4's
caught the docstring explaining its own design. Both were found by running them and neither by
reading them, and the pattern is worth naming: a scan over prose needs a stated boundary between
what the code *says* and what the code *quotes*.

### Two numbers that were fetched and drawn nowhere

`BoardSummary.by_pipeline` shipped in phase 2 and no row read it. `TaskOut.history` shipped in
phase 4 and no panel read it. **Nothing fails when a correct number is simply not rendered**,
which is the same silence as `--hover` being referenced five times and defined nowhere.

The board's comparison also has a rule the endpoint cannot keep: **a delta needs a finished run.**
`-43% vs usual` under a live bar reads as *it was faster*, the opposite of what it means — a run
43% through its usual duration has not been fast at anything yet. A running row says `of ~38m`,
which is the same number saying something true.

And the failing task's **ask now comes from the attempt**. `Run.tsx` took it from the overview
row under a comment reading *"`TaskOut` has no asked half"* — true until phase 4 — and that row
is a per-process aggregate, so on a task that escalated it reported a ceiling no single attempt
was ever given.

### One panel took the whole page down

Adding the envelope made **six graph tests fail at once**. Three fixtures mock `fetch` with a URL
switch that falls through to a `RunState`, so the new panel read `curves` off a shape that has
none and threw during render — taking the header, the failure banner and every tab with it.

The fixtures were wrong and so was the panel. **There is no error boundary above it**, so it now
answers *nothing to draw* for a shape it does not recognise: a run that is hard to read beats a
run that renders nothing.

## What is next

**The browser pass over everything Plan 4 built** — the builder's four surfaces, the typed
sockets, the envelope, the escalation and the board's comparison. It is the last item on phase 5's
own plan, it is owed since phase 3a, and the operator sequenced it after the phases rather than
between them. **Every session that skipped it found defects later that green suites had waved
through** — seven across 3a and 3b, found by rendering a page and reading it.

Then **"Changed underneath you"**, which is its own phase by the operator's decision.

**What Plan 4 has not done, named rather than absorbed:**

- **The three-layer arc field** — decorative ambience, and the one canvas item still unbuilt.
  It was deferred alongside the typed input sockets on the claim that they were the same class of
  work. **They were not**: the sockets carried information a person needs and their data was
  already in the browser, so they are built. Sizing two things as equal because both were
  "not built" is a mistake worth remembering.
- **Two known tensions from phase 0**: `breathe` and `animate-pulse` are a sixth and seventh
  movement, and retiring either is a visible change to a screen phase 5 owns.
- **"Changed underneath you"** on the Overview, and the **resource sentence** — which is now
  *unblocked*: phase 4 projects reserved-beside-used per attempt, so what it was waiting on
  exists. It needs the lab-wide aggregate, not the per-run one.
- **Nothing in the builder has been driven by hand in a live stack.** The shell was rendered
  against fixtures and read — which found seven defects across 3a and 3b that green suites did
  not — but the picker, the overlay, swap and the artifact view have component tests and no
  browser pass, and a real keep, gate and run are unexercised.

**Deferred, named rather than forgotten:**

- **"Changed underneath you"** — `upgrade --dry-run` per pipeline on a worker schedule, a table
  and an endpoint. Its own phase after the runs screens, by the operator's decision.
- **The resource sentence** on the Overview. Reserved-beside-used per attempt is projected as of
  phase 4, so this is no longer blocked on a projection — it needs the **lab-wide** aggregate
  rather than the per-run one. It does not render, which is the absence rule working.
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
  rendered and read. The Builder and Runs screens still carry that debt, and the operator has
  sequenced one browser pass over all of it after the last phase rather than per phase.
- **"Phase 4 built a chart."** It built no pixels at all — phase 5 drew them. `bin_ms` is a
  suggestion the renderer **still has not taken**: the envelope draws every breakpoint, because a
  real run's point count is small enough to draw whole. If a chart ever bins *first*, the
  exactness the pure layer went to trouble for is gone and no test in either phase would notice.
- **"The envelope shows memory used."** It does not, and it cannot. There is no memory-over-time
  curve at any fidelity — `Kind` has two members and the API offers no third — so the component
  has no way to invent one. What it shows is memory *reserved*, which is exact.

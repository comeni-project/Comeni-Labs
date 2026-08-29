# 2026-08-29 — the screens, redesigned: builder, overview, runs

**Read this first if you are picking the project up. This is the newest entry, and
2026-08-29 has two.** The other one,
[`2026-08-29-walking-the-loop.md`](2026-08-29-walking-the-loop.md), was written earlier the same
day and is the *code* half: a pipeline drawn by hand, run end to end, and the fourteen defects
that walk found. **Read it first.** This entry is the *design* half, and it exists because that
walk's conclusion was that the modelling is sound and the surface is not.

## Where things stand

**Nothing in `packages/` or `frontend/` changed in this session.** This was a design session and
its whole output is a browsable canvas plus the notes on it. If you are here to write code, the
canvas is the spec and this entry is the argument.

- **The canvas**: <https://claude.ai/code/artifact/4f65e748-9758-4f06-9b87-1a8dc5a34b34> — five
  pages: Builder, Overview, Run screen, Themes, Runs. Twenty-four artboards, thirty-eight
  annotations. The annotations along the bottom of each page are **implementation notes written
  for you**, not commentary; they carry the reasoning that would otherwise be re-litigated.
- **The source**: `.design/`, committed. `runs_boards.py` generates every Runs artboard,
  `build_boards.py` every Builder one; `canvas.json` is the layout and the notes; `_prev.py`
  renders any board to a PNG with headless Chrome. Re-seed with the `design` skill's
  `seed-canvas.mjs` and republish to the same URL. **The seeded
  `comeni-visual-directions.html` is gitignored** — it is 3 MB of editor payload and it is
  regenerated, not authored.
- **Still uncommitted from the earlier session**: `Makefile`, `docker-compose.yml`,
  `docker-compose.prod.yml`, `frontend/vite.config.ts`, `tests/test_compose.py`, and the two
  audits plus that journal entry. Those are the walk's fixes and they are real code.
- **`CLAUDE.md`'s journal pointer had gone three entries stale** — it named
  `2026-08-24-wiener-w2.md`. Fixed in the same commit as this entry, and the pointer now carries
  a line saying it drifted, because it is the same failure mode as the counts warned about
  directly beneath it.

## What was designed, and the one thing that made it work

Three surfaces, in the order they were done: the **builder canvas**, the **overview**, and the
**runs screens**. The method was the same each time and it is the transferable part:

> **Plan in text first, then draw, then render the drawing and look at it.**

Rendering caught defects that reading the source did not, every single time. On the Runs boards
alone: an SVG `<rect>` with a CSS `background-image` painted **solid black** (`background-image`
does nothing to an SVG rect — it needs a `<pattern>`); done and running tasks were the **same
colour**, because the first draft coloured a timeline bar by process when the lane already
carries identity; and the *asked* curve **fell to zero at the right edge**, because a running
task's interval was being closed at `now` — the exact artefact the *used* curve is hatched to
avoid, arriving on the half that is supposed to be exact.

`.design/_prev.py` strips the `.dc.html` wrapper and screenshots each board with headless
Chrome. Use it. It is thirty seconds and it is the only reason those three shipped fixed.

**Continuity is structural, not checked.** Every Runs board is generated from one shell and
**one task list**, and the timeline, the envelope and the four tiles are all *computed* from it
by the arithmetic the real page would use. That is a direct response to the first builder set,
where eight hand-written boards disagreed with each other. A number cannot drift from the bar
beside it if neither was typed.

## Decisions made, and why

### Wiener has no time series, and that is a rule with three branches — not a blanket

The claim "no charts are possible" was made and then **corrected**, and the corrected version is
the useful one. Per attempt there is a window `[start_ms, complete_ms]` and a set of scalars.
Whether a scalar becomes an honest curve depends on how it distributes across that window:

1. **A reservation is constant over the window → the series is EXACT.** `cpus` and
   `memory_bytes` are what Nextflow held for the whole task lifetime, so Σ over live tasks is
   the true reservation curve — not synthetic at all. Same for anything countable: tasks in
   flight, queue depth from `submit → start`, completions per minute.
2. **A total divides over the window → area-true, shape-false.** `pct_cpu` is a mean,
   `read_bytes` a total. Spreading uniformly preserves the integral and invents the shape.
   Drawable, **stepped**, labelled derived — smoothness is the visual grammar of *I measured
   this*.
3. **A peak does not distribute at all → it is a bound, not a series.** `peak_rss_bytes` is the
   highest value a task ever touched; summing peaks across live tasks describes an instant that
   never happened. **There is no memory-over-time chart at any fidelity.** This is the tempting
   one and drawing it would be exactly the failure the product claim exists to prevent.

Two implementation consequences: build the curves from **boundaries** (`+delta` at start,
`-delta` at end, sort, prefix-sum — exact at every breakpoint, no bin artefacts, 5,000 tasks is
10,000 events; bin only to render, and size the bin off run duration or a 40-second stub run
collapses to one point); and `series(state) -> Series` belongs in **`wiener-core`** — pure, no
clock, the same shape as `overview()` and `spans()`, and it inherits invariant 1 for free.

**Sampling was considered and rejected.** The worker holds the host Docker socket and could poll
cgroups for genuinely measured curves. It only works for the local executor, so the panel would
exist on some runs and not others — and a chart that appears conditionally is worse than one
that never appears. Revisit at W5 if at all.

### An absent series is a reason to draw a DIFFERENT panel, not an empty one

The first answer to *what does the envelope show before any task completes* was a hatched empty
box with a label. That is a placeholder somebody stares at for a minute, and it was rejected.

Until a task ends there is no *used* series at all — but the reservation is exact and live. So
the panel is not a two-curve chart with one curve missing: it is **`cpu reserved`**, one full
curve, and it gains its second curve *and its second name* at the first completion. Generalise
this. `RunEarly` is the whole state 41 seconds in, and it exists as a board because the state
that breaks every dashboard is the one where every number would read zero.

### The failure panel shows the failure and does not explain it

The first version wrote a paragraph naming the OOM killer and tabulated three attempts
escalating 36 → 48 → 72 GB. **Both were wrong, and for different reasons.** This was found by
reading `Failure.tsx`, `TaskTrace`, `RunManifest` and `Run.tsx` rather than by argument.

- **`errorReport` is on `RunManifest`, so it is RUN-level — one per run, not per attempt.**
  `Run.tsx` finds it by scanning the event stream for the first `manifest.report`.
- **`TaskOut.attempts` is a COUNT, not a history.** The per-attempt `memory_bytes` and
  `peak_rss_bytes` do exist, inside `run_task.attempts`, and are not projected. Projecting them
  is what unlocks the escalation panel — and it is a **deterministic** panel when it comes, not
  an AI one.
- **The paragraph was the worse error.** `Failure.tsx` says on its own face *"from the record ·
  nothing interpreted"*, and `wiener.md` §18.1 says nothing explains a failure until W3. So the
  panel shows `exited 137` with a `sigkill` chip — 128+9 is POSIX arithmetic — the peak-against-
  asked bar, and Nextflow's own `errorReport` in a scrolling `<pre>`. **SIGKILL is a fact; "the
  OOM killer did it" is an inference**, usually right and still an inference, since a scheduler
  or a person can send SIGKILL too. The reader draws it.
- The bar draws **only when both halves are known**. Half a comparison is worse than none: a
  bare `71.4 GB` invites the reader to supply a ceiling they do not have.
- A run can fail with **no failed task** — a bad parameter, an unreadable channel. `process` is
  nullable and the panel still says what the record has.

### The board is for a researcher, not an administrator

The first `/runs` led with four 14-day tiles: runs, failed, median, p95. Those describe the
*instance*. A researcher asks four different questions, so the bands are now **running now ·
needs you · finished recently · every run**.

Overlapping the main overview is fine and expected — this is the same question at more depth,
and the operator said so explicitly.

**`median duration` earned its place only by moving onto a row.** A median in the abstract is
trivia; the same median beside a run is a judgement — *usually 38m* under a live bar, *+3% vs
usual* on a finished one. It is the most useful number on the board. And **a delta needs a
finished run**: `-43% vs usual` on a run still going reads as *it was faster*, which is the
opposite of what it means, so a running row says `of ~38m` instead.

**`needs you` only exists when it has something in it.** A card reading *nothing needs you*
trains people to stop looking at the place things appear. Same absence rule as the overview.

### The console is writable, and it is a palette rather than a terminal

`wiener.md` §11, drawn. Five verbs — `cancel`, `relaunch`, `retry task N`, `pause`, `apply` —
and the load-bearing property is the design's own: **there is no code path from that box to a
shell, and adding one means adding a verb, visibly, in a diff.** That is what makes the audit
finite; a reviewer checks a list of five, not a sanitiser.

Two things fell out of drawing it. **The offered verbs are the run's phase** — `cancel` and
`pause` only while it runs, `relaunch` and `retry` only once terminal — and a greyed verb states
its reason rather than vanishing, so the vocabulary is learnable from one screen. And **you
confirm the Intent, not the string you typed**: the preview shows the typed `Intent`, its
`because`, that it needs a named human, and the audit row it will write.

### The AI monitor is DEFERRED, and three things were settled anyway

Decided by the operator this session: too much for the MVP. `wiener.md` §10 stays the design and
**none of it is built** — `AiBrief`, `Redactor`, `PassThrough` and the signature set on
`RunState` are all absent, and `ai-core` (§3.2's rename of `mendel-ai`) does not exist.

`RunMonitor` is on the canvas, labelled *not in the MVP* on its face, drawn so the shape is
settled. **The layout must not hold a hole for it** — no reserved width, no empty column, no
disabled button. The page narrows when the rail arrives.

Three things were settled while deferring, so they are not re-argued:

- **It is NOT a fifth Mendel door.** Mendel's four track the *prompt* taint path, and invariant
  15 says Mendel never receives patient data. Wiener does — `trace.name`, `tag`, `workdir` and
  `script` are `LabString`. That is a different boundary with a different threat, and it needs
  **its own guard in `wiener-core`**, beside the purity one, never an entry in `DOORS`.
  Filing it in `DOORS` would conflate two boundaries and weaken both.
- **Automatic briefs always run redacted.** §10.3's table says `guarded` shows the payload and
  waits for confirmation — but three of the four triggers have **no human present**. Only a
  human ask may release lab strings, after a preview. Automation is then never the thing that
  leaks, which is the honest reading of what `guarded` is for.
- **The console tail never crosses.** `AiBrief` has no field that can hold one, on purpose — the
  budget is a type, not a discipline. So *explain this failure* explains from the signature, the
  resources and `errorReport`, never from the log.

One thing the deferral surfaced that §10 does not cover: **an ETA question needs the process
table, not one task.** So `ASKED` carries the `Overview` rows — still typed, still no lab
strings, since process names come from the artifact — and the answer must name what it has no
basis for. A step that has never run in this pipeline has no history to average.

### Motion and responsiveness, written down and partly baked

Both were *implemented* in the boards and never *stated*, which is how they go stale. The rules
are on all three pages; the reference CSS is baked into the Runs boards' `<style>` block. Lift
it rather than re-deriving it.

**Five movements, one curve** (`cubic-bezier(.32,.72,0,1)`), and the rules that are easy to get
wrong: `grow-x` is **first paint only** (a bar that redraws every poll is unreadable — key on
identity, not value); `settle` staggering **caps at ~8** (a 400-row table at 30ms takes twelve
seconds); `flow` belongs to the running bar and **nothing else**, or it stops meaning *now*;
`lift` is a **contract** — if it lifts it is clickable and if it is clickable it lifts. And
**numbers never tween**: a counter rolling toward its value is illegible exactly when somebody
is reading it, and on a live page it never settles.

**Responsiveness is three rules.** Every band is `auto-fit minmax()`, never a fixed column
count, and **nothing is ever dropped to fit** — a missing panel is indistinguishable from a
panel with nothing to say. `.tbl { overflow-x:auto }` with a `min-width` on the row is the only
horizontal scrolling allowed anywhere; the page body never scrolls sideways. The charts are
already fluid, since every SVG is `width:100%` on a viewBox — what is not fluid is the lane
label gutter, shrunk in exactly one place. Breakpoints are **1180 and 760, chosen from content**:
1180 is where a rail stops fitting beside the page. A side rail **stacks, it does not overlay** —
a drawer hides the thing it is discussing. **A phone is not designed for**, deliberately.

## What is next

**The rework starts from the canvas, in this order.** The order is the operator's and the
reasoning is that each one is a prerequisite for judging the next:

1. **The builder**, because the walk found its defects are all *feedback* defects and the canvas
   already says what the feedback should be.
2. **The overview**, which is the smallest of the three.
3. **The runs screens**, which need the most backend work below.

**The forge stays deferred.** It is still carried as needing testing and rework and nothing in
this session touches it.

## What the runs screens need from the backend

Named here rather than discovered during implementation:

- **`submitted_by` is hardcoded `"operator"` at submit.** The board's `who` filter and any
  person column are decoration over a constant. Wire it or leave the column out — do not ship a
  filter that filters nothing. There is no *mine* filter on the board for this reason.
- **`publishDir` is emitted nowhere**, so a finished run still cannot link to its outputs. Third
  screen this has blocked. Ship *Results* after it, not a half-working version.
- **Attempt windows are not projected.** The timeline and the envelope need `start_ms` /
  `complete_ms` per attempt; they are inside `run_task.attempts` and `/runs/{id}/tasks` pages at
  100. Either three derived columns or a dedicated `/series` endpoint over the pure function —
  **not a fold in the request**, per A191's rule that a board is a query.
- **Per-attempt resources are not projected either**, which is what the failure escalation panel
  waits on.
- **Duration-by-pipeline needs a `GROUP BY artifact_id`** the repository does not have. This is
  what feeds *vs usual*, so it is not optional decoration — it is the board's best number.
- **Performance.** The 2026-08-19 audit found every registry-touching screen cost ~250ms warm.
  Nothing on these boards may resolve anything.

## What a fresh reader gets wrong

- **"The canvas is a mockup, so the numbers are made up."** The layout is a mockup; the
  *arithmetic* is not. Every chart on the Runs page is computed from one declared task list by
  the same boundary sweep the real page should use. If a bar looks wrong, the arithmetic is
  wrong, and it is in `.design/runs_boards.py` where you can read it.
- **"The monitor was cut, so §10 is dead."** It was deferred, not rejected, and three of its
  open questions were closed on the way past. Re-read the `rn-ai` note before re-opening any of
  them.
- **"`RunGraph` is missing."** It was deleted deliberately. Table and graph were two artboards
  of one screen, which is two chances to drift; `RunView` carries both behind a real toggle.
- **"The failure panel is thin."** It is exactly as thick as the record allows. The richer
  version is blocked on a projection, and it is named above.

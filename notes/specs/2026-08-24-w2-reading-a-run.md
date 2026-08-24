# W2 — reading a run without reading text

**Status: spec, 2026-08-24.** Written after W1 shipped and the courier landed, against the types
that exist rather than the ones a plan predicted. It absorbs the interim decisions file
(`2026-08-24-w2-design-decisions.md`, deleted in the same commit) so that two documents cannot
disagree later — which is what A71 and A72 are about.

The screens are drawn: [`docs/design/w2-mockups/`](../../docs/design/w2-mockups/), nine artboards,
each with the argument for it on a note beside it.

---

## 0. Why this document exists

**A bare `§` in this document is `docs/design/wiener.md`'s**, which is the numbering every other Wiener note uses. This document's own sections are named as *this spec's* §n where they are referenced at all.

`docs/design/wiener.md` §18 gives W2 one line and one ending condition:

> The console and dashboard properly: WS with a reconnect offset, the page-then-tail handoff, the
> expandable top panel, the task table, attempts visible — designed against telemetry read since
> W1. **Ends on: you can read a 400-task run without reading text.**

**Two of the five named items are already built**, which is the first thing reading the code
rather than the plan turned up. What is left is the ending condition, and the ending condition is
a statement that *the console cannot be the answer*. Today it is the only answer.

## 1. What W1 actually left

Measured on 2026-08-24, not assumed.

| named in §18 | state |
|---|---|
| WS with a reconnect offset | **done** — `useRunStream` reconnects, and re-*pages* rather than reopening blind, because the tail is capped |
| the page-then-tail handoff | **done** — §7.2's ordering subtlety has one implementation, in the hook |
| the expandable top panel | a counts strip and a `More` button over `Stats.tsx` |
| the task table | **absent** — nothing renders a task |
| attempts visible | **absent** — `NodeRun.attempts` exists and only the graph draws it |

**Two defects were found while reading, and both belong to W2 rather than to a bug list.**

- **`useRunStream` pages once.** It asks `/events?after=-1` with the default `limit=200`, takes
  that page, and subscribes. Reload mid-run on anything bigger and you silently get the first 200
  events and a hole between them and now. It has never been noticed because the largest real run
  is five tasks.
- **`--hover` is defined nowhere.** `hover:bg-[var(--hover)]` appears five times in
  `frontend/src/build/` — `Compare.tsx` twice, `Findings.tsx`, `Builder.tsx` twice — and the
  custom property exists in neither `tokens.css`, nor `main.css`, nor `dashboard.md` §2. Five
  hover states are dead CSS. It is most of why the builder feels inert.

## 2. The research this rests on

General practice, not any one product's.

| principle | what it means here |
|---|---|
| **overview first, zoom and filter, details on demand** (Shneiderman) | the console starts at *details*: a line per event is the last rung shown first |
| **summarisation and exception** (Few) | a display's two jobs; 400 equal rows do neither |
| **position and length encode quantity; hue encodes category** (preattentive research) | `9 / 12` as text is not preattentive; a bar is |
| **data-ink, small multiples, sparklines** (Tufte) | 400 tasks is exactly the case for word-sized graphics, one row per *process* |
| **RED / USE** | a run is a resource, not a service — §9.3's four comparisons already *are* utilisation and saturation |
| **uncertainty amplifies waiting** (NN/g) | prefer a determinate indicator wherever one is computable — §5 is about which one honestly is |
| **a dense table's row hover must be light** | a loud hover flickers as the cursor moves |
| **hover-only affordances go unfound** | so nothing is reachable only by hover, and nothing only by right-click |
| **derive a step's status from state, never an index** | `draftId`, `moved`, `gate.passed`, `artifact`, `runId` are that state |

---

## 3. The run page

Route `/runs/:id`, **full width** rather than `max-w-4xl`, because seven columns need it.

```
← Board                                                        ↩ pipeline
run 85bbe6a0                                    ● running          7m12s
─────────────────────────────────────────────────────────────────────────
 3 of 5 steps finished     ▓▓▓▓▓▓░░░░     declared by the artifact
─────────────────────────────────────────────────────────────────────────
[ Overview ]   Console   Graph   Tasks              following · read-only until W4
```

`↩ pipeline` renders only when the builder handed over — it passes `?from=<draftId>`. **The
browser carries that continuity and neither API learns the other exists**, which is the courier's
argument (`wiener.md` §12) applied to a link. A run someone sent you simply has no back-link.

The active view lives in the URL (`useUrlState("view")`, already there), so a link to a failing
graph stays pasteable.

## 4. The overview

**One row per process the *artifact declares*** — which is why `MULTIQC` has a row before the run
reaches it, and why the table's length is known before the first event arrives.

| column | encodes |
|---|---|
| process | name, plus `↻n` when any task of it retried |
| tasks | `12 done`, and `9 more seen` when the process is live |
| progress | length: done over tasks seen |
| memory peak / asked | length: `peak_rss` over `memory`, on a 0–100% scale |
| cpu used / asked | length: `%cpu` over `cpus`, on a 0–100% scale |
| worst realtime | length: this process's worst over the run's worst |
| read / written | length: this process's total over the run's largest |

Four rules, each of which is a test in this spec's §15:

- **Length encodes quantity, on an identical scale down each column.** That is what makes a
  column a small multiple rather than seven unrelated bars, and comparison is the entire reason
  the numbers are worth putting in a row at all.
- **Absence is `—`, never `0%`.** A run launched without `trace.enabled` reports nothing, and a
  zero reads as *this process used no memory* — a lie about a real number that a reader cannot
  distinguish from a true one. `ProcessStats` already returns `None` for exactly this reason; the
  UI must not undo it.
- **No total is claimed while a process is live.** §5.
- **Attempts are on the row**, not discovered by expanding.

### 4.1 Every comparison, every row — and why not exception-only

The recommendation was to show a comparison **only when it had something to say** — a peak above
~80% of the ceiling, a cpu below ~25% of what was asked. The operator rejected it and the argument
is the better one: **an exception threshold at 80% is a magic number nobody sourced**, and this
project refuses an unsourced value everywhere else. A value without a `why:` is a refused build.
Hiding a comparison behind a threshold the interface invented is the same fault wearing a UI
costume, and for a scientific tool the reader decides what is anomalous.

## 5. The only honest denominator is the artifact's

**Nextflow does not know how many tasks a process will have.** Tasks appear as channels emit, so
a task-level denominator is *discovered* and grows. A percentage over it is a number nobody can
source — the same fault §9.2 refuses when it forbids a rate on a live edge.

What *is* declared is the pipeline's steps, before the run starts.

- The run bar is **steps finished of steps declared**: honest at t=0, monotonic, and sourced from
  `pipeline.yml`.
- Per-process counts are **absolute** — `12 done`, `9 more seen` — and the row's bar fills against
  tasks *seen*, which is a fact about what has been reported rather than a claim about what is
  coming.

## 6. Tasks — two places, one component

**Expanding a process row** answers *what did this process do*; **the Tasks tab** answers *what
across the whole run retried*. Different questions, each cheap alone.

The cost is two renderings of a task row, and it is paid by **one `TaskRow` component with two
callers** — the same shape as `dag-core` serving both canvases. A test holds the importer count.

A task row carries: tag, attempt, exit code, memory, cpu, realtime, and a mark (`worst`,
`↻ retried once`, `killed — out of memory`). Every field is on `Attempt`, which already keeps all
fifteen trace fields per attempt.

The Tasks tab filters by process, status and attempt, sorts by any column, and is **paged and
filtered server-side** — 5,000 rows is not an overview.

## 7. The console — kept, and no longer the front door

It stays, and it gains a job it does not have: **opened from a process, it arrives filtered to
that process.** That is the zoom-and-filter rung, and it is where the overview's right-click
`open in console` lands.

Nothing about its rows changes. It is virtualised (this spec's §11).

## 8. The graph

Unchanged in kind — `dag_core.of(graph_of(pipeline))` laid out, `coloured(pipeline, layout,
state)` joined on. §9.2's rule stands untouched: a live edge means *this edge is active* and
carries no rate; a finished edge may carry its real weight.

What is new is the **canvas menu** (this spec's §12.3), and one item on it is worth arguing for.

## 9. Failure

A banner above the overview, rendered only when the phase is `failed`, assembled entirely from
the record:

- which process, which task tag, the exit code, the attempt — `TaskState.latest_exit` and
  `Attempt`;
- a resource line **only when both halves are known**: *peaked at 63.8 of 64 GB asked*;
- **Nextflow's own `errorReport`** — `RunManifest.report`, which `admit()` already keeps and
  nothing renders.

The failed process is expanded beneath it, with its sibling tasks, because **the comparison is the
diagnosis**: one task at 63.8 GB beside eleven at 58 says something a single number cannot.

`report` is a `LabString`. It reaches this browser and **must never become a span attribute** —
§8 already forbids it and a test already holds it. Nothing here weakens that.

**This shows the failure and does not explain it.** §18.1's *"nothing explains it until W3"* stays
true, and that is a boundary rather than a shortfall.

---

## 10. The projection — one, and `stats()` is it

`wiener_core.stats.stats(state)` is already the per-process projection: pure, folded from
`RunState`, worst-case kept, `None` where nothing was reported. W2 **grows it** rather than adding
a second one.

```python
def overview(state: RunState, pipeline) -> Overview: ...
```

It takes a `Pipeline` for the same reason `graph.coloured` already does — so it can name the
processes the artifact declares and the run has not reached.

`ProcessRow` = today's `ProcessStats` plus:

| field | from |
|---|---|
| `declared: bool` | the artifact's steps |
| `reached: bool` | whether any task of it has been seen |
| `done` · `running` · `failed` · `cached` | the fold, per process |
| `attempts_max` | the fold — `max(len(task.attempts))` |

`Overview` also carries run-level `steps_declared` and `steps_finished` for §5's bar.

**Rejected — composing in the browser** from `/runs`, `/stats` and `/graph`. `routes/build.py`
settled this argument already: *a judgement made in the browser is one the agent driving this API
cannot reach.* Deciding that `STAR_ALIGN` in the graph and `STAR_ALIGN` in stats are the same row
is such a judgement, and an agent asking Wiener *how is my run* would have to re-derive it. Three
round trips for one screen, and a fourth thing to keep in agreement.

**Rejected — a second `overview()` beside `stats()`.** Two per-process projections that must never
disagree, and no test that can hold it. That is the shape of the bug where `admit()` dropped
fifteen fields and nothing noticed.

### 10.1 The endpoints

| | |
|---|---|
| `GET /api/runs/{id}/overview` | replaces `/stats`, answers the whole page in one request |
| `GET /api/runs/{id}/tasks?process=&status=&attempt=&sort=&after=&limit=` | paged, filtered, sorted server-side |
| `/api/runs/{id}` · `/events` · `/graph` · `/stream` | unchanged |

`/stats` is **renamed rather than kept beside** the new one: its only consumer is `Stats.tsx`,
which the overview replaces.

## 11. Scale

The target is **~5,000 tasks** — a 200-sample cohort through a full pipeline, about 15,000 events.
Everything stays in the browser and the API does not change shape.

### 11.1 Page until drained

The first defect in this spec's §1. `pageThenTail` loops while a full page comes back, then subscribes. It is four
lines and it is the difference between a correct record and a silent hole.

### 11.2 Virtualisation

The console and the Tasks tab are windowed with **`@tanstack/react-virtual`** — same maintainer as
the `@tanstack/react-query` already in the tree, ~3 kB, no styling opinions. **The one new
dependency in W2**, flagged rather than hand-rolled, because a windowing bug is subtle and this
one is somebody else's solved problem.

The overview stays **O(processes)**, so the default view never depends on run size.

---

## 12. Interaction

### 12.1 Two derived tokens, and a defect closed

```css
--hover:        color-mix(in oklab, var(--ink) 5%, transparent);
--hover-strong: color-mix(in oklab, var(--ink) 9%, transparent);
--t:            140ms cubic-bezier(.4, 0, .2, 1);
--ring:         0 0 0 2px var(--paper), 0 0 0 4px var(--pea);
```

**`--hover` adds no hue**: it is `--ink` at 5%, so it tints whatever surface it lands on and
inverts for free in dark mode where `--ink` is light. That is the same argument the Depth tokens
make from `--shadow`. Defining it closes the five dead hover states in this spec's §1.

**`--t` is not a new number** either: it is what Tailwind's `transition-colors` already resolves to
in the seven places the product uses it. Naming it is what lets everything else agree with those
seven rather than each picking its own.

### 12.2 What moves, and what must not

- A **row tints** on hover — light, because a loud hover on a dense table flickers as the cursor
  moves. The caret darkens and nudges 2px.
- **Controls lift**: `--e1 → --e2` on hover, back to `--e1` on press. The elevation ramp finally
  does something dynamic rather than being three static shadows, which is the direction earning
  its choice.
- **Nothing that encodes a quantity moves.** No bar animates, on hover or otherwise. Motion
  implying a number nothing measured is the fault §9.2 refuses on a live edge, and a bar is a
  quantity by construction.
- **Nothing appears on hover.** A first pass revealed `console` and `tasks` chips on a row and the
  operator killed them: they covered the *read / written* column, and they pointed at two of the
  four tabs sitting directly above the table. An affordance that obscures data to reach something
  already one click away is a bad trade.

### 12.3 The right-click vocabulary

Every Wiener surface showing a row, a node or an edge answers a right-click. **A menu on one page
and nowhere else is worse than none**, because it teaches a gesture that then fails.

Two rules govern all of them:

- **Nothing is reachable only by right-click.** Every item duplicates a visible control or is a
  clipboard action, so the discoverability cost does not apply.
- **The browser's own menu survives where it matters** — a text selection, and the failure
  banner's `errorReport` block. Overriding right-click everywhere **steals *Copy* from people**,
  which is a worse bug than having no menu.

W4's verbs appear **listed and dimmed with a `W4` tag** rather than absent: a menu that grows two
new items later is worse than one that always had the shape.

| surface | items |
|---|---|
| **board row** | open · open in a new tab · copy run id · copy a link to this run · copy row as TSV · *cancel* · *relaunch* |
| **process row** | show its tasks · open in console · show in graph · copy process name · copy row as TSV · *retry failed tasks* · *cancel* |
| **task row** | open in console here · copy work directory · copy task hash · copy the command line · *retry this task* |
| **console line** | copy this line · copy the task's work directory · filter to this process · show it in the overview · copy everything **shown** |
| **graph node** | show its tasks · open in console · show it in the table · copy process name · copy the container image · *retry failed tasks* |
| **graph edge** | copy the type it carries · copy the bytes moved — **only once the consumer finished** (§9.2) |
| **graph canvas** | fit to the window · zoom to 100% · **copy the graph as SVG** · save as PNG · show the pipeline it came from |
| **column header** | sort ascending · sort descending · copy the column |

Three of those are judgements rather than obvious:

- **`copy the graph as SVG`** is where a figure leaves the tool for a methods section. It is
  honest to offer *only* because `dag-core`'s layout is deterministic — the same run draws the
  same figure twice, which is the reason that layout lives in Python and not the browser.
- **`copy everything shown`**, not everything. A console filtered to `STAR_ALIGN` that copied all
  412 lines would be lying about what you were looking at.
- **The column menu stops at sort and copy.** Hiding columns is a preference store; the answer to
  a table that is too wide is fewer columns for everyone, not a setting.

### 12.4 Keyboard and reduced motion

- **One `--ring` token**, and every row is tabbable. The product has `focus-visible` in three
  places and no shared ring; a keyboard should reach everything a mouse does.
- **`Shift+F10` fires a `contextmenu` event**, so handling the event covers the key. Keyboard
  parity on the menus is free rather than a second implementation.
- **`prefers-reduced-motion` removes the transition, never the feedback.** The colour still
  changes; it arrives at once, and the lift is dropped. A reduced-motion reader loses the
  animation, not the information.

## 13. The walk — the builder's rail

Not a Wiener screen, and in W2 because the courier made it one journey.

The right panel gains a **vertical rail** above its existing tabs, owning all four steps —
**draw → keep → gate → run**. Gate and Run stop being tabs; the toolbar keeps nothing but the
pipeline name.

- Every status derives from state that already exists — `draftId`, `keptGraph`/`moved`,
  `gate.passed`, `artifact`, `runId` — **never a step index**.
- **The blocked reason is rendered under the step**, not put in a `title`. That is the single
  biggest change: *why can't I* stops requiring a hover. `useKeep.blocked` already composes the
  sentence; it has simply had nowhere visible to go.
- Gate output and submit errors expand in place beneath their step.

**A defect this fixes on the way**: `Gate` and `GatePanel` each call `useGate`, and `GatePanel`
renders a `Gate` inside itself — so the toolbar and the panel were two independent gates until
this session moved the run id into the query cache. The rail removes the duplication entirely.

## 14. Depth lands

§9.5's four tokens — `--e1`, `--e2`, `--e3`, `--well` — go into `frontend/src/tokens.css` and are
applied across **builder, forge, runs and home**. All four derive from `--shadow`; no new hue.

`docs/design/dashboard.md` §2 claims authority over that file, so it changes with it.

Judging *boring and stale* on one screen tells you nothing, which was the whole argument for
making the hypothesis testable.

---

## 15. What a test holds

Each watched failing, per A14.

| guard | what breaking it looks like |
|---|---|
| a process with no traces serialises `null` and renders `—` | it reports `0%` |
| the run bar's denominator comes from the artifact, not from tasks seen | a percentage that goes backwards |
| `TaskRow` has exactly two importers | two task renderings drift |
| 5,000 tasks renders a bounded number of DOM nodes | virtualisation installed but not engaged |
| `overview()` golden tests over the committed weblog corpus | including a no-trace run and a retry |
| the events page loops until drained | a reload mid-run shows 200 events and a hole |
| `--hover` resolves to a colour | the five builder hovers go dead again |
| every right-click surface has a menu, and a text selection does not | `Copy` is stolen |

## 16. What W2 does not do

- **No verbs.** W4. The menus list them dimmed; nothing acts.
- **No AI, no chat panel.** W3, and the right-hand column stays absent rather than stubbed —
  §18.1.
- **No cluster.** `cicd.worker.*` and queue wait stay empty until W5. Build the view, expect zero.
- **No cross-run dashboard in the SPA.** The four boards live in the telemetry backend, which is
  what keeps §9.4's *"this is not a second dashboard"* true.
- **No preference store.** No column hiding, no density switch, no saved filters.
- **Not the builder's canvas menu.** Right-clicking a node to delete, disconnect or pin a producer
  is Mendel's, and this spec's §12.3's shape is written to be borrowed by whoever next opens
  `frontend/src/build/`.

## 17. Costs, stated

- **One new dependency**, `@tanstack/react-virtual`.
- **A breaking API rename**, `/stats` → `/overview`, and the generated client changes with it.
- **A token change touching every screen** — Depth, plus `--hover` and `--ring`.
- **Two renderings of a task row**, paid by one component and held by a test.
- **The overview needs the artifact**, so a run whose artifact cannot be read shows counts and no
  declared rows. `/graph` already has this failure mode and answers 404; the overview must degrade
  rather than 404, because counts are still worth showing.

## 18. Open

- **`MAXLEN ~ 10000`** on the Redis stream is still a guess (`wiener.md` §17). A 5,000-task run makes ~15,000
  events, so a browser that reconnects late will now genuinely fall off the tail and re-page —
  which is the designed behaviour, and the first chance to measure whether the number is right.
- **Sorting the overview.** Rows are in the artifact's declared order, which is the pipeline's
  shape. Whether a reader wants to sort by memory is a question for somebody who has used it for a
  week.

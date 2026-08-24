# W2 — design decisions taken so far

**Status: brainstorming in progress, 2026-08-24.** Three questions were put to the operator and
answered; the approaches and the sectioned design are not written yet. This file exists so the
answers are not lost in a chat log — the same reason `wiener.md` §17 keeps closed questions.

## The research the answers rest on

| principle | source | what it means here |
|---|---|---|
| overview first, zoom and filter, details on demand | Shneiderman's mantra | the console starts at *details*: a line per event is the last rung shown first |
| summarisation and exception | Few, *Information Dashboard Design* | a display's two jobs; today we show 400 equal rows and do neither |
| position and length encode quantity, hue encodes category | preattentive research | `9 / 12` as text is not preattentive; a bar is |
| maximise data-ink, small multiples, sparklines | Tufte | 400 tasks is the case for word-sized graphics, one row per *process* |
| RED / USE | Wilkie, Gregg | a run is a resource, not a service — §9.3's four comparisons already *are* USE |
| uncertainty amplifies waiting | NN/g, Fluent | prefer a determinate indicator wherever one is computable, and one is |
| staged disclosure, one clear next action, a disabled control must say why | multi-step flow guidance | `useKeep.blocked` already carries its reason; the sequence is what is missing |
| derive each step's status from state, never a step index | stepper guidance | `draftId`, `moved`, `gate.passed`, `artifact`, `runId` are that state |

## D1 — the run page opens on a process overview

**One row per process, not per task.** Length-encoded progress, and the console becomes a tab you
open when the overview points at something.

§18's ending condition is *read a 400-task run without reading text*, which is a statement that
the text view cannot be the answer — and today it is the only answer.

## D2 — every comparison, every row

**All four of §9.3's asked-vs-got comparisons on every row**, on identical scales down each
column so processes are comparable by position and length.

**Exception-only was recommended and rejected, and the operator's argument is the better one**: an
exception threshold at 80% is a magic number nobody sourced, and this project refuses an unsourced
value everywhere else. For a scientific tool the reader decides what is anomalous. Hiding a
comparison behind a threshold the interface invented is a `why:`-less value wearing a UI costume.

Two consequences:

- **The run page goes full-width**, like the builder, rather than `max-w-4xl`.
- **Absence is not zero.** A process with no trace data shows `—`, never `0%`.

## D3 — the walk is a rail in the builder's right panel

A vertical stepper owning **draw → keep → gate → run**, replacing the toolbar buttons and the two
separate tabs. Each step's status is derived from state that already exists; **the blocked reason
sits under the step rather than in a `title`**, so *why can't I* is on screen instead of on hover.

Today those four controls live in three places and nothing says they are one sequence — which is
the complaint that produced Plan 3D.

## D4 — tasks appear in two places, from one component

**Expand a process row in place, and a Tasks tab across the whole run.** They answer different
questions — *what did this process do* against *what across the run retried* — and each is cheap
alone. The cost is two renderings of a task row, paid by **one `TaskRow` component with two
callers**, the same shape as `dag-core` serving two canvases.

## D5 — the scale target is ~5,000 tasks

A 200-sample cohort through a full pipeline: ~5,000 tasks, ~15,000 events. The overview stays
O(processes); the Tasks tab and the console are virtualised; the API does not change.

**A defect was found while deciding this**: `useRunStream` pages **once** with `limit=200` and then
tails, so reloading mid-run on anything larger silently shows the first 200 events and nothing
between them and now. Page until drained.

## D6 — progress is process-level, because that is what is declared

**Nextflow does not know how many tasks a process will have** — tasks appear as channels emit, so
a task-level denominator is *discovered* and a percentage over it is a number nobody can source.
That is the same fault §9.2 refuses when it forbids a rate on a live edge.

So: the run bar is **steps finished of steps declared**, sourced from the artifact, honest before
the run starts and monotonic. Per-process counts are **absolute** — `12 done`, `9 more seen` —
and claim no total while the process is live.

## D7 — a failed run opens on a banner, then the overview

Which process, which task, exit code, attempt, the resource line where it is known, and
**Nextflow's own `errorReport`** — which `RunManifest.report` already admits and nothing renders.
The failed process is expanded beneath it.

This **shows** the failure and does not explain it, so §18.1's *"nothing explains it until W3"*
stays true. `report` is a `LabString`: it reaches the browser and must never become a span
attribute (§8).

## D8 — one per-process projection, and `stats()` is it

`wiener_core.stats.stats()` grows a `Pipeline` argument — as `graph()` already takes one — so it
can name processes the artifact declares and the run has not reached, and it carries counts and
attempts beside the four comparisons. One endpoint answers the page.

Rejected: composing in the browser from `/runs`, `/stats` and `/graph`, because
`routes/build.py` already settled that argument — *a judgement made in the browser is one the
agent driving this API cannot reach*. Also rejected: a second `overview()` beside `stats()`, two
projections that must never disagree and no test that can hold it.

## D9 — the Depth tokens land, across every screen

§9.5's four tokens (`--e1`, `--e2`, `--e3`, `--well`), all derived from `--shadow`, no new hue.
Applied to builder, forge and runs — judging *boring and stale* on one screen tells you nothing,
which was the whole argument for making the hypothesis testable.

## D10 — nothing appears on hover; the shortcuts are on right-click

A hover on an overview row does exactly two things: **it tints, and the caret darkens and
nudges**. One timing governs everything — `--t`, 140ms on `cubic-bezier(.4,0,.2,1)`, which is
what Tailwind's `transition-colors` already resolves to in the seven places the product uses it,
so naming it is what lets the rest agree rather than each picking its own.

**A first pass revealed `console` and `tasks` chips on row hover and the operator killed them**,
on two counts that are both right: they **covered the read/written column**, and they pointed at
two of the four tabs sitting directly above the table — an affordance that obscures data to reach
something already one click away.

So the shortcuts moved to a **context menu**, which is where a shortcut belongs. Nothing is
reachable *only* there, so there is no discoverability cost — the research is blunt that
hover-only affordances go unfound, and a right-click that duplicates a visible control is the
opposite of that.

| right-click a **process row** | right-click a **task row** |
|---|---|
| show its tasks · open in console · show in graph | open in console here |
| copy process name · **copy this row as TSV** | copy work directory · task hash · command line |
| *retry the failed tasks* · *cancel this process* — dimmed, tagged W4 | *retry this task* — dimmed, tagged W4 |

Three things this settles:

- **W4's verbs are listed and dimmed rather than absent.** A control that does not exist yet is a
  promise a reader can see, and a menu that grows two new items later is worse than one that
  always had the shape.
- **Copying a row as TSV is not a nicety.** A scientific tool should let you get a number out.
- **Keyboard parity is free.** `Shift+F10` fires a `contextmenu` event, so handling the event
  covers the key; every row is already tabbable, and one `--ring` token gives it a focus state
  the product currently has in three places and no shared form.

Motion is bounded by the same rule as everything else: **nothing that encodes a quantity moves.**
No bar animates on hover — motion implying a number nothing measured is the fault §9.2 refuses
when it forbids a rate on a live edge. `prefers-reduced-motion` removes the *transition* and never
the feedback: the colour still changes, it just arrives at once.

**A defect the pass found**: `hover:bg-[var(--hover)]` appears five times in
`frontend/src/build/` — `Compare.tsx` twice, `Findings.tsx`, `Builder.tsx` twice — and `--hover`
is **defined nowhere**: not `tokens.css`, not `main.css`, not `dashboard.md`. Five hover states in
the builder are dead CSS, which is most of why it feels inert. `--hover` becomes `--ink` at 5%,
tinting whatever surface it lands on and inverting for free in dark mode — the same argument the
Depth tokens make from `--shadow`.

## What is still open

- The sectioned design, presented and not yet approved.
- Which virtualisation to use, and whether it is a new dependency.
- Whether `GET /api/runs/{id}/stats` is renamed or kept beside a new `/overview`.

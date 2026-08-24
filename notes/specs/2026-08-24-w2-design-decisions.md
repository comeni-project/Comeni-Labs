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

## What is still open

- The approaches (2–3, with trade-offs) and the sectioned design.
- Whether the task table is a fourth view or details-on-demand under a process row.
- The scale target: 400 tasks, or an order more.
- Whether §9.5's four Depth tokens land in `frontend/src/tokens.css` as part of this.

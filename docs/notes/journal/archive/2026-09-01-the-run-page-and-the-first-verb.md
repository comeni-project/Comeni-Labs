# The run page, the first verb, and what reading cannot find — Plan 6

*2026-09-01, evening. The third entry for this day. Thirty commits, all on `main`.*

**This is the day's last entry and 2026-09-01 has three**, which a filename sort does not order.
Read them as: [`a-channel-gets-a-name`](2026-09-01-a-channel-gets-a-name.md) (Plan 5B phases 1–3),
[`the-fan-out-and-the-sheet`](2026-09-01-the-fan-out-and-the-sheet.md) (5B phases 4–5, and the
browser pass that followed), then this one.

The plan is
[`../plans/2026-09-01-plan-6-what-the-run-page-still-owes.md`](../plans/2026-09-01-plan-6-what-the-run-page-still-owes.md),
with an execution record under each phase.

---

## What is true now

**`/runs/{id}` is bands, not tabs.** The page was still W2's four-tab screen; the 2026-08-29
redesign replaced tabs with one scrolling pyramid and Plan 4 phase 6 rebuilt the builder against
its artboards without reaching this one. A tab **is** a second page for the same run, which
`page-5` forbids in as many words, and the table/graph pair it names as *"STATE, NOT A SECOND
SCREEN"* were two of the four.

**Band 1 is four panels** — progress, failures, moving, resource fit. `moving` did not exist in
any form: a run with four tasks running and nothing completing for twenty minutes was
indistinguishable from a healthy one on every other reading.

**The timeline exists, and `page-5`'s claim that it was blocked is retired.** That annotation
files it under *"BLOCKED, FAKE, OR NOT YET PROJECTED"* because attempt windows are not projected
as columns — true of the columns and never of the data. `Attempt.start_ms` and `complete_ms`
have been in `run_task.attempts` since W2. `lanes()` is the fourth pure verb beside `overview()`,
`spans()` and `series()`.

**A pipeline's name crosses the courier.** `PipelineDraft.name` has existed since Plan 3E and
`usePipelineDraft`'s own header records that nothing in the browser ever set it. It was never
missing; it was dropped in transit.

**Cancel exists, and W4's door is open.** `wiener.md` §11's closed vocabulary of five verbs, each
a typed `Intent` requiring approval and leaving an audit line. Cancel is first for §11's own
reason — *"the only one that needs no artifact"* — which argues for building the machinery under
the cheapest verb rather than skipping it. `run_intent` is the audit table; `EventKind.CANCELLED`
is Wiener's own event, so a replayed run still reaches `cancelled`.

**The three `read-only until W4` strings came down.** True while nothing could act on a run; a
promise the page was breaking the moment cancel shipped.

---

## The lesson of the day, and it is a method

**I compared the page to its artboard by reading, and reported it as matching. It was not.**

Reading the annotations and the HTML source found six real differences — a wrong colour token, a
duration formatter with no hours, an axis dividing its span into five equal slices, a monospace
title, a header in the wrong order, a missing sparkline. All genuine, all worth fixing.

Then the operator said: *"it's still very different… just please actually compare them visually,
I know you haven't because it's completely different."* Correct on both counts.

`.design/_compare.html` puts both in one viewport — the artboard in one iframe, the live page in
the other, each authored at 1400px and scaled to half the window so they are compared at the
same width. **Four more defects fell out of the first screenshot, and they were the ones that
made the page look wrong:**

- **A panel is translucent.** Every artboard's `.pl` is `background: rgba(12,18,22,.62)` over the
  arc field, so the arcs and scan texture read *through* the bands. `--surface` is opaque, which
  turned every band into a card floating on a backdrop. `--line` already matched at `#172025`
  exactly — which is why nothing in the tokens looked wrong.
- **The envelope drew at half width.** `width="100%"` over a fixed 620-wide viewBox, so the
  default `xMidYMid meet` scaled the drawing to fit the 54px *height* and centred it. Nothing in
  the code says 620px; it says *fit*, and fit against a fixed height means do not use the width.
- **Band headers had a chrome fill the artboards do not have.** `.pl > .hd` is a bottom rule and
  nothing else.
- **The timeline was squashed into ~40px for five lanes**, where the artboard's chart is
  `0 0 1230 182` with a 132px label gutter.

And after that, three more the operator pointed at directly: a header shelf neither artboard has
(under a comment claiming *every run screen* has one), a task grid whose `1fr` was in the wrong
place, and a graph 404 that was a seeding bug.

> **The general form: reading finds wrong strings; it does not find wrong pictures.** Every one
> of the second set was invisible in the markup, where a shelf and a rule are both one line, and
> `bg-surface` and `bg-panel` differ by a word. `_compare.html` is committed because this
> session proved the tool is needed.

---

## What was found by guards, and by breaking things

**Watching the recycled-pid guard fail terminated the test runner.** With the start-time check
removed, `test_a_recycled_pid_is_never_signalled` sent `SIGTERM` to `os.getpid()` — pytest
itself. A pid is not an identity; they are reused, and that check is what stands between this
verb and a stranger's process.

**Three guards caught me during execution and all three were right:**

- `test_the_tables_are_the_four_that_argued_for_themselves` refused `run_intent` until §7.1
  carried a prose argument for it beside `run_message`'s. The argument was written first and the
  guard widened after — never the other order.
- `test_every_operation_is_named_by_hand` refused two new routes until they were named in its
  literal list.
- `reported.test.ts` refused `Cancel.tsx` until the mutation was lifted into a hook that returns
  it. My first instinct was to widen the scan; the house pattern was simply better.

**`IntentKind`, `Intent` and `Reason` already existed** in `wiener_core/policy.py`, with
`OPERATOR_REQUEST` matching §11's `because:` line exactly. The plan's instruction to check before
writing is what avoided a second vocabulary for one idea. **`run_intent` was already in §7.1's
schema listing** too — the design had anticipated both.

---

## What a fresh reader will get wrong

**`make dev` runs the Python APIs from a baked image.** No source mount, no `--reload`, so every
backend change is invisible until `docker compose up -d --build wiener-api`. It cost two rounds
of 404s that were green in tests. Same class as the stale dev registry found this morning: the
running stack not reflecting the source. **Not fixed — recorded**, because it will cost the next
person the same twenty minutes.

**The task grid's `1fr` has now been moved twice and the note says so.** It began on `tag`, which
pushed every figure to the far right; moving it last fixed that and created the opposite fault.
The artboard has both properties at once and neither correction found it.

**Cancel's `who` is not an identity.** It records `"operator"`, which is what this deployment
knows — `WIENER_API_TOKEN` is the only boundary and §12.1's accounts do not exist. §11 says
*approval by a named human*; that is a limit stated rather than dressed up, and `run_intent.who`
must not be read as authentication until something authenticates.

**Three things on the artboard are still not built**, and each is a decision rather than an
oversight: the envelope is five stacked rows where the artboard is one CPU chart with a legend
(it shipped in Plan 4 phase 5 and changing it is a design call); the processes table's columns
differ from the artboard's `state / slowest / retries`; and the nav has no Registry tab,
breadcrumb, ⌘K hint or laboratory name.

---

## What is next

**End-to-end manual testing.** The operator's next step, and this session is the argument for it:
every defect that mattered today was found by a person looking at a screen, and none by a suite
that stayed green throughout. The loop has never been walked by hand since the bands landed.

**Repo cleanup**, then **the forge rework**. The forge has been deprecated since 2026-08-31 —
`make forge-rework` lists everything Plan 5A touched or invalidated, and
`notes/specs/2026-08-19-the-forge-redesigned.md` is the standing spec.

**Comeni Code is a separate repository and is not built here.** Design work on it starts next;
nothing in this repo should grow toward it.

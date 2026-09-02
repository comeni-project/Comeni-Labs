# Plan 4 Phase 0 — the shared floor

> **For agentic workers:** REQUIRED SUB-SKILL: use `superpowers:executing-plans`, driven by the
> operator's own session, task by task. **Do NOT use `subagent-driven-development`** — `CLAUDE.md`
> forbids farming out implementation. Tick each `- [ ]` as it completes, and where a step was
> carried out differently, tick it anyway and record the deviation in the execution table.

**Goal:** the three things all three screens need, built once, before any of them is rebuilt —
one motion system, one responsiveness system, and one answer to *a mutation failed*. Plus the
forge leaves the navigation without leaving the router.

**Architecture:** nothing new. The motion and responsiveness rules are **lifted** from
`.design/runs_boards.py`'s `<style>` block, which is the reference implementation the canvas
annotations tell you to lift rather than re-derive. The failed-mutation surface is one component
and one hook, and every `useMutation` in the app routes through it.

**Tech Stack:** React 19 · TypeScript · Tailwind 4 · `@tanstack/react-query` · vitest.

**Design source:** the canvas —
<https://claude.ai/code/artifact/4f65e748-9758-4f06-9b87-1a8dc5a34b34>, annotations `mo-page-1`,
`rs-page-1`, `impl-walk` and `impl-walkbugs`. The generators are in `.design/`; `_prev.py`
renders any board to a PNG and you should use it.
[`../journal/2026-08-29-walking-the-loop.md`](../journal/2026-08-29-walking-the-loop.md) is the
defect list this phase closes the first item of.

## Why this is a phase rather than the first three tasks of the Overview

Because the Overview would otherwise invent all three, and the Builder would re-derive them a
week later. That is exactly how eight hand-drawn artboards came to disagree with each other, and
the fix on the design side — one shell, one task list, everything computed — has a direct
equivalent here: one token file, one motion layer, one error surface.

## Global constraints

- **One curve.** `cubic-bezier(.32,.72,0,1)` everywhere. A second easing curve is a second
  personality, and there are currently **three** in the codebase (see the pre-execution notes).
- **Five movements and nothing else moves.** `settle` · `grow-x` · `flow` · `blink` · `lift`.
- **`prefers-reduced-motion: reduce` kills all five and the transition**, not just the decorative
  ones. The page must be fully legible with every animation off — which is also how it renders in
  a screenshot and a PDF.
- **Numbers never tween.** Elapsed time, task counts and byte figures snap, in `tabular-nums`.
- **`lift` is a contract**: if it lifts it is clickable, and if it is clickable it lifts.
- **Nothing is ever dropped to fit.** A missing panel is indistinguishable from a panel with
  nothing to say.
- **`docs/design/dashboard.md` §2 is authoritative over `tokens.css`.** That file's own header
  says so. Any token this phase adds or changes is edited in **both**, in the same commit — A194
  is the precedent and it is one line of discipline.
- **The frontend gate is `npx tsc -b && npx vitest run && npm run lint`**, run from `frontend/`.
  That is what CI runs. **No task here touches `resolve.py`, `router.py`, `rules/`,
  `mendel_compiler/cli/`, `emit.py` or `artifact/pipeline.py`, so `make verify` is not required**
  — but `make check` still runs, because Task 1 touches the router's tests.
- **No route is deleted.** The forge leaves the navigation and stays in the router.

---

## Pre-execution notes — checked against the code on 2026-08-30

Read these before Task 1. Two of the four change what a task does.

**P0-1 — `tokens.test.ts` is ALREADY the generalised guard.** The canvas annotation `impl-walkbugs`
says *"`tokens.test.ts` greps for it — any new token needs the same guard"*, which reads as though
it greps for `--hover` specifically. It does not: it walks every `.tsx`/`.ts`/`.css` under `src/`,
collects every `var(--name)` including fallback chains, and asserts each is defined in `tokens.css`
or `main.css`. It even carries A67's anti-vacuity check. **So there is nothing to generalise.**
What it does **not** cover is an **animation or utility class** — `class="settle"` referencing a
`@keyframes` nobody wrote is the same silence one layer up, and that is the gap Task 3 fills.

**P0-2 — there are three easing curves, not one.**

| Where | Curve |
|---|---|
| `frontend/src/tokens.css:25` (`--t`) | `cubic-bezier(.4, 0, .2, 1)` |
| `frontend/src/home/Home.tsx:117` (inline Tailwind arbitrary value) | `cubic-bezier(.2,.7,.3,1)` |
| `.design/runs_boards.py`, every board | `cubic-bezier(.32,.72,0,1)` |

Changing `--t` is a **deliberate break with its own stated rationale** — its docstring in both
`tokens.css` and `dashboard.md` §2 argues the value is not new because it is what Tailwind's
`transition-colors` resolves to. That argument is now outranked by *one curve*, and the docstring
must be rewritten rather than left contradicting the value beside it. The `Home.tsx` one is
deleted outright, because Phase 2 rebuilds that page anyway.

**P0-3 — `dashboard.md` §8 Motion is three sentences and describes a different system.** It names
a 45ms node stagger, a 120ms port scale and a 150ms node shadow. The canvas says 30ms capped at
~8, and five named movements. §8 is **replaced**, not appended to, and the replacement says where
the reference implementation lives.

**P0-4 — the Shell's nav has five tabs in two groups**, and the forge owns three of them:
`Forge`, `Queue`, `Tools`. `Builder` and `Runs` are the other two. Removing the forge's three
also removes the separator and the second group, which leaves the nav as two tabs — and
`Shell.tsx`'s docstring argues at length about why nothing in that nav is disabled or absent.
That docstring must be extended rather than silently falsified.

---

## Task 1 — the forge leaves the navigation and stays in the router

**Deliverable:** no forge link is reachable from the frame; every forge URL still resolves.

- [x] Delete the `Forge`, `Queue` and `Tools` `<Tab>`s from `frontend/src/app/Shell.tsx`, and
      the `<span className="w-px h-5 bg-line" />` separator and the second `<div>` that held two
      of them. `Builder` and `Runs` remain.
- [x] Extend `Shell.tsx`'s docstring with a paragraph saying the forge is **hidden, not removed**,
      dated, naming the operator's decision of 2026-08-30 and the reason: the forge is carried as
      needing testing and rework, and a link into a surface nobody is maintaining is a link into a
      surface nobody is maintaining. Say that the routes still resolve and where.
- [x] Add `it("keeps every forge route resolvable after the tabs came out")` to
      `frontend/src/app/router.test.tsx`, rendering `/forge/queue`, `/forge/tools` and
      `/forge/contracts/*` and asserting each mounts rather than hitting the `ErrorBoundary`.
      **Watch it fail** by deleting one route from `routes`, and record the message in
      [`../audits/guard-ledger.md`](../audits/guard-ledger.md).
- [x] Add `it("offers no way into the forge from the frame")` to the same file: render the
      `Shell` and assert no link's `href` starts with `/forge`. **Watch it fail** by restoring one
      tab.
- [x] Leave `frontend/src/forge/` untouched. Nothing in it is deleted in this plan.

**Not in this task:** reparenting the forge under a `Registry` section. The canvas annotation
`ov-blocked` calls for `Builder / Runs / Registry` with the forge inside Registry — but Registry
does not exist, and inventing a section to hold one hidden thing is worse than a nav with two
tabs. Raise it when Registry has a second occupant.

**Verify:** `cd frontend && npx tsc -b && npx vitest run && npm run lint`.

---

## Task 2 — one curve, five movements

**Deliverable:** the motion system exists as tokens and utility classes, and the three curves
become one.

- [x] In `frontend/src/tokens.css`, change `--t` to `140ms cubic-bezier(.32,.72,0,1)` and add
      `--ease: cubic-bezier(.32,.72,0,1)` as the named curve every keyframe uses. **Rewrite the
      comment above it** — the current one argues the value is not new because Tailwind resolves
      to it, and that is no longer why it has the value it has.
- [x] Add the five movements to `frontend/src/main.css` as utility classes with their keyframes,
      lifted from `.design/runs_boards.py`'s `<style>` block (search it for `@keyframes settle`).
      Durations are `settle 200ms` · `grow-x 520ms` · `flow 1.1s` · `blink 1.1s` · `lift 140ms`.
- [x] `settle` staggers at 30ms and **caps at eight items**. Implement the cap where the stagger
      is applied, not as a note: a 400-row table at 30ms takes twelve seconds. The ninth item and
      everything after it appears with no delay.
- [x] `grow-x` is **first paint only**. Whatever applies it must key on **identity, not value** —
      a bar that redraws on every poll is unreadable, and re-running it on every render turns a
      filter change into a light show.
- [x] Add the `prefers-reduced-motion: reduce` block that sets `animation: none` on all five and
      `transition: none` globally. Lift it from the same `<style>` block.
- [x] Add a `tabular-nums` utility and use it nowhere yet. Phases 2, 3 and 5 apply it; declaring
      it here is what stops three different spellings arriving.
- [x] Delete the inline `cubic-bezier(.2,.7,.3,1)` from `frontend/src/home/Home.tsx:117`, replacing
      it with the `settle` class.
- [x] Update `docs/design/dashboard.md` §2's `--t` row and **replace §8 Motion entirely** with the
      five movements, the one curve, the reduced-motion rule, the never-tween rule and the `lift`
      contract. Name `.design/runs_boards.py`'s `<style>` block as the reference implementation.

**Verify:** the frontend gate. `tokens.test.ts` should stay green throughout — if it goes red you
have referenced a property you did not define, which is the guard working.

---

## Task 3 — a class that animates nothing is the same silence as an undefined token

**Deliverable:** a guard that catches a referenced-but-undefined animation class.

- [x] Add `it("defines every motion class the app references")` to
      `frontend/src/tokens.test.ts`: walk `src/` the way `referenced()` already does, collect
      every occurrence of the five movement class names, and assert each has a matching rule in
      `main.css`. Reuse `referenced()`'s walker rather than writing a second one.
- [x] Give it the same anti-vacuity assertion the file's second test already has — a walk that
      reaches nothing must fail rather than pass.
- [x] **Watch it fail**: rename `.settle` in `main.css` to `.settled` and confirm the message
      names the files that reference it. Record the revert in
      [`../audits/guard-ledger.md`](../audits/guard-ledger.md).

**Why this and not more:** the token guard already covers custom properties, and it was written
because an undefined `var()` renders as inherited and looks deliberate. A missing animation class
renders as *nothing moves*, which looks exactly like the reduced-motion path working correctly.
Same failure mode, one layer up, and nothing was watching it.

---

## Task 4 — three responsiveness rules, declared once

**Deliverable:** the layout primitives exist, so no screen invents its own breakpoints.

- [x] Add the two content breakpoints as the only ones any screen may use: **1180** — where a
      rail stops fitting beside the page — and **760** — where a two-up band stops being two-up.
      Declare them in `main.css` as named custom media or as documented Tailwind screens, and say
      in a comment that they are content breakpoints rather than device ones and that a third
      needs a piece of content that demands it.
- [x] Add a `band` utility: `grid-template-columns: repeat(auto-fit, minmax(...))`, **never a
      fixed column count**. Four tiles become two, then one, and nothing is dropped.
- [x] Add a `tbl` utility: `overflow-x: auto` with a `min-width` on the row. **This is the only
      horizontal scrolling allowed anywhere in the product** — the page body never scrolls
      sideways. The heading grid and the row grid must be one declaration, which is what stops
      them drifting apart.
- [x] Add a `withRail` utility that goes to **one column at 1180 with the rail underneath**. A
      side rail stacks; it does not overlay. An overlay drawer hides the thing the rail is
      discussing.
- [x] Add `it("never lets the page body scroll sideways")` — assert `overflow-x` is not `auto` or
      `scroll` on any ancestor the Shell renders, and that `.tbl` is where it lives instead.
- [x] Update `docs/design/dashboard.md` §4 Layout with the three rules and both breakpoints, and
      state that **a phone is deliberately not designed for**: these are desk screens, the rules
      degrade to a tablet, and that is where they stop.

**Verify:** the frontend gate.

---

## Task 5 — every mutation that fails says so

**Deliverable:** one surface, used by every mutation in the app, and it is impossible to add a
silent one without deleting a test.

This is the walk's worst defect and the reason this phase exists.
[`../journal/2026-08-29-walking-the-loop.md`](../journal/2026-08-29-walking-the-loop.md): *Keep*
answered 500, the rail sat there unchanged still offering *Keep*, nothing appeared on screen or
in the console, and the only way to learn that the page's central action had failed was
`docker logs`. Every other item on that list is friction; this one is a lie by omission.

- [x] Write `frontend/src/ui/Failed.tsx` — the surface. It takes an `unknown` error and renders
      what is actually known: the operation's own name in the caller's words, the status if the
      error carries one, and the server's refusal text if there is one. **It never invents a
      cause.** `Refusal.tsx` already exists for typed refusals — read it first and extend it if it
      fits rather than shipping a second component that renders errors.
- [x] Handle `Unauthorized` by deferring to `TokenPrompt` rather than rendering a message: an
      unconfigured Wiener token is a thing a person can fix, and `wiener/Token.tsx` already says
      it appears only when a request has actually been refused.
- [x] Write `frontend/src/api/useReported.ts` — a thin wrapper over `useMutation` that cannot
      return without an error channel. The point is not convenience; it is that the *type* makes
      a silent mutation hard to write.
- [x] Convert every existing mutation to it: `useKeep`, `useGate`, `useSubmit`, `useAnswer`,
      `useAnswerAll`, `useAccept`, `useDecide`, `usePropose`, `useDraft`. Nine hooks. The forge's
      five are converted even though the forge is hidden — leaving them behind is how the wrapper
      becomes optional.
- [x] Add `it("reports a failed mutation rather than sitting there")` for the specific defect:
      render the builder's keep control, make the API answer 500, and assert something on screen
      changes. **Watch it fail against the current code** — restore `useKeep` as it was, confirm
      the test goes red, and record it in [`../audits/guard-ledger.md`](../audits/guard-ledger.md).
      The W2 lesson applies exactly here: a guard that passes on the code it was written to reject
      is a green tick over an open hole, so watch it fail **against this defect**, not merely
      watch it fail.
- [x] Add a repo-level guard: a test that greps `frontend/src/` for `useMutation(` and asserts
      every call site is inside `useReported.ts`. Cheap, and it is what stops the tenth hook.

**Verify:** the frontend gate, and `make check` for the router test from Task 1.

---

## Execution record

**Executed 2026-08-30**, on `worktree-plan-4-phase-0`. 27 of 27 steps. The frontend gate is
green: `tsc -b` clean, **281 tests in 51 files** (from 267 in 50), lint unchanged at its five
pre-existing `only-export-components` warnings. `make check` is green at 1644 passed — nothing in
Python moved.

| Task | Carried out as written? | Deviation |
|---|---|---|
| 1 | Yes, except the gate | The step said `make check`. `router.test.tsx` is a vitest file, so `make check` does not run it — the frontend gate is the gate for the whole phase, and no task here touched Python at all. |
| 2 | No — three conflicts with code the plan had not read | **`flow` was a name collision.** `main.css` already defined `@keyframes flow` as `stroke-dashoffset` for a live wire (`.live`, worn by `runs/Graph.tsx`); the canvas's `flow` is `background-position` on a running bar. Resolved as `flow-stroke` / `flow-bar` — **one concept, two spellings, because an SVG stroke and a DOM background do not animate the same way** — rather than one keyframe silently winning. **`prefers-reduced-motion` already existed** as `.01ms !important` with a written argument for why it removes the transition and not the feedback; kept rather than replaced with the plan's `animation: none`, and it is the better one (an animation that runs still fires `animationend`). **The ambient 46s/680s movement was not added at all** — there is no ambient background in the product, and declaring an unused class is the dead-name defect `main.css` itself records. |
| 2 | Plus one thing the plan did not foresee | **`breathe` is a sixth movement and it was kept**, on a running task dot in `runs/Console.tsx`. By the canvas's own argument it dilutes `flow`; by `main.css`'s it encodes state. Retiring it changes how a screen looks, which this phase forbids itself — so it is documented as a known tension in `dashboard.md` §8 and **phase 5 owns the verdict**, where it is a visible change to the screen it belongs to. |
| 3 | No — the premise was wrong | The plan said `tokens.test.ts` needed generalising from a `--hover` grep. **It has walked every file and every `var()`, fallback chains included, since 2026-08-24.** Nothing to generalise. What was actually missing was the same guard one layer up — a motion *class* whose rule nobody wrote — so that is what shipped. Extended in task 4 to cover the layout utilities, which fail identically. |
| 4 | Partly — one step asked for something the environment cannot do | The step said *assert `overflow-x` is not `auto` or `scroll` on any ancestor the Shell renders*, which is a rendered-DOM claim. **happy-dom has no layout engine**, so a test phrased that way computes nothing and passes — the exact shape the 2026-08-24 ledger entry warns about. Shipped the checkable rule instead: `.tbl` is the only design-system rule declaring `overflow-x`, and `Shell.tsx` declares none. The limit is stated in `dashboard.md` §4 rather than implied. |
| 5 | No — smaller than written, and the finding behind it was wrong twice | **The plan's premise was that hooks swallow errors. None do.** `Failed` already existed in `ui/States.tsx` with six call sites; `useKeep` already returned `error` documented *"Shown, not swallowed"*. The single break was `Builder.tsx` handing `Walk` a `keep` prop with **no error slot** — one call site, one dropped field. So **no `useMutation` wrapper was written**: a wrapper cannot make a consumer read what a hook returns, and it would not have caught this. The fix is a **required prop**, and `tsc` immediately named all three forgetful call sites plus eight fixtures. `Failed` now defers to `Refusal` on a coded message, so one refusal reads the same everywhere. |
| 2 | And the constraint was false in the shipped file | **"One curve" was three in `dist/`, with every test green.** Found in final verification by `npm run build && grep -o 'cubic-bezier([^)]*)' dist/assets/*.css`. Eleven components use `transition-colors` and one `animate-pulse`; each emits Tailwind's own easing, and **nothing in this repository compiles the stylesheet** — not vitest, not tsc — so no test could have been wrong about it. Fixed with two `@theme` overrides rather than twelve call-site rewrites. A source-side guard now holds it and the compiled command is written into `dashboard.md` §8, since it needs a production build. |
| 5 | And a second wrong finding, caught mid-task | An audit-by-grep classified six forge hooks as silent and built an `UNREPORTED` debt list around them. **All six return the `useMutation` result whole**, which carries `.error`, and every forge consumer references one. The list was fiction and would have shipped six files permanently labelled broken. Caught only because a revert written to watch that guard fail **did not apply** — and the guard passed. See the ledger; that miss is recorded at length because it is question 3 of the ledger's own three, answered wrongly for a full cycle. |

## What this phase deliberately does not do

- **It does not touch a screen.** No page is redesigned here. If a screen looks different at the
  end of this phase beyond one easing curve, something was done that was not asked for.
- **It does not build a `Registry` nav section.** See Task 1.
- **It does not delete anything in `frontend/src/forge/`.**
- **It does not add a sixth movement**, however much a particular screen wants one. Raise it.

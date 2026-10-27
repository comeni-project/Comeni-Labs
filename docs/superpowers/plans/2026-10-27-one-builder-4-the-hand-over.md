# One builder, plan 4: the hand-over — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** When a build finishes, the conversation says so with a hand-over (#393): what the
pipeline is, how its values were decided, what still needs you, and what to do next.

**Architecture:** No new block and no model call. The engine already writes a wrap-up receipt
(`walk.wrap`, id `wrap-<seq>`, once per revision). The page draws **the newest wrap-up of a
complete session** as a `HandoverCard`, composed from records it already holds: the decided
steps in order and the goal (`session.history`), the value counts (`valuesOf`, as the header
counts them, #397), the steps with open values (`open`, #385), and the header's Run and
Pipeline file actions. Older wrap-ups stay one line. The engine's own sentence stays under the
card as its record (registry gaps and tools that no longer apply are said there).

**Tech Stack:** React 19, TanStack Query, vitest. No server change.

**Spec:** `docs/superpowers/specs/2026-10-22-one-builder-design.md`, *My calls*: *The hand-over
message (#393) is composed by the engine from its records, no model call: (1) what the
pipeline is — input to output, its steps named in order; (2) how its values were decided —
counts by evidence (#397), each count opening its values; (3) what still needs you, each with a
button that opens it (Run stays locked, #385); (4) what next — Run it, Look at the pipeline
file, or keep asking.* Builds on plan 3 (`one-builder-3`, PR #405).

## Global Constraints

- **Derived, not redeclared:** every part of the card is computed from what the page already
  reads (session, frame steps); no new server field, block kind or stored shape.
- **Engine-composed words, no model call** (`docs/design/voice.md`); counts follow the evidence
  (#397): *measured* only when every premise was measured.
- Run stays locked while a value needs you (#385); the card's *Run it* is the header's action,
  disabled for the same reasons, saying why.
- Frontend traps from plan 3 apply (`tokens.test.ts`, named radii, `Primary` for a main button).

## Review Focus

1. **A wrap-up followed by a correction**: the next wrap-up becomes the card; the older one is a
   line. Test in Task 1.
2. **A complete session with an open value**: part 3 lists the step, *Run it* is disabled with
   the reason, and opening the step from the card opens `StepSheet`. Test in Task 2.
3. **A session that is not complete** (a wrap-up then a new offer): no card. Test in Task 1.

---

### Task 1: Which wrap-up is the hand-over

**Files:**
- Modify: `frontend/src/build/living/format.ts` (add `handoverId`, `stepsInOrder`)
- Test: `frontend/src/build/living/handover.test.ts`

**Interfaces:**
- Produces: `handoverId(session: AuthoringSession): string | null` — the id of the newest
  receipt whose id starts `wrap-`, when `session.phase === "complete"` and no proposal is
  pending; else `null`.
- Produces: `stepsInOrder(session: AuthoringSession): string[]` — accepted step proposals'
  nodes in history order, then graph nodes not among them, sorted.

- [x] **Step 1: Failing tests** — `handoverId` is the newer of two wrap receipts; `null` when
  the phase is `building` or a proposal is pending; `stepsInOrder` returns the history's
  accepted steps in order, then a hand-added node.
- [x] **Step 2: Run** `npx vitest run src/build/living/handover.test.ts` — Expected: FAIL.
- [x] **Step 3: Implement** both in `format.ts`.
- [x] **Step 4: Run** — Expected: PASS.
- [x] **Step 5: Commit** `feat(build): which wrap-up is the hand-over (#393)`

### Task 2: The hand-over card

**Files:**
- Create: `frontend/src/build/living/blocks/HandoverCard.tsx`
- Modify: `frontend/src/build/living/Chat.tsx` (a `render` override for one block id),
  `Stream.tsx`, `ChatPanel.tsx`, `LivingSurface.tsx` (pass `onRun`, `runnable`, `onView`)
- Test: `frontend/src/build/living/HandoverCard.test.tsx`, a `LivingSurface.test.tsx` case

**Interfaces:**
- Consumes: `handoverId`, `stepsInOrder` (Task 1); `valuesOf` (`values.ts`); `open`
  (`useBuilder`).
- Produces: `HandoverCard({ session, steps, summary, runnable, onRun, onView, onSelect })`;
  `Chat` prop `override?: { id: string; node: React.ReactNode }`.

- [x] **Step 1: Failing tests**
  - the card's four parts, in order: **What you built** (`fastq.reads, genome.fasta → counts.matrix`
    and the steps named in order, `→` between them); **How its values were decided** (one count
    per non-zero kind: *settled*, *measured*, *read by AI*, *optional*, *need you*, each a button
    that calls `onView("artifact")`); **What still needs you** (one button per step with open
    values, calling `onSelect(node)`; absent when none); **Next** (*Run it*, *Look at the
    pipeline file*, and *or keep asking below*);
  - *Run it* is disabled with *Answer the values above first* when a value needs you, and calls
    `onRun` otherwise;
  - the engine's sentence (`summary`) is under the card, quiet;
  - in `LivingSurface`, a complete session with two wrap receipts shows one card, for the newer,
    and the older as its line; a building session shows no card.
- [x] **Step 2: Run** — Expected: FAIL.
- [x] **Step 3: Implement** the card (headings at `text-heading`, counts as quiet chips in the
  evidence colours, `Primary` for *Run it*) and the override wiring.
- [x] **Step 4: Run** `npx vitest run` and `npx tsc -b` and `npm run lint` — Expected: PASS, no
  new lint errors.
- [x] **Step 5: Commit** `feat(build): the build ends with a hand-over (#393)`

### Task 3: Docs

**Files:** `docs/reference/pipelines/builder-interface.md` (one row: *Hand-over*),
`CHANGELOG.md` (frontend), `docs/notes/journal/2026-10-27-one-builder-4-the-hand-over.md`;
tick this plan; comment on #393.

- [x] **Step 1:** write them; `make links` and `make doc-sizes` — Expected: exit 0.
- [x] **Step 2: Commit** `docs: one builder plan 4 — the hand-over (#393)`

## Deviations

- None in substance. `LivingSurface` now computes `runnable` once, for the header and the
  hand-over. Under a session's estimate. The browser check of the card waits with plan 3's (#404).

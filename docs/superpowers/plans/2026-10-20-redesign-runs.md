# Redesign 6 — runs Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** The runs board lists runs by pipeline under outcome tabs; a run opens on its failure,
drawn as the board's panel. **Spec:** `docs/superpowers/specs/2026-10-20-redesign-runs-design.md`
**Architecture:** layout changes in `Board.tsx`, `Run.tsx`, `Failure.tsx`; the board adds the
drafts query Home uses. No server change. **Tech Stack:** React 19, Tailwind, Vitest.

## Global Constraints
- No names of people; no relaunch. Named radii; colour by meaning. `npx vitest run && npx tsc -b`.

## Review Focus
- Mendel down on the board: runs still list, pipeline reads *unknown pipeline* — Task 1.
- A failure with no history: no attempt bars, the rest stands — Task 3.
- Phone width: the board table scrolls inside its panel — Task 4.

### Task 1: the board
- [x] Tests in `Board.test.tsx`: tabs and the `phase` query; total on the active tab; pipeline
  names by digest; no executor/submitter text; Mendel failing leaves *unknown pipeline*. Implement. Commit.
### Task 2: the run header and order
- [x] Tests in `Run.test.tsx`: breadcrumb, *Console*, *Open the pipeline* with `from`, failure
  before panels, *Steps*/*Tasks* headings. Implement. Commit.
### Task 3: the failure panel
- [x] Tests in `Failure.test.tsx`: two regions, attempts with asked/peak, console action, report.
  Implement. Commit.
### Task 4: browser and records
- [x] Fixtures at 1440/390, light/dark; CHANGELOG; tick; commit.

## Deviations (recorded during execution)

- **Removed from the board:** the five summary tiles (*needs you*, *running now*, *succeeded ·
  14 days*, *typical run*) and the runs-per-day chart. *Went wrong* is a tab; the summary query
  stays for the per-row *vs usual*.
- **The stat panels' and timeline's labels** became sentence-case headings, and *Delete* a header
  action, so the run page reads in one style.
- **Phone width:** the board and run page roots take `min-w-0` (they grew to their widest
  child), the attempt figures wrap under their bar, and the Steps and Tasks bands scroll sideways
  rather than clip.
- **The failure report's footer** said *W3 explains*, which is internal vocabulary; it reads
  *shown as written*.
- **Browser check:** fixtures through the DevTools script for the board and a failed run, 1440
  and 390, light and dark. The live socket is not answered there, so the console stream is not
  shown.

# Redesign 6 — runs Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

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
- [ ] Tests in `Board.test.tsx`: tabs and the `phase` query; total on the active tab; pipeline
  names by digest; no executor/submitter text; Mendel failing leaves *unknown pipeline*. Implement. Commit.
### Task 2: the run header and order
- [ ] Tests in `Run.test.tsx`: breadcrumb, *Console*, *Open the pipeline* with `from`, failure
  before panels, *Steps*/*Tasks* headings. Implement. Commit.
### Task 3: the failure panel
- [ ] Tests in `Failure.test.tsx`: two regions, attempts with asked/peak, console action, report.
  Implement. Commit.
### Task 4: browser and records
- [ ] Fixtures at 1440/390, light/dark; CHANGELOG; tick; commit.

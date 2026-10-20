# Redesign 5 — Home Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Home leads with describing, then what needs you, then your pipelines and results.
**Architecture:** `Home.tsx` composes a header, `Describe`, a card row (`Now` split into
`RunningCard`, `NeedsYouCard`, `WentWrongCard`), the pipelines panel (`Work.tsx`) and
`ResultsCard`. Data is the three queries Home already makes. No server change.
**Tech Stack:** React 19, TypeScript, Tailwind (part 1 tokens), Vitest.
**Spec:** `docs/superpowers/specs/2026-10-20-redesign-home-design.md`

## Global Constraints

- Absence is absence: a card with nothing is not drawn. No owner, lab or *started by* anywhere.
- Named radii only; colour by meaning; `bg-action` raises. `cd frontend && npx vitest run && npx tsc -b`.

## Review Focus

- Wiener down: no run cards, the message, pipelines still drawn — Task 2.
- A draft with only `open_not_named` — Task 1.
- Many failed or finished runs — capped at three — Task 1.
- Phone width: cards stack, table scrolls inside its panel — Task 3.

---

### Task 1: the cards
- [ ] Tests in `home/Cards.test.tsx`: `NeedsYouCard` lists pipelines with settings and *Answer*
  links, says *N values* for unnamed; `WentWrongCard` caps at three, newest first, links;
  `ResultsCard` only succeeded, capped at three; `RunningCard` has no *started by*; each returns
  nothing when empty. Implement in `home/Cards.tsx`; delete `Now.tsx`. Commit.

### Task 2: Home, Describe, Work, First
- [ ] Tests in `Home.test.tsx`: header *Your work* and its line; *New analysis* link; order —
  describe, cards, *Your pipelines*, results; no *Owner* header; decided words in the table;
  Wiener down. Update existing Home/First tests that read the old layout. Implement. Commit.

### Task 3: browser and records
- [ ] Fixture-answered Vite at 1440/390, light/dark; fix; CHANGELOG; tick; commit.

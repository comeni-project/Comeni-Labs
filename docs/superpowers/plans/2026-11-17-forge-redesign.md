# The Forge, to the board — implementation plan

**Goal:** Forge home and the forging pages (Tool · Tests · Publish) built to the redesign board.
**Spec:** `docs/superpowers/specs/2026-11-17-forge-redesign-design.md`
**Tech:** React + TanStack Query + Tailwind tokens; FastAPI for the one summary change.

## Global constraints

- Tokens only (no hex), no uppercase outside `RailControls`, no "#123" in strings.
- No assistant-voice copy. Derived facts only. Tests use recorded fixtures, never live models.
- Python tests via the `pt` wrapper on the test DB (5442).

## Review focus

1. A forging with no items yet (just started, drafting) — Tool page shows the draft state, not a blank canvas.
2. A forging with removed items — removed ports/params never drawn or counted.
3. A refused command (stale `expected`) — the page re-reads and the inspector shows the refusal.
4. Tests unavailable / publish unavailable — the reason shows where the action would be.
5. Catalogue down — home still lists forgings and needs-you; search says it is unavailable.

## Tasks

### Stage 1 — Forge home

- [x] 1.1 `AdaptationSummary` gains `tests_failed: int` and `pull_request: str | None` (state);
      test in `packages/mendel-api/tests/forge/` asserting both for a forging with a failed test.
- [x] 1.2 `frontend/src/forge/stages.ts`: `stagesOf(summary) → [tool, tests, publish]` each
      `done | now | failed | later` plus a status line; unit tests.
- [x] 1.3 `frontend/src/forge/ForgeHome.tsx` at `/forge`: search (catalogue `q`, rows with
      reads → makes chips, fit line, Forge button starting a forging), Needs you, Forgings cards,
      "+ Forge a tool by hand" (search focus). Rail slot: forging picker + Forgings list. Test.
- [x] 1.4 Rail's Forge place → `/forge`; delete `ForgingList`.

### Stage 2 — The forging frame

- [x] 2.1 `frontend/src/forge/ForgingFrame.tsx`: loads the adaptation, rail sub-pages
      Tool / Tests / Publish with status lines, Review list of waiting AI items, page header.
- [x] 2.2 Routes `/forge/:id`, `/forge/:id/tests`, `/forge/:id/publish`; delete
      `/registry/forging*`; update links in Selected, Tool, Measurers.

### Stage 3 — Tests

- [x] 3.1 `frontend/src/forge/TestsPage.tsx`: summary line, Run all, cases list, selected case
      (inputs, parameters changed, expected vs got), coverage card. Test.

### Stage 4 — Publish

- [x] 4.1 `frontend/src/forge/PublishPage.tsx`: track (Drafted, Tests passed, Pull request opened,
      Merged, Released) with the action for the current step and blockers; files card. Test.

### Stage 5 — Tool

- [x] 5.1 `frontend/src/forge/parts.ts`: items → `{ process, inputs, outputs, params, rules,
      measurers, vocabulary, review }`; unit tests (removed hidden; AI waiting detected).
- [x] 5.2 `frontend/src/forge/ToolCanvas.tsx`: process box with ports, neighbours, legend; part cards.
- [x] 5.3 `frontend/src/forge/Inspector.tsx`: Part tab (port and parameter fields, other kinds
      read-only, AI note with Looks right / Change) and Assistant tab (chat). Test.
- [x] 5.4 Draft action for the next piece when it has no items.

### Stage 6 — Cleanup and checks

- [x] 6.1 Delete unused `registry/forging/*` components and their tests.
- [x] 6.2 `make client`, frontend suite, tsc, forge API tests, ruff; browser check against the board.
- [x] 6.3 Issue for "Your registry can't yet"; commit; push.

## Deviations

- **1.3** The forging card's description comes from the catalogue entry (one read a card); absent
  when the catalogue is down.
- **2.2** The old forging's `useAdaptation`, `useForgeActions`, `useForgeSteps`, `progress`, the item
  forms (`ItemConstructor`, `ConstructorFields`, `SettingFields`), `RulePreview` and `ValueDetails`
  moved to `src/forge/` and are reused; everything else in `registry/forging/` and
  `registry/parts/Tracker` is deleted.
- **5.3** The inspector edits ports (data type, format, needed / always made) and parameters
  (default, help); other kinds show their value and open the item form on *Change*. Board fields
  with no field in the contract are left out: a port's *How it arrives* (the type's grain, not the
  port's), a parameter's *Who decides it*, *Ask AI* buttons, *Check again / See replay*.
- **5.4** Drafting stays piece by piece: a banner names the next piece with *Draft with the AI*.
- **3.1** *Run this test*, *+ New test* and the *Expect a file / value / snapshot* buttons are left
  out: the API runs all tests at once and tests are written as items (Tool → + Add on tests).
- **6.3** "Your registry can't yet" filed as an issue; the strip is not shown.
- **Names:** `ForgingFrame.tsx` is `Forging.tsx`, `parts.ts` is `items.ts`, `ToolCanvas.tsx` is part
  of `ToolPage.tsx`; the assistant is `Assistant.tsx`. Page tests are in `forge/Forge.test.tsx`
  over the recorded quast forging (`quast.fixture.json`). Issue 534 holds "can't yet".

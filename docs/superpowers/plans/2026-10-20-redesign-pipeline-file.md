# Redesign 4 — pipeline file and run sheet Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The pipeline file becomes a page of values with their reasons beside the file; the run
sheet becomes numbered sections with a summary holding the action.

**Architecture:** A pure `valuesOf(steps, graph)` summarises settings by how they were decided;
`PipelineFile` draws it beside `FileText` (preview or kept). `LivingSurface` swaps the canvas and
panel for `PipelineFile` when the header's view is *Pipeline file*. `RunSheet` keeps its props
and `SubmitPanel`/`GateVerdict`, and changes its layout only.

**Tech Stack:** React 19, TypeScript, Tailwind with part 1 tokens, Vitest.

**Spec:** `docs/superpowers/specs/2026-10-20-redesign-pipeline-file-design.md`

## Global Constraints

- No server or generated-client change; tier names come from `useTiers`, never typed here.
- Open means `useBuilder.open` after `withTypedValues`; a model's choice is not drawn.
- Named radii only (`rounded-control|button|panel`); colour by meaning; `bg-action` buttons raise.
- Test with `cd frontend && npx vitest run && npx tsc -b`; lint with `npm run lint`.

## Review Focus

- A step with no settings: its card says so rather than drawing an empty table — Task 2.
- Preview not ready (empty/illegal/outdated): the file column says why; the values column still
  draws from the frame — Task 2.
- *Show only open* with nothing open: says *Nothing is open* — Task 2.
- The run sheet before keeping (no `draftId`): sections still draw; the action says why it waits
  — Task 3.
- Phone width: both pages stack without sideways scroll — Task 4.

---

### Task 1: `valuesOf` and the header

**Files:** Create `frontend/src/build/living/values.ts`, `values.test.ts`; modify
`LivingHeader.tsx` (+ its test in `LivingSurface.test.tsx`).

**Interfaces:** `valuesOf(steps: AnsweredStep[]): { total: number; settled: number; measured: number; open: number }`
— settled = tiers 1–2 not open, measured = tier 3, open = `open(setting)`.
`LivingHeader` gains `openValues: number`; toggle labels *Canvas* / *Pipeline file* (test ids
unchanged); chip `data-testid="needs-you-chip"`.

- [ ] Tests: counts on a fixture with tiers 1–4 and one answered tier-4 value; header words and
  chip (absent at 0, *1 value needs you*, *2 values need you*). Fail, implement, pass, commit.

### Task 2: `PipelineFile`

**Files:** Create `frontend/src/build/living/PipelineFile.tsx`, `PipelineFile.test.tsx`;
modify `LivingSurface.tsx` (render it for `view === "artifact"` in the build stage, replacing the
drawer); keep `ArtifactPreview`'s states and change-highlight inside the file column; delete the
drawer use for the artifact.

**Interfaces:** `PipelineFile({ steps, preview, draftId, kept })` where `steps: AnsweredStep[]`,
`preview: AuthoringPreview | null`, `kept: boolean`.

- [ ] Tests: summary words and counts; a step table row (tier name from a mocked `/registry/tiers`
  response, reason, premise); open value `null`; *Show only open*; *Nothing is open*; a step with
  no settings; download creates a blob with the preview text; tabs *as it would read* / *as kept*
  (kept disabled when not kept); preview `outdated` text. Fail, implement, pass, commit.

### Task 3: the run sheet layout

**Files:** modify `frontend/src/build/RunSheet.tsx` and its tests (`Submit.test.tsx`,
`Gate.test.tsx` untouched; add `RunSheet.test.tsx` if absent).

- [ ] Tests: sections *Checked*, *Your files*, *Values still open* in order (third only when
  open values exist); summary rows *Steps*, *Inputs*, *Values open*, *Where · this machine*; the
  summary holds `send-to-wiener`; Escape and Cancel still close. Fail, implement, pass, commit.

### Task 4: browser check and records

- [ ] `?fake=1` with the artifact view and the run sheet (the fakes have no run sheet: check it
  through the stack or a test harness page if needed), 1440 and 390, light and dark; fix layout;
  CHANGELOG line; tick this plan with deviations; commit.

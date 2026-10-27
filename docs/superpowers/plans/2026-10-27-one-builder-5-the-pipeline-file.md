# One builder, plan 5: the pipeline file, file first — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The pipeline file page puts the file first (#394): the file takes most of the page,
each value line carries a mark of how it was decided, clicking a line opens its reason beside the
file, the counts filter the file, and *Compile it* shows the Nextflow it compiles to.

**Architecture:** One read-only endpoint emits `main.nf` and `nextflow.config` from the draft's
preview materialisation, with the same `emit` / `emit_config` the bundle uses. The page maps
each line of the server's `pipeline.yml` text to its step and setting (`fileLines`, from the
file's own layout: `- id:` opens a step, `  - name:` under `  settings:` a setting), and draws
the marks and the reason panel from the frame's steps it already holds. The values table, its
bar and *Show only open* give way to the file, the count strip and the reason panel.

**Tech Stack:** Python 3.12, FastAPI, pytest; React 19, TanStack Query, vitest.

**Spec:** `docs/superpowers/specs/2026-10-22-one-builder-design.md`, section *The pipeline file
(#394)*. **Decided (operator, 2026-10-27): option A**, the reason opens beside the file (mockup
`.design/one-builder-5/pipeline-file.html`). On a phone the reason panel is a sheet from the
bottom. Builds on plan 4 (`one-builder-4`).

## Global Constraints

- **The file is the server's text**: the page never rewrites or reformats it; marks and the
  reason panel sit beside lines, and filtering hides lines, never edits them.
- **Compile writes nothing** and makes no network or model call: `emit` and `emit_config` over
  the in-memory preview materialisation, as `mendel emit` does. A draft whose preview is not
  `ready` answers with the preview's state and its coded findings.
- **Marks are named by evidence** (#397): `measured` only when every premise was measured;
  tier words come from `useTiers`, never typed (the board-match trap).
- Diagnostics are declared in `diagnostics.yml` and raised through `coded()`.
- Frontend traps from plan 3 apply.

## Feature inventory (current page → after this plan)

- [ ] counts headline and bar → the count strip (each count a filter)
- [ ] *Show only open* → the strip's *needs you* count
- [ ] section chips (Goal, Facts, Steps, …) → kept, above the file
- [ ] values table (setting, value, how, why) → line marks + the reason panel
- [ ] *pipeline.yml* / *as kept* tabs → kept, beside *main.nf* and *nextflow.config*
- [ ] preview label, changed-line highlight, not-ready states and findings → kept (`ArtifactPreview`)
- [ ] Download pipeline.yml → kept, in the page's bar

## Review Focus

1. **A setting whose block spans several lines** (a wrapped `reason:`): every line of it selects
   the same setting; the mark sits on its `- name:` line only. Test in Task 2.
2. **A step with no settings** (`settings: []`): no marks, its lines select nothing. Test in Task 2.
3. **Compile on a draft that is not ready** (empty, outdated): the tabs say why, never empty
   files. Test in Tasks 1 and 3.
4. **A filter with no matches**: the file says so and offers *show all*. Test in Task 3.

---

### Task 1: The draft's Nextflow, emitted on request

**Files:**
- Modify: `packages/mendel-api/src/mendel_api/services/drafts.py` (add `emitted`)
- Modify: `packages/mendel-api/src/mendel_api/routes/build.py` (`GET /pipeline/drafts/{draft_id}/emitted`)
- Modify: `packages/comeni-core/src/comeni_core/diagnostics.yml` (`MI0219`: nothing to compile yet)
- Test: `packages/mendel-api/tests/pipelines/test_emitted.py`; `make client`

**Interfaces:**
- Produces: `drafts.emitted(draft_id: str, *, ai=None) -> Emitted`, where
  `Emitted(NamedTuple): revision: int; main_nf: str; config: str`; raises
  `ValueError(coded("MI0219", …))` when the preview's state is not `ready`, with its first
  finding in the message.
- Produces: route `operationId: emittedPipeline`, response
  `EmittedPipeline { revision: int; main_nf: str; nextflow_config: str }`, 422 on `MI0219`.

- [ ] **Step 1: Failing tests** — for a ready draft the route returns a `main_nf` holding a
  `workflow {` block and one `include` per step in the preview, the same text twice in a row
  (deterministic), and a non-empty `nextflow_config`; an empty draft
  answers 422 with `MI0219`; the route writes nothing under the draft directory.
- [ ] **Step 2: Run** with the test database — Expected: FAIL (404).
- [ ] **Step 3: Implement**, reusing `_materialised` as `preview` does (one path to the text).
- [ ] **Step 4: Run** — Expected: PASS. `make client`; `make docs` (diagnostics reference).
- [ ] **Step 5: Commit** `feat(build): the draft's Nextflow, emitted on request (#394)`

### Task 2: Which setting each line of the file is

**Files:**
- Create: `frontend/src/build/living/fileLines.ts`, `valueMarks.ts` (`chipWords` and the chip
  colours moved out of `PipelineFile.tsx`)
- Test: `frontend/src/build/living/fileLines.test.ts`

**Interfaces:**
- Produces: `fileLines(text: string): (LineRef | null)[]`, one entry per line, where
  `LineRef = { step: string; setting: string; head: boolean }` (`head` on the `- name:` line).
- Produces: `markOf(setting: Answered, tiers): { words: string; tone: "measured" | "open" | "yours" | "plain" }`.

- [ ] **Step 1: Failing tests** over a slice of `tests/fixtures/pipeline-v8/pipeline.yml`
  (STAR_ALIGN's `seq_platform` block, with its wrapped `reason:`): every line of the block maps
  to `{step: "star_align", setting: "seq_platform"}`, only its `- name:` line has `head: true`;
  `trimgalore`'s `settings: []` and its `why:` lines map to `null`; top-level keys map to `null`.
  `markOf`: an open tier-4 value is `needs you`/`open`; an answered one `your answer`/`yours`;
  tier 3 measured `measured`; tier 3 over a typed value the served tier-3 group name, `plain`.
- [ ] **Step 2: Run** — Expected: FAIL.
- [ ] **Step 3: Implement** (a line scan tracking indentation; no YAML parser in the browser).
- [ ] **Step 4: Run** — Expected: PASS.
- [ ] **Step 5: Commit** `feat(build): which setting each line of the file is (#394)`

### Task 3: The page, file first

**Files:**
- Modify: `frontend/src/build/living/PipelineFile.tsx` (rewrite), `ArtifactPreview.tsx` (line
  marks, selection, filter), `LivingSurface.tsx` (pass `onSelect`, `onAsk`, `setView`)
- Modify: `frontend/src/main.css` (`.pipeline-file` grid: file `minmax(0,1fr)`, reason 340px;
  under 640px the reason is a bottom sheet)
- Test: `frontend/src/build/living/PipelineFile.test.tsx` (rewrite to the new page)

**Interfaces:**
- Consumes: `emittedPipeline` (Task 1), `fileLines`, `markOf` (Task 2).
- Produces: `PipelineFile({ steps, preview, draftId, kept, onChange, onAsk })` where
  `onChange(node)` opens that step in the builder and `onAsk(text)` puts text in the composer
  and returns to the conversation.

- [ ] **Step 1: Failing tests**
  - the strip shows one count per non-zero kind; clicking *1 measured* hides every setting block
    that is not measured (step `- id:` lines stay) and says *showing measured · show all*; a
    filter with no matches says *Nothing is measured.* with *show all*;
  - the `- name:` line of each setting carries its mark (`measured`, `needs you`, …);
  - clicking any line of `sjdbOverhang`'s block opens the reason panel: step, setting, value,
    mark, reason, premise; *Change it* calls `onChange("star_align")`; *Ask about it in the chat*
    calls `onAsk("About STAR_ALIGN sjdbOverhang: ")`;
  - *Compile it* fetches `/pipeline/drafts/{id}/emitted` and shows *main.nf* and
    *nextflow.config* tabs with the text; a 422 shows the finding instead;
  - *as kept* still appears only when kept; Download still downloads the shown `pipeline.yml`.
- [ ] **Step 2: Run** — Expected: FAIL.
- [ ] **Step 3: Implement**; tick the inventory above with each item's home.
- [ ] **Step 4: Run** `npx vitest run`, `npx tsc -b`, `npm run lint` — Expected: PASS.
- [ ] **Step 5: Commit** `feat(build): the pipeline file, file first (#394)`

### Task 4: Docs and checks

**Files:** `docs/reference/pipelines/builder-interface.md` (*Pipeline file* row),
`CHANGELOG.md` (mendel-api, frontend), journal entry; copy the mockup to
`.design/one-builder-5/`; tick this plan; comment on #394.

- [ ] **Step 1:** write them; `make check` — Expected: exit 0.
- [ ] **Step 2: Commit** `docs: one builder plan 5 — the pipeline file (#394)`

## Deviations

(Recorded during execution.)

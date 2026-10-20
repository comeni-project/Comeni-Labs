# Redesign 4 — the pipeline file and the run sheet

**Issue:** #379 (parent #370). **Status:** the operator asked for the redesign parts to be built
from the issue and the boards without a question round (2026-10-20); the calls below are the
builder's. Implemented; deviations are in the plan. Branch `redesign-pipeline-file`, stacked on part 3 (`redesign-describe-build`); the
redesign lands on `main` as one pull request at the end.
**Boards:** `.design/hybrid/PipelineFile.dc.html` (*Pipeline file — every value and its reason*)
and `.design/hybrid/RunSheet.dc.html` (*Run — files, reference, where*).

## Why

`pipeline.yml` is the pipeline, and every value in it carries why it has that value. Today the
builder shows it as monospace text in a drawer over the canvas, so a person has to read YAML to
learn which values were measured, which are conventions and which still need them. The run sheet
is an 820 px dialog of placeholder slots with the real controls below the fold. The boards draw
both as pages a researcher reads: the values as a table with their reasons, beside the file; the
run as numbered sections with a summary that holds the one action.

## What changes

### 1. The header

- The view toggle reads **Canvas · Pipeline file** (a segmented control, as on the boards), and
  *Run* carries a ▸ mark.
- Beside the name: a **needs you** chip counting open values (`N value(s) need you`) when there
  are any. The existing status line stays.

### 2. The pipeline file — a page, not a drawer

Choosing *Pipeline file* replaces the canvas and panel (build stage only) with two columns:

- **Left — every value and its reason**, from the canvas frame's steps (`CanvasFrame.steps`,
  each `StepView.settings`), with typed answers laid over them (`withTypedValues`):
  - A summary card: **N values, and how each was decided** — a bar split by how they were
    decided, and a line: *settled by a rule or convention* (tiers 1–2), *measured from your
    files* (tier 3), *need you* (open, by `useBuilder.open`). There is no per-value record of a
    model's choice in `SettingView`, so the board's *chosen by a model* segment is not drawn.
  - **Show only open** (a toggle) and **Download pipeline.yml** (the text on screen, as a file).
  - One card per step: the process, its contract, its counts, and a table — *Setting*, *Value*,
    *How it was decided* (the tier's name from `useTiers`, coloured by meaning: measured amber,
    open needs-you red, the rest neutral), *Why* (`reason`, then the premise when there is one).
    An open value shows `null` in needs-you ink.
- **Right — the file itself**, line-numbered: *as it would read* (`AuthoringPreview`) or *as
  kept* (`ArtifactView`'s artifact) when kept, as tabs. Lines holding `null` are tinted
  needs-you. The preview's states (empty, illegal, outdated, unavailable) and its findings say
  what they say today. Below 1000 px the columns stack, values first.

### 3. The run sheet — sections and a summary

The same overlay and the same sequence (*Send to Wiener*, then fill what the artifact declares,
then *Start run*: uploading is what discovers the parameters), laid out as the board:

- **Left — numbered sections:** ① *Checked* — the gate's verdict (`GateVerdict`); ② *Your
  files* — each input the pipeline needs, with its type, and, after sending, the sample sheet
  and the declared values (`SubmitPanel`'s form); ③ *Values still open* — when there are any,
  each with its step and reason, and *You can run with these open; whatever they become is
  recorded as yours*. A section's mark is a tick when done, its number otherwise.
- **Right — Ready to run:** steps, inputs, values open, where it runs (*this machine*, the only
  executor today), then the primary action (`SubmitPanel`'s *Send to Wiener* / *Start run* /
  *Watch it*), then *What this run will record*.

**Not drawn, because nothing in the product knows them:** the reference picker, Kubernetes and
AWS Batch, the largest-task limits, *took last time*, and a task estimate. Absence is absence.

## Not in this part

The runs pages (#380), Home (#378), settings (#381). No server change.

## Testing

Vitest with the existing fixtures: the toggle words; the needs-you chip and its count; the
summary's counts and words; a step table row's tier name, reason and premise; *Show only open*
hides decided rows; open values read `null`; download produces the text; the preview states;
the kept tab only when kept. Run sheet: the three sections in order, the summary's facts, the
open section only with open values, and the existing `SubmitPanel`/`GateVerdict` tests still
passing. Then the browser at 1440 and 390 px, light and dark, beside both boards.

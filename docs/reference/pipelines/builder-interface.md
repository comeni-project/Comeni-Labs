# Builder interface

Use this page to identify controls and status signals in the builder.
For the task sequence, see [Build and inspect a pipeline](../../how-to/pipelines/build.md).

## What you see

| Area | What it is for |
|---|---|
| Pipeline name | the draft name shown on the home page and run links; click it to rename |
| Status chip | *working* while the agent is, *built* once there is a pipeline, *outdated* when your answers moved past it; and how many values still need you |
| Canvas | the steps and wires in the pipeline, as they stand; a step the AI chose that nobody has reviewed carries a small **AI** tag. A step with many ports grows to show each on its own row |
| Step menu | right-click a step (a long press on a touch screen, `⋯` beside the selected step, or Shift+F10): *Ask about this step*, *Settings…*, *Inputs…*, *Swap tool…*, *Show in pipeline file*, *Keep whole* / *Run on parts*, *Looks right*, *Remove step…* — each only where it applies |
| Step card | opens beside the step from a click (Settings) or the menu, one at a time; Esc or × closes. Settings: what the AI chose there with **Looks right**, what still needs you, then optional, measured and settled values. Inputs: each optional input off, optional or required, and running in parts |
| `+ Add step` | browse tools that can be added to the graph |
| Ports | drag from an output to an input to wire it; click a port to see what can connect there |
| Wire | click to detach it |
| Delete | remove the selected step |
| Fit, −, +, 1:1, Tidy | fit the drawing, zoom, reset the view, give moved steps back their places |
| Canvas · What was understood | the switch above the canvas: the drawing, or the record of what you said, measured and corrected |
| Conversation | what you say and what the agent says. While it works, its trail shows what it says it is about to do, each tool it used, the one running now, and *Thinking…* while the model answers; all of it folds into **How I got here** once it answers. Each answer is marked as the AI's words, with links to the steps its tools read or changed |
| Agent question | a question the agent needs you to answer, drawn as options, a number with its unit, yes or no, an upload, or a line of text; only the newest is answerable |
| Retry | on a turn that failed: ask the agent again |
| Composer | never locked: what you type while the agent works is read next |
| Pipeline file | the `pipeline.yml` behind the draft: an outline of its sections and steps, with the counts of how values were decided as filters; tabs for `pipeline.yml`, `main.nf` and `nextflow.config` (compiled when opened); each step's provenance folded to one line; a value's reason beneath its lines with **Ask the AI** and **Change**; any selected text can be explained or asked about; and the AI panel, the same conversation as the builder, which folds away |
| Run | keep, check, collect run inputs, and submit |

**A change on the canvas is yours at once.** Removing, adding, wiring or swapping a step, or
typing a value, is read as what it means (you never want this tool here, this input comes from
that step) and recorded as your decision; the pipeline is built again from it. Moving a step is
layout only. If the agent changed the pipeline while you were looking, your change is refused
(`MI0201`) and the canvas shows the pipeline as it now is.

The conversation and the canvas run side by side from the first message: the canvas is empty
until the agent builds, then shows each step as it lands. On a phone, **Chat**, **Canvas** and
**Understood** are tabs.

## Good signs

| Signal | Meaning |
|---|---|
| Saved status is current | the draft has been persisted |
| No validation findings | the graph shape is acceptable to the build service |
| No red decisions | no required human answer is open |
| Artifact view renders | there is a materialized pipeline record to inspect |

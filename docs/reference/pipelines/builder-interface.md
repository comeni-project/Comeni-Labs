# Builder interface

Use this page to identify controls and status signals in the builder.
For the task sequence, see [Build and inspect a pipeline](../../how-to/pipelines/build.md).

## What you see

| Area | What it is for |
|---|---|
| Pipeline name | the draft name shown on the home page and run links; click it to rename |
| Status chip | *working* while the agent is, *built* once there is a pipeline, *outdated* when your answers moved past it; and how many values still need you |
| Canvas | the steps and wires in the pipeline, as they stand; a step the AI chose that nobody has reviewed says *chosen by the AI · review* |
| `+ Add step` | browse tools that can be added to the graph |
| Ports | drag from an output to an input to wire it; click a port to see what can connect there |
| Wire | click to detach it |
| Delete | remove the selected step |
| Fit, −, +, 1:1, Tidy | fit the drawing, zoom, reset the view, give moved steps back their places |
| Canvas · What was understood | the switch above the canvas: the drawing, or the record of what you said, measured and corrected |
| Conversation | what you say and what the agent says; its working trail, one line per tool it used, folds into **How I got here** once it answers |
| Agent question | a question the agent needs you to answer, drawn as options, a number with its unit, yes or no, an upload, or a line of text; only the newest is answerable |
| Retry | on a turn that failed: ask the agent again |
| Open step | a step opened over the conversation: what the AI chose there and **Looks right**, what still needs you, what was measured, what a rule settled, and its tools; **×** returns |
| Composer | never locked: what you type while the agent works is read next |
| Pipeline file | the `pipeline.yml` behind the draft, file first: each value's line marked by how it was decided, its reason beside the file, the counts as filters, and **Compile it** for `main.nf` and `nextflow.config` |
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

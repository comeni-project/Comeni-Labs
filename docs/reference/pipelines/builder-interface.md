# Builder interface

Use this page to identify controls and status signals in the builder.
For the task sequence, see [Build and inspect a pipeline](../../how-to/pipelines/build.md).

## What you see

| Area | What it is for |
|---|---|
| Pipeline name | the draft name shown on the home page and run links; click it to rename |
| Status chip | where the build is, and how many values still need you |
| Canvas | the steps and wires in the pipeline |
| `+ Add step` | browse tools that can be added to the graph |
| Ports | drag from an output to an input to wire it; click a port to see what can connect there |
| Wire | click to detach it |
| Delete | remove the selected step |
| Fit, −, +, 1:1, Tidy | fit the drawing, zoom, reset the view, give moved steps back their places |
| Canvas · What was understood | the switch above the canvas: the drawing, or the record of what you said, measured and corrected |
| Conversation | everything the engine asks and offers, and what you say; the step on offer and the open question are its newest message |
| Step strip | the plan above the conversation: click a step to open it; **Step n of m** opens the whole plan, who decided each step and how |
| Open step | a step opened over the conversation: what still needs you, what was measured, what a rule settled, and its tools; **×** returns |
| Still needed | the open question, docked above the composer once you talk past it; answer it there or show it again |
| Composer | never locked: what you type while the engine works waits in line, marked *waiting* |
| Hand-over | when a build finishes: what you built, how its values were decided, what still needs you, and **Run it** or the pipeline file |
| Pipeline file | the `pipeline.yml` behind the draft, file first: each value's line marked by how it was decided, its reason beside the file, the counts as filters, and **Compile it** for `main.nf` and `nextflow.config` |
| Run | keep, check, collect run inputs, and submit |

**A change on the canvas is read before it counts.** Removing, adding, wiring or swapping a
step changes nothing at once: the engine says how it read the change (*So you never want
trimming here — right?*) in the conversation. **Yes** records it as your decision and the
engine plans around it; **No, undo** leaves the pipeline as it was. A value typed in a setting
counts at once. Moving a step is layout only. Every change made outside the conversation is
announced in it, with a link to the step or line it changed.

While you describe, the same page shows **What was understood** where the canvas will be, and
**Start building** in the header confirms it. On a phone, **Chat**, **Canvas** and **Understood**
are tabs.

## Good signs

| Signal | Meaning |
|---|---|
| Saved status is current | the draft has been persisted |
| No validation findings | the graph shape is acceptable to the build service |
| No red decisions | no required human answer is open |
| Artifact view renders | there is a materialized pipeline record to inspect |

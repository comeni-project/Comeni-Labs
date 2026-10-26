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
| Step panel | the step line, a selected step's settings and tools, and **From your edit** |
| Assistant | the conversation |
| Pipeline file | the materialized `pipeline.yml` behind the draft, and its findings |
| Run | keep, check, collect run inputs, and submit |

**A change on the canvas is read before it counts.** Removing, adding, wiring or swapping a
step changes nothing at once: the engine says how it read the change (*So you never want
trimming here — right?*) under **From your edit**. **Yes** records it as your decision and the
engine plans around it; **No, undo** leaves the pipeline as it was. A value typed in a setting
counts at once. Moving a step is layout only.

## Good signs

| Signal | Meaning |
|---|---|
| Saved status is current | the draft has been persisted |
| No validation findings | the graph shape is acceptable to the build service |
| No red decisions | no required human answer is open |
| Artifact view renders | there is a materialized pipeline record to inspect |

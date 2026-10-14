# Builder interface

Use this page to identify controls and status signals in the builder.
For the task sequence, see [Build and inspect a pipeline](../../how-to/pipelines/build.md).

## What you see

| Area | What it is for |
|---|---|
| Pipeline name | the draft name shown on the home page and run links |
| Status line | save state, validation state, and how many values still need you |
| Canvas | the steps and wires in the pipeline |
| `+ Add step` | browse tools that can be added to the graph |
| Step/settings panel | inspect a selected step and answer settings |
| Ask/problems panel | open decisions and validation findings |
| Artifact view | the materialized `pipeline.yml` behind the draft |
| Run | keep, check, collect run inputs, and submit |

Use the canvas to inspect and change the draft. The artifact view shows the saved
pipeline record for review before execution.

## Good signs

| Signal | Meaning |
|---|---|
| Saved status is current | the draft has been persisted |
| No validation findings | the graph shape is acceptable to the build service |
| No red decisions | no required human answer is open |
| Artifact view renders | there is a materialized pipeline record to inspect |

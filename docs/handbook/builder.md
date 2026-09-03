# The builder

The builder is where a pipeline draft becomes something you can defend. It is a low-code graph
editor backed by typed tools and rules, not a free-form drawing surface.

A draft is the editable graph. An artifact is the saved pipeline record behind it. See
[Core words](core-words.md) if those terms are new.

![RNA-seq draft in the alpha builder](../assets/screenshots/builder-rnaseq-alpha.png)

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

The canvas is not the source of truth by itself. The artifact is. Use the canvas to inspect and
change the draft; use the artifact view when you need the exact record of what will be run.

## Common workflow

1. Open `/build` or click **New pipeline** from the home page.
2. Inspect the draft that opens.
3. Select a step to see its ports, settings, and reasons.
4. Answer red decisions before relying on the pipeline.
5. Use **Artifact** to see the materialized pipeline record.
6. Press **Run** when the status line is clean enough for the gate you intend to run.

## Worked example: inspect STAR

Using the shared [RNA-seq example](rnaseq-example.md), select the aligner step. In the current
registry this is usually `STAR align` for 150 bp reads.

Read the step in three passes:

| Pass | What to check | Example |
|---|---|---|
| Ports | whether the step consumes and produces the right biological objects | reads and genome index in, BAM out |
| Settings | whether any value still needs a person | `seq_platform` may be unanswered |
| Reason | why this implementation was chosen | read length matched the STAR rule |

The useful question is not “did the app pick STAR?” It is “what evidence made STAR the current
answer, and which premise would change that answer?”

## Canvas and artifact

The canvas is for working. The artifact is for review.

![Artifact view in the alpha builder](../assets/screenshots/artifact-view-alpha.png)

When something looks surprising on the canvas, open **Artifact** and find the same step in
`pipeline.yml`. The artifact should name the selected contract, settings, decision tiers, and
provenance. If the app and artifact disagree, treat the artifact as the durable record and the
UI as suspect.

## Good signs

| Signal | Meaning |
|---|---|
| Saved status is current | the draft has been persisted |
| No validation findings | the graph shape is acceptable to the build service |
| No red decisions | no required human answer is open |
| Artifact view renders | there is a materialized pipeline record to inspect |

## Alpha note

The builder is already the main product surface, but some details are expected to change:
natural-language goal entry, input collection, and run submission are still being shaped. Learn
the loop and the evidence model; do not treat the current input form as a stable external API.

## Where the science enters

Tools, types, measurements, and rules come from the registry. If the builder cannot choose a
tool or asks a question the lab can answer with a rule, the fix usually belongs in the
[Registry](../registry/index.md), not in a one-off graph edit.

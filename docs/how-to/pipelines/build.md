# Build and inspect a pipeline

Use the builder to inspect steps, review their settings and save a pipeline artifact.
Every pipeline opens in the same builder: a conversation with the builder agent beside a canvas.
With a model configured you can start by describing the analysis; without one, start by drawing
at `/build`.

The draft is a **living pipeline**: the agent builds it as you describe the analysis, tells you
what it chose and why, and asks when it needs something only you know. You can change any step
or setting yourself at any time. The conversation and canvas are two views of that one draft,
while the artifact remains its durable record. How the agent works, and what it may and may not
do, is in [How the builder agent works](../../explanation/builder-agent.md).

A draft is the editable graph. An artifact is the saved pipeline record behind it. See
[Core words](../../explanation/pipeline-concepts.md) if those terms are new.

![RNA-seq draft in the alpha builder](../../assets/screenshots/builder-rnaseq-alpha.png)

## Inspect and review the draft

1. Open a pipeline from the home page, or click **New analysis** and say what you have and what
   you want.
2. Read what the agent says it did. **How I got here** under each answer lists the tools it used.
3. Answer the agent's questions in the card it draws, or in your own words.
4. Open a step marked *chosen by the AI · review* to see what it chose there. Ask in the chat
   why, change it, or press **Looks right**.
5. Answer red decisions before relying on the pipeline.
6. Use **Pipeline file** to see the materialized pipeline record.
7. Press **Run** when nothing needs you.

## Change it by hand

Add a step, remove one, swap its tool, or drag a wire between two ports. The engine reads what
the change means (you never want trimming here, this input comes from that step) and records it
as your decision at once: the pipeline is built again around it, and the agent plans around it on
every later turn. When the engine cannot honour a change (you excluded the only tool that can
make something), it says so with a code and keeps nothing.

To start without a model, open **New analysis** and add the step that makes what you want, such
as featureCounts for gene counts, then wire and add the steps it needs.

## Optional inputs

Some tools can run with or without an input — QUAST runs on assemblies alone, and adds
misassembly reports when it also gets a reference genome. On the canvas, such an input is drawn
dashed. Open the step to see its **Optional inputs**: each says what it adds and is one of:

- **Off** — the pipeline does not take it. This is where every optional input starts.
- **Optional** — the pipeline takes it, and each run may supply the file or leave it empty.
- **Required** — every run supplies it.

Switching one is your decision, kept with its history like any other. You can also say it in
the conversation (*check my assemblies against the K-12 reference*), and the agent switches it
and says so; a switch the agent made on its own is marked as the AI's for review. The engine
never switches an input on by itself; it only makes one required when a later step needs what it
adds, and says why. If a tool's rules tie inputs together (QUAST reads a GFF only with a reference), switching
one brings the other, and the step says so.

## Inspect the aligner in the RNA-seq example

Using the shared [RNA-seq example](../../tutorials/rnaseq-example.md), select the aligner step. In the current
registry this is usually `STAR align` for 150 bp reads.

Read the step in three passes:

| Pass | What to check | Example |
|---|---|---|
| Ports | whether the step consumes and produces the right biological objects | reads and genome index in, BAM out |
| Settings | whether any value still needs a person | `seq_platform` may be unanswered |
| Reason | why this implementation was chosen | read length matched the STAR rule |

Check the evidence behind the selection and whether a different premise would change it.

## Canvas and artifact

The canvas is for working. The artifact is for review.

![Artifact view in the alpha builder](../../assets/screenshots/artifact-view-alpha.png)

When something looks surprising on the canvas, open **Artifact** and find the same step in
`pipeline.yml`. The artifact should name the selected contract, settings, decision tiers, and
provenance. If the app and artifact disagree, treat the artifact as the durable record and the
UI as suspect.

## Where the science enters

Tools, types, measurements, and rules come from the registry. If the builder cannot choose a
tool or asks a question the lab can answer with a rule, the fix usually belongs in the
[Registry](../../explanation/registry.md), not in a one-off graph edit.

For control and status definitions, see [Builder interface](../../reference/pipelines/builder-interface.md).
To answer a data question using a file, follow [Answer with a sample](answer-with-sample.md).

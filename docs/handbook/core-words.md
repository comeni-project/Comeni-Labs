# Core words

Comeni uses a few words in a precise way. Learn these before reading the deeper pages.

| Word | Plain meaning | RNA-seq example |
|---|---|---|
| Draft | the editable pipeline you see in the builder | the graph with Trim Galore, STAR, samtools, and featureCounts |
| Artifact | the saved record of the pipeline | the `pipeline.yml` that records every step and reason |
| Emitted files | Nextflow files generated from the artifact | `main.nf`, `nextflow.config`, and `modules/` |
| Gate | a check before trusting or submitting the artifact | lint the emitted workflow before launching it |
| Run | one execution of emitted files with local inputs | run the RNA-seq pipeline against FASTQs and references |
| Registry | the knowledge Comeni builds from | contracts, types, measurements, rules, and citations |

## Draft

A draft is the working copy. It belongs to the builder and can still be changed. Moving a step,
answering a question, or swapping a tool changes the draft.

The draft is useful because it is visual, but it is not the final record. Before Comeni can gate
or run it, the draft has to become an artifact.

## Artifact

An artifact is the durable pipeline record. It says which tools were selected, how they are
wired, what settings they use, and why those choices were made.

In practice, the artifact centers on `pipeline.yml`. If someone asks “what exactly did this
pipeline mean?”, the artifact is the answer.

## Emitted files

Comeni emits ordinary Nextflow files from the artifact:

| File | Job |
|---|---|
| `main.nf` | the workflow Nextflow executes |
| `nextflow.config` | profiles and run parameters |
| `modules/` | the tool code this workflow includes |

These files are why the output can leave the app. Comeni is the builder and reviewer; Nextflow
is the runtime.

## Gate

A gate is a check on an artifact. A lint gate can catch different problems from a test gate on
real data. A passed gate is evidence for the thing it checked, not a universal guarantee.

In the current alpha, the app's **Run** action performs the practical sequence for you: keep the
draft, run a lint gate, open the run sheet, and submit.

## Run

A run is one execution. The same artifact can have many runs with different input paths,
profiles, or execution environments.

This distinction matters: changing a run input is not the same thing as changing the pipeline
decision that selected STAR or featureCounts.

## Registry

The registry is the knowledge base behind the builder. It tells Comeni what tools exist, what
they consume and produce, what facts about data matter, and which rules justify choices.

For exact interface terms, use the [glossary](reference/glossary.md). For registry details,
start with [Registry](../registry/index.md).

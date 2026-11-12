# Running pipelines

Comeni builds a pipeline artifact; Nextflow runs it. The local alpha stack can launch a run
from the app, and the emitted files can also be taken to the environment where your lab already
runs Nextflow.

If the lifecycle terms are not clear yet, start with [Core words](../../explanation/pipeline-concepts.md).

```mermaid
flowchart TD
  A[Comeni builder] --> B[pipeline.yml]
  B --> C[Emitted Nextflow files]
  C --> D[main.nf]
  C --> E[nextflow.config]
  C --> F[modules/]
  D --> G[Nextflow runtime]
  E --> G
  F --> G
  G --> H[Laptop, HPC, Kubernetes, or cloud]
```

## Run from the app

In the builder, press **Run**. In the current alpha, that action:

1. keeps the current draft as an artifact,
2. runs the lint gate,
3. opens the run sheet for local input values,
4. submits the run to the local Wiener services.

Inputs and samplesheets are still an alpha surface. Expect this flow to become more polished
and more lab-aware before the API is treated as stable.

### When your samples differ

If you told the builder that a fact differs between your samples (strandedness, say), the run
sheet asks for it on each sample's row, offering only the values the pipeline accepts. Where the
pipeline can measure the fact itself, you may leave the cell blank, or choose *auto*, and it is
measured in the run. The pipeline checks every row before it processes any sample, and stops
naming the row, the sample and the column if a cell does not fit.

If you said some samples are paired-end and some single-end, leave a single-end sample's second
reads cell blank: the pipeline reads it as single-end, and passes it one file. After the run, the run page
says each value a setting took and where each fact behind it came from.

If you said a sample may span several rows (in *What was understood*, on the reads), give each
lane its own row with the same `sample` and its own `unit`. A one-lane sample may leave `unit`
blank. The pipeline merges each sample's lanes before anything reads them; a one-lane sample
passes straight on. Lanes of one sample that disagree, one paired and one single-end say, stop the
run naming the sample, and so does a repeated `sample` and `unit`.

The dedicated input model page is [Inputs in the alpha](../../explanation/inputs-and-data.md).

![Run sheet in the alpha app](../../assets/screenshots/run-sheet-alpha.png)

For the shared [RNA-seq example](../../tutorials/rnaseq-example.md), a local run needs paths like these:

| Input | Example |
|---|---|
| Paired reads | `data/*_R{1,2}.fastq.gz` |
| Genome FASTA | `reference/genome.fa` |
| Annotation GTF | `reference/genes.gtf` |

Those are run-time paths. They are not part of the scientific choice that selected STAR,
samtools, or featureCounts.

An input the pipeline takes as **optional** is marked *optional — leave empty to run without
it*. Leave it empty and the tool runs without it; supply it and you get what it adds. When
inputs depend on each other, the sheet says so before you start — *`gff` is used only with
`fasta`* — and holds **Start run** until the values agree. The pipeline checks the same rule
again when it starts, however it was launched.

## Current alpha behavior

| Step | What happens today |
|---|---|
| Keep | the current draft is written as a pipeline artifact |
| Lint gate | the app checks the artifact before submission |
| Run sheet | the app asks for local input values |
| Submit | the local run service launches Nextflow from the artifact |

## Expected to change

Input collection will likely become more structured. A lab should eventually be able to reuse
known sample sheets, project locations, and execution profiles instead of filling loose fields
each time.

The stable concept is the boundary: Comeni decides and records the pipeline before local paths
enter the run.

## Run as plain Nextflow

The artifact contains the Nextflow files and vendored modules needed to run outside the app.
That is the portability boundary: Comeni helps create and justify the workflow, while Nextflow
executes it on the target system.

For execution backends and production Nextflow configuration, use the official Nextflow and
Seqera documentation alongside the emitted files.

The app path does this for you locally. The equivalent shape outside the app is:

```bash
cd exported-pipeline
nextflow run main.nf -profile docker \
  --input 'data/*_R{1,2}.fastq.gz' \
  --fasta reference/genome.fa \
  --gtf reference/genes.gtf
```

Treat that command as illustrative. The exact parameter names come from the emitted
`nextflow.config` and the pipeline artifact you are running.

If you are handing the pipeline to someone else, hand over the artifact directory rather than a
memory of the builder screen. The artifact is the portable record.

## Before relying on a run

Run a gate appropriate to the evidence you need. A lint or preview gate checks different things
from a test gate on real data. A successful gate is evidence only for what that gate actually
exercised.

For the local containers and development commands, see [Local development stack](../development/local-stack.md).

Next: use [Watching runs](watch.md) to interpret what happens after submission.

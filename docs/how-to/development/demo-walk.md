---
title: Walk the demo
description: The everyday path of the redesign, from a question to a finished run, as a script to rehearse and present.
---

<!--
Serves: build, run.
-->

# Walk the demo

This is the script for showing Comeni end to end: a question, the person's own files, a pipeline
built and approved, a run with no form. It is also the closing check of the redesign's first plan
(`docs/superpowers/plans/2026-11-15-frontend-redesign-1.md`, Tasks 14 and 15). Walk it before
every presentation, and record anything that breaks in an issue, not around it.

The data is yeast RNA-seq from nf-core's test datasets. It is small, so a run finishes while you
talk. It is test data, not a laboratory's.

## Before you start

You need the local stack (`make dev`) and a model reached by your subscription or a key, under
**Settings → Models**. Without a model, every beat except the assistant's still works; see
[If something goes wrong](#if-something-goes-wrong).

Build the demo folder from the test data the stack keeps:

```bash
python3 tools/demo_data.py
```

This writes `.run/data/demo-yeast/` with `reads/` and `reference/`. Four samples (Y1 to Y4) are
paired-end reads; Y3 is cut to 50 bases, and Y4's read 2 is named `Y4_2.fq.gz`, which the default
reading rule does not pair. Those two faults are what *Check these* shows.

Start from a clean screen: open a private window at `http://localhost:5173/`, light theme, rail
expanded, browser at 1440 × 900.

## The script

Each beat lists what you do, what the audience should see, and the one sentence to say.

### 1. The question

**Do:** on Home, type *Count genes in my yeast RNA-seq samples* and press Enter.

**See:** a new analysis opens on **Data**. The rail shows it in the slot, with Data, Build and Run.

**Say:** *You start from what you want to find out, not from a tool.*

### 2. Your files, where they are

**Do:** in the rail's **Folders**, open `data`, then `demo-yeast`. Tick `reads`.

**See:** the scan counts up, then the Overview fills in. It shows tiles for 5 samples, 1 kind of
data and 8 files, and *What was measured*: paired reads, Phred+33, read length.

**Say:** *Comeni reads the files where they are, only the first few megabytes of each, and keeps
what it measured. Nothing is copied.*

### 3. Check these

**Do:** point at *Check these*.

**See:** two items:
- Y3's read length is 50, while the other samples have 101.
- Y4_R1 has no read 2, and `Y4_2.fq.gz` looks like it.

**Do:** press **Use Y4_2.fq.gz** on the second item, then **Leave out** on Y3.

**See:** Y4 becomes one paired sample. Y3 stays listed but greyed. Both changes are tagged YOU.

**Say:** *The rule that pairs files is shown, and every exception comes with its fix. Nothing
fails silently.*

### 4. Samples, and the rule

**Do:** open **Samples**.

**See:** the reading rule as examples (*Y1_R1.fastq.gz → sample Y1, read 1*), then the table, with
read 1, read 2 and the measured facts as columns.

**Say:** *The columns follow the data. A folder of assemblies would show one file and its N50
instead.*

### 5. The reference

**Do:** in **Folders**, tick `reference` too. Open **References**, and under **From a file**
add `genome.fasta` as `genome.fasta`, then `genes.gtf` as `annotation.gtf`.

**See:** both listed with their kinds. On **Files** they say *reference*, and they are not samples.

### 6. Build

**Do:** open **Build**.

**See:** the agent builds the pipeline in the Assistant tab: trimming, alignment, counting. The
canvas draws it, with per-sample steps marked ×3 and the reference shared.

**Do:** click the alignment step. In the **Step** tab, open *Advanced*, then press **Ask AI** on
one setting and accept the suggestion.

**See:** every value carries its source: MEASURED, RULE, DEFAULT, YOU or AI. The accepted
suggestion shows AI until you keep it.

**Say:** *The engine validates, routes and emits. The model chooses and explains, and every choice
it makes is marked for you to review.*

### 7. Run, with no form

**Do:** open **Run** and press **Run**.

**See:** no inputs form: the summary reads *3 samples, 1 reference*. The run starts, and
**Overview** shows N of M samples and the live pipeline.

**Say:** *Build connected the pipeline's inputs to the Data tables by type. No path was typed
anywhere.*

### 8. Watch it, and the results

**Do:** open **Steps**. Click the alignment step in the **Graph**, then switch to **Timeline**.

**See:** the step stays selected, and its tasks are listed under either view, one per sample.
When the run finishes, **Outputs** lists the count matrix and the QC report.

**Say:** *Two views of the same steps: how they connect and when they ran.*

## If something goes wrong

| What happens | What to do |
|---|---|
| The model is slow or answers oddly | Keep going: Data, the rule and the run do not need it. In Build, use **Add step** by hand. |
| The scan says it failed | Read its message. `MI0221` means the folder is outside `COMENI_DATA_ROOT`. |
| Run is disabled | Each missing input links to the Data page that fixes it; follow it. |
| A step fails | Open it in **Steps**: the failed task and its error are at the top. Show that, then rerun. |

## After the walk

Delete the analysis from Home so the next walk starts clean, and rebuild the folder with
`python3 tools/demo_data.py` if you changed it.

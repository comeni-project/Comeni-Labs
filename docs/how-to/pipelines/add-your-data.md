# Add your data

An analysis's data is the folders you tick on its **Data** page. Comeni reads the files where they
are and never copies them. It pairs them into samples and measures each one. The facts it
measures are what the pipeline is built from, and the same files are what a run reads. When the
agent asks for your data, its question links to Data.

The Data pages are being rebuilt (#511). Until they land, ticking folders is available through
the API (`PUT /api/data/{analysis}/folders`).

## Before you start

Your files must be under the folder this installation reads, `COMENI_DATA_ROOT` (see
[Install](../install.md#point-it-at-your-data)). A folder outside it is refused with `MI0221`.

## Tick the folders

1. Open the analysis's **Data** page.
2. In the rail's **Folders**, tick each folder that holds your files. A folder's own files are
   read, not its subfolders'. Tick those separately.
3. Wait for the scan. It reads the first 4 MB of each file, one sample at a time.

Files are paired by name (`_R1` and `_R2`, or `_1` and `_2`, any case, with Illumina's `_001`).
Any other file is a sample of its own, and a sample name met twice is numbered (`S1`, `S1#2`). A
link that leads outside the data folder is skipped, never followed.

## What the facts say

- **Where every sample agrees**, the value is the analysis's fact, marked *measured*.
- **Where they differ**, the fact *varies*. Each sample keeps its own value, for the run to use.
- **Where a sample did not measure it**, the fact stays open, and the agent asks you.
- **Your word stands over a measurement.** A fact you stated is not replaced by new data.
- **Facts follow the data.** Untick a folder, or tick another, and the facts change with it.
  Nothing has to be withdrawn.
- **A measured fact is a premise you check.** The steps that rest on it say so before you build.

FASTQ, plain or gzipped, is measured for read length, pairing and quality encoding. A file
nothing here reads is listed, and is not measured.

## What is kept

The analysis keeps the folders you ticked, each file's path, the samples by name and what was
measured on each, and deletes them with the analysis. Paths and sample names never enter the
pipeline file or a log. The agent's model may see sample names, so it can talk about your
samples. It never sees a path or a file's contents.

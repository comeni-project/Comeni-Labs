# Answer a data question with a sample

When the agent asks for your samples, choose the files in its question: one file per sample, or
both files of each paired sample, for as many samples as your study has.
Sample upload and model reading must be permitted by the installation protection level. Review
the resulting facts and their sources before continuing.

When the builder asks something about your data you can't answer, such as how long the reads
are, or whether you have a reference genome, you can answer with your files instead. Paired files
are matched by name (`_R1` and `_R2`, or `_1` and `_2`); any other file is a sample of its own.

## When your samples differ

Each sample is measured on its own and kept with the conversation, under its name, with what
was measured on it. *Current answers* lists every sample: filter by name, sort by a measurement,
or group by one to see how they spread.

- **Where every sample agrees**, the value is recorded, as for one sample.
- **Where they differ**, nothing is recorded for that fact, and the agent asks you or works from
  what else it knows. Showing the agent how the samples spread is tracked in #503.
- Sample names stay with the conversation and are deleted with it. They are never put in the
  pipeline or written to a log. At protection level 0 the agent's model may see them, so it can
  talk about your samples by name.

## What happens to each file


- The browser sends only the first 4 MB of each file. The inspection service reads
  that bounded sample in memory; the rest of the file stays on your computer.
  What was measured, and the agent's replies, are recorded. This is not a guarantee that no
  sample-derived text reaches storage.
- **A file this server knows how to read is measured.** FASTQ, plain or gzipped, is measured for
  read length, pairing and quality encoding. Each fact says *measured*, by what, and on how many
  reads.
- **A file nothing here reads is not measured.** Having the AI read such a file is planned as an
  agent tool (#501).
- **Your word stands over a measurement.** A fact you already gave is not replaced by an upload.
- **A fact read by AI or measured is a premise you check.** The steps that rest on it are yellow:
  *check the premise* before you build.

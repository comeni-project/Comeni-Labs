# Answer a data question with a sample

Open the waiting data question in the authoring conversation, then choose your samples' files:
one file per sample, or both files of each paired sample, for as many samples as your study has.
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
- **Where they differ**, the question says how: *Your uploads differ: 150 in 480 samples, 75 in
  20.* It proposes an answer for you to confirm. Where the fact can differ per sample, the
  proposal is *It differs between samples*, and each sample's value then comes from its row of
  the run's samplesheet. Where it cannot yet, such as the read length that chooses the aligner,
  the question is which value to build for, and the most common is proposed.
- Sample names stay with the conversation and are deleted with it. They are never put in the
  pipeline, sent to a model, or written to a log; the model sees only how the values spread.

## What happens to each file


- The browser sends only the first 4 MB of each file. The inspection service reads
  that bounded sample in memory; the rest of the file stays on your computer.
  Model characterisation can put an excerpt in the job queue, and model replies are
  recorded. This is not a guarantee that no sample-derived text reaches storage.
- **A file this server knows how to read is measured.** FASTQ, plain or gzipped, is measured for
  read length, pairing and quality encoding. Each fact says *measured*, by what, and on how many
  reads.
- **A file nothing here reads goes to the AI**, as at most 8 KB and 200 lines of its text, and only at the
  protection level that allows it. The AI says which kind of file it is, from the kinds this
  registry knows. It may name only properties that a line of the file states, quoting that line,
  and each quote is checked against the file. Everything it reads is labelled **read by AI**.
  When it names a kind of file this server measures (a FASTQ named `.txt`, say), the file is sent
  again by itself and measured.
- If the sample conflicts with a known answer, review the difference and choose
  which answer to retain. The observation does not automatically replace it.
- **A fact read by AI or measured is a premise you check.** The steps that rest on it are yellow:
  *check the premise* before you build.

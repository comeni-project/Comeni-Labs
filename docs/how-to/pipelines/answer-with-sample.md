# Answer a data question with a sample

Open the waiting data question in the authoring conversation, then choose a sample file
or an R1/R2 pair. Sample upload and model reading must be permitted by the installation
protection level. Review the resulting facts and their sources before continuing.

When the builder asks something about your data you can't answer, such as how long the reads
are, or whether you have a reference genome, you can answer with a file instead: one file, or a
pair (R1 and R2).

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

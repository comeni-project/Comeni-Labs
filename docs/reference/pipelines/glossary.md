# Glossary

Interface terms, with links to the relevant schemas and procedures.

### contract

**What a tool takes, what it gives, and how to call it** — one declared file per tool, in the
registry. It is a hand-written FFI binding to a Nextflow module: `mendel build` refuses to emit
if a contract disagrees with the module it describes.

Read [`contract-schema.md`](../registry/contract-schema.md).

### type

**A semantic name for a thing that flows between tools** — `alignment.bam`, `genome.fasta`,
`fastq.reads`. Not a file format: nf-core declares both a sorted and an unsorted BAM as
`type: file, *.bam`, and *sorted* exists only in the English description. The type, and the
**states** it carries, are the missing meaning routing depends on.

Types are **closed**: a contract naming an undeclared one fails to load. Read
[`vocabulary-schema.md`](../registry/vocabulary-schema.md).

### role

**The job a tool does in a pipeline** — `sort_bam`, `align_reads`, `index_building`. A judgement
about how this registry partitions work, not a fact about the tool, which is why a tool's own
documentation cannot answer it.

Rules target a role rather than a tool, so a rule keeps working when a better tool arrives.

### measurement

**Something observed about the data, that a rule may read** — read length, strandedness, how
many samples. Measurements are declared and cited. An `assertion_only` measurement is stated
by a person rather than produced by a tool.

Read [`measurement-schema.md`](../registry/measurement-schema.md).

### proposal

**Nothing declared fits, so somebody proposed a new one.** Vocabularies are closed, so a type or
role that does not exist cannot simply be typed into a contract — it enters as a proposal on the
question that needed it, and a named person approves, renames or rejects it.

That is invariant 2 in the small: a person or a model proposes, a human approves, and nothing is
written to the registry automatically.

# Glossary

Eight words the interface uses. Each is one sentence and a link to the page that defines it
fully — this file is for the moment you are looking at a screen and do not know what it is
saying, not for learning the system.

**It exists because the person who co-designed Mendel could not read its own interface.** That
was the verdict on 2026-08-19, and it was correct: every screen was written for somebody who had
already read [`ARCHITECTURE.md`](../../ARCHITECTURE.md). Nothing in the product defined
*contract*, *role*, *type*, *measurement*, *drift*, *hole*, *band* or *proposal*, and all eight
appear on screen without explanation.

The frontend renders these same eight through `<Term>`, and a test asserts the two lists match in
**both directions** — a word on screen with no entry here, and an entry here nothing uses, are
both defects. Same shape as the diagnostics guard.

---

### contract

**What a tool takes, what it gives, and how to call it** — one declared file per tool, in the
registry. It is a hand-written FFI binding to a Nextflow module: `mendel build` refuses to emit
if a contract disagrees with the module it describes.

Read [`contract-schema.md`](contract-schema.md).

### type

**A semantic name for a thing that flows between tools** — `alignment.bam`, `genome.fasta`,
`fastq.reads`. Not a file format: nf-core declares both a sorted and an unsorted BAM as
`type: file, *.bam`, and *sorted* exists only in the English description. The type, and the
**states** it carries, are the missing meaning routing depends on.

Types are **closed**: a contract naming an undeclared one fails to load. Read
[`vocabulary-schema.md`](vocabulary-schema.md).

### role

**The job a tool does in a pipeline** — `sort_bam`, `align_reads`, `index_building`. A judgement
about how this registry partitions work, not a fact about the tool, which is why a tool's own
documentation cannot answer it and why the forge shows you which other contracts already declare
each role.

Rules target a role rather than a tool, so a rule keeps working when a better tool arrives.

### measurement

**Something observed about the data, that a rule may read** — read length, strandedness, how
many samples. Declared, cited, and each says whether a tool can actually produce it: five of the
first six turned out to be `assertion_only`, meaning a person states them and no tool measures
them.

Read [`measurement-schema.md`](measurement-schema.md).

### drift

**The source says something the contract does not.** A contract was true when it was written and
its module has since changed — a new parameter, a renamed output, a different container. Drift is
the only thing in the forge that *breaks something already working*, which is why it is the one
kind of work rendered in coral.

Accepting drift rewrites the contract to match its source and records that it happened.

### hole

**A field the forge could not derive, so a person must fill it.** Drafting a tool reads its
module and fills in what is stated as fact — the process name, the container, the port names —
and opens a hole for everything that is a judgement. A hole carries what it is asking, why a
person rather than a rule is being asked, and which declared values it will accept.

### band

**How much a piece of work costs if it waits** — not how likely it is to matter. Drift blocks
because it breaks something that works; an open question waits because somebody is held up; an
undrafted tool is idle because it is an opportunity nobody is waiting on.

The queue is ordered by band, worst first.

### proposal

**Nothing declared fits, so somebody proposed a new one.** Vocabularies are closed, so a type or
role that does not exist cannot simply be typed into a contract — it enters as a proposal on the
question that needed it, and a named person approves, renames or rejects it.

That is invariant 2 in the small: the forge proposes, a human approves, and nothing is written to
the registry automatically.

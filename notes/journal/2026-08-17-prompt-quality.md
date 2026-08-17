# 2026-08-17 — the forge's first real model run, and what it found

The fourth entry today, and the first one written from **measurements rather than reasoning**.
[`2026-08-17-forge-phase-2.md`](2026-08-17-forge-phase-2.md) shipped a model behind the forge's
`HoleFiller` seam with every test green and a model that had never once been called. This entry
is what happened when one was.

## Where things stand

**A local model now fills the forge's holes, and it is measurably good at it.** `gemma3:12b`
over Ollama on a consumer GPU re-derives the shipped nf-core contracts at **90%** of scored
fields, up from **69%** before the fixes below. `make verify` is green.

**The plumbing works, and invariant 13 has evidence behind it for the first time.** *"Self-hosted
is not a degraded tier"* has been asserted since the design documents and never checked. It is
now: same `LiteLLMTransport`, same `ModelAccess`, same code path, only `base_url` differs. ROCm
picked up a gfx1102 card with no override, and the first real call returned a validated `Choice`.

**No counts are repeated here.** `make check` counts the tests, `make residue` counts guard
coverage. The accuracy figures above are the spike's, and the spike is throwaway.

## The method, because it is reusable and the numbers are worthless without it

For every shipped nf-core contract, draft the same tool from its vendored module, fill the holes
with a model, and diff against the contract a human wrote and approved. **The registry is the
ground truth**, and that is only possible because Phase 1 made the forge able to re-derive a
shipped contract from its source.

Two limits, stated rather than buried:

- **Ten contracts is a small set**, and two of them (`comeni/`) have no adapter that can re-read
  them, so eight tools carry the measurement.
- **90% is a tuned number.** `multiqc` and `subread/featurecounts` were held out of the fixing
  loop precisely so an unfitted figure exists, and scoring them is the next thing to do.

## What the first run found: every defect was ours

**69%, and `star/align` failed completely** — twenty-nine holes, twenty-nine declines, fifty
minutes. The temptation is to read that as "a 12B model cannot do this". Reading the prompts said
otherwise.

**1. The question never said which port it was about.** A hole read *"a value for
produces[0].type_id"* and carried every port's documentation. `fastqc` has three outputs, so its
three prompts differed only in an index digit — and got three identical answers.

The decisive evidence is on `hisat2/build`: the model answered **`gtf`** for `consumes[1].name`
and then **`genome.index.hisat2`** for `consumes[1].type_id`. It identified the port correctly
and we discarded that between two independent calls. The emit name was already derived and
sitting in the same scaffold.

**2. The evidence was a Python `repr` of parsed YAML.** `'FastQC report'` and `*.html` were in
there, wrapped in nested quotes, `\n` escapes and Groovy-map noise. No model picked them out —
every `fastqc` output was answered `fastq.reads`, which is the type its *description* mentions.

**3. The instruction came before the evidence.** Survivable at 3,000 characters and fatal at
14,000: given `star/align`'s stringified output block, the model answered by **explaining the
YAML**. Not a refusal, not a parse failure — a different question, answered well.

Two smaller ones. `Hole.why_open` was never sent, and it is where the scaffold explains the
judgement — for a port name it says the contract's name and the module's channel name are
different choices, which is exactly what three misses got wrong. And nothing told a list-valued
hole to prefer a small answer.

## What the fixes bought

| | before | after |
|---|---|---|
| scored accuracy | 69% | **90%** |
| `star/align` | 29 declines, 3000s | scores, 227s |
| `star/align` prompt | 14,706 chars | 1,841 |

Every miss caused by *"the question did not say which port"* is gone, including both
`consumes[1]` cases where the model had contradicted itself between two calls.

## The four survivors, and what they are

- **`samtools/index consumes[0].name`** — `input` (the module's channel) rather than `bam` (the
  contract's port). The rename convention, which `why_open` now explains and which still loses.
- **`samtools/index roles`** — `index_building` rather than `bam_indexing`. Both are declared
  roles and a person could pick wrong. This is judgement, and it is what review is for.
- **`star/align roles`** and **`trimgalore roles`** — both *over-selection*: the right value plus
  a plausible extra (`bam_sorting`, `qc_per_sample`). The "choose the smallest set" instruction
  helped less than hoped.

**Three of four are `roles`.** If there is a next lever, it is there and not in type inference.

## A fifth miss that was not one, caught before it was written down

`star/align produces[0].type_id` scored as a miss — model `qc.report`, human `alignment.bam`.
**It was the spike's own bug.** The contract declares one output port (`bam`); the draft creates
one per emit channel, and STAR's first emit is `log_final`. Different ports, compared by index.

Checking it before publishing changed the number (88% → 90%) and removed the only apparent
type-inference failure. It also turned up something worth more than the correction: asked to
type a STAR **log file** from twenty-two declared types, the model answered `qc.report` — which
is arguably the best available answer, because **there is no correct one**.

## Two design questions this run raised, which are not prompt problems

Recorded here because they are real and neither is fixed.

**`choose_one` cannot say "none of these fit".** `choose_many` can return an empty list — 'none
of these' is a legal answer there — but a single-valued closed choice can only pick or fail
validation. So the honest answer is unavailable, and *"no declared type fits this port"* becomes
a wrong pick instead of a signal. That signal is exactly what invariant 7's approval queue
exists to consume: it means the vocabulary needs a new type.

**The forge drafts a port hole per emit channel, and a contract legitimately declares a subset.**
`star/align` emits nineteen; the shipped contract declares one, because the other eighteen have
no declared type and invariant 7 is closed. So the forge asks eighteen questions with no legal
answer. The human was not wrong to declare one — the *forge* is wrong to ask about all nineteen,
and nothing records which ports were deliberately omitted, so `forge check` cannot tell "not
modelled yet" from "missing".

## What a fresh reader gets wrong

**"The model was bad."** It was not. Where the evidence was readable and the question identified
its subject, a 12B model on a consumer GPU answered correctly — including every input type on
`hisat2/align` and `hisat2/build`. The three defects above were all ours, and all of them were
invisible to a suite of 1143 passing tests.

**"A green suite meant Phase 2 worked."** Phase 2's tests assert that a validated answer comes
back and that an invalid one is declined. **Not one of them asked whether the question was
answerable.** That is the gap this run closed, and it is the same lesson as Phase 1's hand-run
one level deeper: run the thing, and read what it actually sends.

## What is next

The two held-out tools, then the survivors, then the design questions above. The rule drafter
([`notes/README.md`](../README.md) row 16) still follows, and it inherits `generate(shape)` and
this prompt shape — which is the whole argument for having measured them first.

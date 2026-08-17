# 2026-08-17 — searching the prompt design, and what it cost to learn

The fifth entry today, and the one most worth keeping: it records a **search** rather than a
result. Eight configurations were measured against a local model; three of them were worse than
where we started, and none of that is derivable from the code afterwards. Without this file
somebody re-runs every one of them.

Read [`2026-08-17-prompt-quality.md`](2026-08-17-prompt-quality.md) first — it is where the
method comes from.

## Where things stand

**`gemma3:12b` re-derives the shipped nf-core contracts at 86–88%**, up from 69% before any of
this. `mendel-ai` samples at temperature 0 now, so a re-run of the same draft gives the same
answer. `make check` is green.

**The remaining misses look like a floor set by the data, not by the prompt** — see §What is
left. That judgement is why the search stopped rather than continued.

## The method, and the two limits that matter

Draft every shipped nf-core contract from its vendored module, fill the holes with a model, diff
against the contract a human approved. **The registry is the ground truth**, which is only
possible because Phase 1 made a shipped contract re-derivable.

- **Ten contracts, eight of them carrying the measurement.** Small.
- **Every shipped contract has valid types by construction**, so "nothing in the vocabulary fits"
  cannot appear in this test set at all. The case the forge exists for is invisible to it.

## The results, and why most of the differences are not real

| # | configuration | scored | result |
|---|---|---|---|
| 1 | baseline | 29/42 | **69%** — `star/align` declined all 29 holes in 50 minutes |
| 2 | port identity in the question, readable evidence, instruction last | 38/42 | **90%** |
| 3 | + name candidates from type segments, + proposals | 43/50 | **86%** |
| 4 | + registry exemplars on candidates | 44/50 | **88%** |
| 5 | + reorder candidates, + sibling ports as evidence | 40/50 | **80%** |
| 6 | + drop segments, + open the name field | 38/50 | **76%** |
| 7 | drop segments, keep the field closed | 43/50 | **86%** |

**Rows 3 onward have a larger denominator than rows 1–2**, because `star/align` began scoring
instead of failing outright. 86% over 50 fields is more work done than 90% over 42, and the raw
percentages across that boundary are not comparable.

**And nothing set the sampling temperature until after row 7.** Every run above sampled at the
provider's default, so:

- **69% → 88% is real.** Far outside any plausible noise band.
- **The 76% and 80% dips are probably real.** Six to ten points.
- **86% versus 88% is not distinguishable from noise.** Three fields apart, one model, random
  sampling. Conclusions drawn from that gap during the session — "dropping segments cost two
  points" — were reading dice.

That was found by asking what the numbers would look like if the thing being feared were true,
which is the same move that caught three other defects today.

## What generalises — the durable findings

These are the ones to carry into the rule drafter, which inherits `generate(shape)` and this
prompt shape.

1. **Name the subject in the question.** `produces[0].type_id` carrying every port's
   documentation is a question that does not say which port it is about; `fastqc`'s three
   outputs got prompts differing only in an index digit and three identical answers.
2. **Evidence must be readable.** `str(dict)` of parsed YAML buried `'FastQC report'` in
   Groovy-map noise, and no model picked it out.
3. **Instruction last, and say that nothing but JSON is wanted.** At ~13,000 characters the model
   answered by *explaining the documentation* instead of choosing.
4. **A derived fact beats an instruction.** "Every contract in this registry declares exactly one
   role" fixed every over-selection. "Choose the smallest set that is true" had fixed none.
5. **Ground the model in the registry's own data.** A role is a judgement about the registry, so
   the registry is the only thing that can answer it — naming which contracts already use each
   role and type is the evidence the tool's documentation cannot provide.
6. **Do not invent candidates.** Offer names humans chose, not strings derived from an id.
7. **Answers already in the draft are evidence.** A port asked about in isolation while its
   siblings' answers sit unused beside it is the defect that started all of this, and it recurred
   twice more at different levels.

## The negative results — do not re-run these

Each cost a measurement to establish, and none is visible in the code that remains.

- **Type segments as candidates are a net loss.** Splitting `fastq.reads` into `fastq` and
  `reads` made three unwinnable ports winnable and broke five that were right: the model takes
  the *namespace* segment — `fastq`, `genome`, `annotation`, `star` — which reads like a name and
  is almost never the one a person picked.
- **Position bias was not the cause of the name misses.** Reordering so the right answer led
  changed nothing: `reads` was listed first and `fastq` was still chosen. The pull is semantic.
- **Opening the name field is worse than closing it — 76%, the worst configuration measured.**
  Unconstrained, the model answers with a category word (`genome`, `annotation`, `alignment`) or
  with the type id itself (`fastq.reads`), never the specific name a person chose. This was worth
  testing: `PortName` is a shape alias with no closed set behind it, so closing it *is* stricter
  than the type system requires. It is still what works.
- **Search would not help the one type miss.** `samtools/index`'s input is a BAM and the model
  says `alignment.bai`. Everything a search could surface — the process name `SAMTOOLS_INDEX`,
  the output `*.bai`, the script `samtools index`, `meta.yml`'s `"input file"` — points at the
  wrong answer. The only line that decides it is the one-line description, which the prompt
  already carries.

## What is left, and why it looks like a floor

- **`multiqc consumes[0].name`** wants `reports`. The only other `qc.report` port in the registry
  is `fastqc`'s, and it is named `zip` — after its emit channel. **The registry's own convention
  is 24/30**, and one of the six exceptions sits exactly where the model needs to learn it.
- **Three `annotation.gtf` ports** want `gtf`; the model says `annotation`. Both are real: the
  registry uses `gtf` twice and `annotation` once for the same type.
- **`samtools/index consumes[0].type_id`** — the direction confusion above.

Two of the three are the registry disagreeing with itself. **No prompt fixes that**, and whether
to make the naming consistent is a decision about the data rather than about the model.

## The process finding, which may outlast the technical ones

**Six defects were found today. Three were in the measurement, not the product**: ports matched
by index rather than by name, proposals vanishing from the denominator so an over-proposing model
would score higher, and unset sampling temperature. A fourth — a contract citing itself as its
own exemplar — would have inflated every subsequent figure.

All four would have produced *plausible numbers*. None would have failed a test.

**A measurement harness is production code.** It was treated as scaffolding for most of a day,
and it was the least reliable thing in the loop.

## What is next

Brainstorming, tomorrow, rather than more tuning — the operator's call, and the right one: the
remaining gap is the registry's own inconsistency and a small model's ceiling, and grinding
prompt variants against sampling noise measures neither.

**The cold modules are still the untested case.** `samtools/faidx`, `bedtools/sort` and
`picard/markduplicates` are vendored and have no contracts, so nothing in this entry's numbers
covers the situation the forge actually exists for: a tool whose types are not in the vocabulary
yet. That is where the proposal path gets exercised for real, and there is no ground truth there —
so the report will be a judgement, and must say so.

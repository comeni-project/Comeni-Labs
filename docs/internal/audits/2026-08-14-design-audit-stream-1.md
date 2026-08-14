# Design audit — Stream 1: the claim, end to end

**Reviewer:** cold, no session context. **Block:** A76–A89 (A76–A86 used).
**Date:** 2026-08-14. **Tree:** worktree off `main` @ `346eeac`.
**Brief:** `docs/internal/audits/2026-08-14-design-audit-brief.md`, § Stream 1.

Baseline established before any finding: `make verify` **green** — 608 fast + 3 slow + 27 guards,
`ruff check` clean, exit 0. Every finding below was produced by ordinary use of the shipped
verbs against the shipped registry, with no attack and no code change. Experiment directories
are preserved under `audit-tmp/` (12 MB, untracked) and named per finding.

The claim under test:

> Same goal in → same pipeline out, and nothing was guessed silently.

**Verdict for this stream: it holds with named repairs.** "Same goal in → same pipeline out" is
sound and I could not break it. "Nothing was guessed silently" is not yet earned: two of the four
tiers cannot state their own justification, the one place a human supplies a judgement has nowhere
to record why, and one verb deletes an explanation without saying so.

---

## Findings

| # | What | Shape | Severity | Verdict |
|---|---|---|---|---|
| A76 | tier 2 is "a documented default exists" and the design has nowhere to put the document; an overlay changes a value from 0 to 30 with a byte-identical `why` | (ii) | **critical** | CONFIRMED |
| A77 | a human's tier-4 answer has nowhere to record its reason, and `mendel upgrade` silently deletes a hand-written `why.reason`, restoring "selected the first of 1 candidates without judgement" under `source: human` | (i)+(ii) | **critical** | CONFIRMED |
| A78 | a tier-3 rule with no `cite` and no `because` loads, fires, and emits a reason ending in a bare colon | (i) | important | CONFIRMED |
| A79 | `Pin.because()` prefers a block `cite` over a row `because`; the **shipped** registry therefore cites the STAR paper as the reason HISAT2 was chosen | (i) | important | CONFIRMED |
| A80 | `channels[].meta` carries the measured facts — including the one that becomes featureCounts' `-s` — with no `why` of any kind, and drops the citation the measurement declares | (ii) | important | CONFIRMED |
| A81 | positional literals reach the tool with `why: null`; `SAMTOOLS_SORT(…, 'bai')` and `STAR_ALIGN(…, false)` are real choices in no review queue. The schema reference documents a `literal` + `why` the registry cannot produce | (i) | important | CONFIRMED |
| A82 | `ext_args` reaches the tool with no `why`, deliberately — and its justifying premise is graph-contingent. One goal edit removes TrimGalore and `--readFilesCommand zcat` survives | (i)+(ii) | important | CONFIRMED |
| A83 | tier 4 labels "two defensible options" and "nobody ever wrote a default" identically; emptiness is reported to the user as ambiguity | (ii) | important | CONFIRMED |
| A84 | `RouteStep.satisfies` is discarded at materialisation, so a structural insertion's reason is "the only contract that produces this" with no referent | (ii) | important | CONFIRMED |
| A85 | the review count double-counts a tied module selection — 2 open questions printed as 3 | (i) | minor | CONFIRMED |
| A86 | a contract displaced by module key leaves `why.displaced_layer: null` on the step it displaced; a *rule* overlay records it | (i) | minor | CONFIRMED |

Two independent arrivals at known issues are recorded under **Confirmations of known issues**, not
as findings: issue #1 (routing ties) and issue #2 (tier 3 over asserted measurements).

---

## A76 — tier 2 promises a document the design cannot hold. **Critical. CONFIRMED. Shape (ii).**

`CLAUDE.md` and `ARCHITECTURE.md` §4 both define tier 2 as *"a documented default exists"*.
Nothing in the data model can hold that document.

Both routes into tier 2 carry a bare value:

- `Param.default: Any` (`comeni_core/contract.py`) — no `cite`, no `because`, no `from_layer`.
  `resolve._resolve_param` emits `reason=f"contract default for {param_name}"`.
- `ModuleContract.priority: int` — no `cite`, no `because`. `router._choose` emits
  `reason=f"registry priority {p}, over {…}"`.

Both sentences name **who** settled it and say nothing about **why**, which is the brief's
definition of a circular reason.

### Demonstration

The shipped spine (`audit-tmp/base/pipeline.yml`):

```yaml
  - name: min_mqs
    value: 0
    why: {tier: 2, source: resolver, reason: contract default for min_mqs,
          from_layer: null, displaced_layer: null}
```

The justification for `0` does exist — it is a **YAML comment** in
`registry/contracts/nf-core/subread-featurecounts.yml`: *"0 is featureCounts' own documented
default, so declaring it changes no number."* That is precisely the document tier 2 names, and it
is dropped at parse. Nothing that reaches a reader carries it.

Now an ordinary overlay. `audit-tmp/lab/` is a one-file layer identical to the base contract
except `default: 30`:

```
$ uv run mendel build --goal examples/rnaseq-goal.yml \
    --registry registry/ --registry audit-tmp/lab --out audit-tmp/overlay
1 overlay reroute(s) …
  OVERLAY  contracts: nf-core/subread/featurecounts@2.0.6 from acme-lab over …
5 modules, 1 requiring review

$ diff audit-tmp/base/pipeline.yml audit-tmp/overlay/pipeline.yml
-    value: 0
+    value: 30
```

The `why:` block is **byte-identical between the two builds**. `-Q 0` (keep everything) and
`-Q 30` (discard multi-mappers and most low-confidence alignments) are materially different
analyses, and the file's own explanation of both is the same seven words. `from_layer` reads
`null` in both, while the `step` twelve lines above correctly reads `from_layer: acme-lab` — so
the field designed to answer "which layer decided this value" is null exactly where it matters.
`registry.displaced` does record the contract swap, so the fact is recoverable by a reader who
knows that `min_mqs` lives on that contract; it is not *stated*.

A secondary consequence of the same shape: the tier-2 branch is `if default is not None`, so a
contract cannot declare "the documented default is *nothing*". Such a parameter falls to tier 4
permanently and joins the required-review queue (see A83).

### What it would take

`Param` and `ModuleContract.priority` need a `because`/`cite` the way `Decision` has one, and
`_resolve_param`/`_choose` need to carry it into `Why.reason` and `Why.from_layer`. Tier 3 already
proves the shape works. Until then, half the tier ladder answers "why" with "because".

---

## A77 — a human judgement has nowhere to record its reason, and `upgrade` deletes the one a person writes. **Critical. CONFIRMED. Shape (i) + (ii).**

Tier 4 is the honesty mechanism (invariant 6) and the declared difference from a chat window.
It is the one tier where a *person* supplies the answer. There is no field in which that person
can say why.

`settings[].value` is the documented writable home of the answer
(`docs/reference/pipeline-schema.md`, *Answering a tier-4 question is editing this file*).
`ParamDecision.human_override` is a bare value. `Setting.why.reason` is derived from the
resolver's `Resolution.reason` on every re-materialisation.

### Demonstration, in four ordinary steps

**1. Build and answer**, exactly as the reference documents it:

```
$ uv run mendel build --goal examples/rnaseq-goal.yml --out audit-tmp/base
  REVIEW  star_align.seq_platform
$ cp -r audit-tmp/base audit-tmp/answer
$ sed -i 's/^    value: null$/    value: illumina/' audit-tmp/answer/pipeline.yml
$ uv run mendel emit audit-tmp/answer/pipeline.yml --out audit-tmp/answer
MD0213: … has changed since the Nextflow was generated from it. Regenerating.
```

The value reaches the tool (`nextflow.config`: `ext.args = { "… 'PL:illumina'" }`). Good.

**2. Read what the artifact now says.** `audit-tmp/answer-up/pipeline.yml`, after the documented
`upgrade` that promotes the answer to `source: human`:

```yaml
  - name: seq_platform
    value: illumina
    why:
      tier: 4
      source: human
      reason: no rule covered 'seq_platform'; selected the first of 1 candidates
        without judgement — please review
```

`source: human` and *"selected the first of 1 candidates without judgement"* in the same record.
The reason describes what the flag-only resolver did **before** a person answered. The published
artifact tells a stranger that a value a human chose was picked without judgement, and asks them
to review something already reviewed.

**3. Write down the real reason**, in the only free-text field that exists, in a file whose first
line is *"Read it; edit it"*:

```yaml
      reason: our sequencer is an Illumina NovaSeq X; lab SOP BIOINF-014
```

`mendel emit` honours it — it is the file.

**4. Run `mendel upgrade`**, the documented verb for re-resolving against a moved registry, which
`CLAUDE.md` says "replays every recorded decision":

```
$ uv run mendel upgrade audit-tmp/reasoned/pipeline.yml --out audit-tmp/reasoned-up
the generated pipeline is byte-identical to the one recorded
1 decisions replayed, 0 newly asked
1 tier-4 question(s) answered by a human — still tier 4, and still recorded:
  ANSWERED star_align.seq_platform = 'illumina'
5 modules, 0 requiring review

$ grep NovaSeq audit-tmp/reasoned-up/pipeline.yml
(nothing)
```

The sentence is gone, replaced by the machine's non-reason, with **no diagnostic**. `upgrade`
reports success on every axis it measures.

### Why the existing machinery cannot catch this

Everything `upgrade` compares is the *generated code*: `main.nf` and `nextflow.config` are
byte-identical, the decision replayed, the digests agree. The only thing lost is the
**explanation**, and the explanation is the product. `diff_ir`, `MD0213`, `MD0214` and
`emitted.files` are all blind to it by construction — a design-level blindness, not a bug.

This is also a second instance of round two's root G, one level over from A55: `why.reason` is
simultaneously generated output and a field a human is invited to edit, and the design has never
declared which. (Stream 3 owns root G; I record the overlap rather than claiming it.)

### What it would take

A `Setting`-level field a human writes and no verb regenerates — the natural spelling is
`human_reason` beside `human_override` on `ParamDecision`, replayed the way the value already is,
and rendered into `Why.reason` in place of the resolver's sentence when `source: human`.
Alternatively `Why` gains a second, never-derived `note`. Either is small; the absence is not.

---

## A78 — a tier-3 rule needs no citation to load or to fire. **Important. CONFIRMED. Shape (i).**

Tier 3 is the differentiating tier: yellow rather than silent precisely because "a rule match is
only as good as the measurement behind it" — the reader is asked to check the premise, and the
citation is the premise. `Decision.cite`, `Decision.because`, `DecisionRow.cite` and
`DecisionRow.because` are all `str | None = None`, and `rules._validate` checks five other
properties and never this one.

### Demonstration

`audit-tmp/nocite/rules/aligner.yml` — a lawful overlay rule block with no justification:

```yaml
decisions:
  - decides: {producer_of: alignment.bam}
    rows:
      - {when: {read_length: ">= 70"}, then: nf-core/hisat2/align@2.2.2}
      - {when: {read_length: "< 70"},  then: nf-core/star/align@1.11.0}
```

```
$ uv run mendel build --goal examples/rnaseq-goal.yml \
    --registry registry/ --registry audit-tmp/nocite --out audit-tmp/nocite-build
5 modules, 1 requiring review
```

Exit 0, no warning. `audit-tmp/nocite-build/pipeline.yml`:

```yaml
  why:
    tier: 3
    source: resolver
    reason: 'rule producer_of:alignment.bam matched {''read_length'': ''>= 70''}: '
```

The reason terminates in a colon and nothing. The aligner — the most consequential module choice
in an RNA-seq pipeline — was changed by an installed layer, labelled *data-profiled*, given review
level *advisory*, and justified by an empty string. A reviewer skimming for red sees yellow.

Secondary, same line: `matched {'read_length': '>= 70'}` is a Python `dict` repr in the file a
bench scientist is told to read. `{…}` and the doubled quotes are Mendel's internals surfacing in
the artifact.

### What it would take

One clause in `rules._validate`: a `Decision` must carry a `cite` or a `because`, and so must
every row that does not inherit one (see A79). The message can say what the author may write, as
the other five checks already do. The cost is that the shipped registry's own block already
complies, so this rejects nothing that exists.

---

## A79 — the shipped registry cites the STAR paper as the reason HISAT2 was chosen. **Important. CONFIRMED. Shape (i).**

`Pin.because()` (`mendel_resolver/rules.py`) documents itself as *"The most specific justification
available, row before block"* and implements:

```python
return self.row.cite or self.decision.cite or self.row.because or self.decision.because or ""
```

That is **cite before because**, not row before block. Two consequences, both live.

### Demonstration 1 — the shipped registry, one goal edit

`registry/rules/rnaseq.yml` carries a block-level `cite: "Dobin et al. 2013,
doi:10.1093/bioinformatics/bts635"` — the STAR paper — over two rows, one of which selects HISAT2.

```
$ sed 's/read_length: 150/read_length: 60/' examples/rnaseq-goal.yml > audit-tmp/goal-rl60.yml
$ uv run mendel build --goal audit-tmp/goal-rl60.yml --out audit-tmp/rl60
5 modules, 1 requiring review
  REVIEW  hisat2_align.seq_platform
```

`audit-tmp/rl60/pipeline.yml`:

```yaml
- id: hisat2_align
  why:
    tier: 3
    reason: 'rule producer_of:alignment.bam matched {''read_length'': ''< 70''}:
      Dobin et al. 2013, doi:10.1093/bioinformatics/bts635'
```

A reader who follows that DOI reads *"STAR: ultrafast universal RNA-seq aligner"* and finds
nothing about HISAT2 at all. The brief asked for a `why` a stranger could act on; this is one a
stranger would act on and be misled by. It ships today, in the only rule the registry contains,
reachable by changing one number in the example goal.

### Demonstration 2 — a row's own justification is unreachable

`audit-tmp/rowbecause/rules/aligner.yml` gives each row an explicit `because` and the block a
`cite`:

```yaml
    cite: "Dobin et al. 2013, doi:10.1093/bioinformatics/bts635"
    rows:
      - when: {read_length: ">= 70"}
        then: nf-core/star/align@1.11.0
        because: "STAR's seed-extend search is designed for long reads"
```

```
$ uv run mendel build --goal examples/rnaseq-goal.yml \
    --registry registry/ --registry audit-tmp/rowbecause --out audit-tmp/rowb
$ grep -A4 'tier: 3' audit-tmp/rowb/pipeline.yml
    reason: 'rule producer_of:alignment.bam matched …: Dobin et al. 2013, doi:…'
```

The row's sentence never appears. Nor does the block's own `because` ("read length determines
which aligner is appropriate") — the field that explains **the question** is discarded whenever
any `cite` exists, so the artifact shows a bare DOI and never a sentence. A row-level `cite` does
win when present (verified in `audit-tmp/rowb60`), which is the only path to a correct attribution
and is optional.

### What it would take

Make the fallback lexical rather than field-typed — row's `because`+`cite` first, block's only if
the row has neither — and render both a sentence and a citation rather than one or the other. Then
make a rule's justification mandatory (A78), at which point the borrowing that produces the false
attribution stops being needed.

---

## A80 — the most consequential value in the pipeline is the one with no `why`. **Important. CONFIRMED. Shape (ii).**

`ARCHITECTURE.md` §5a records a deliberate decision: *"Measured facts do not go through `via:` at
all."* `strandedness: reverse` rides in `channels[].meta` and featureCounts contains its own
translation to `-s 2`. The reasoning is sound and I do not dispute it.

The consequence, which the decision did not examine, is that those facts also do not go through
`why:`. `MetaEntry` is:

```python
class MetaEntry(BaseModel):
    key: NfIdentifier
    value: ParamValue
```

Two fields. No tier, no source, no reason, no layer.

### Demonstration

`audit-tmp/base/pipeline.yml`:

```yaml
channels:
- type_id: fastq.reads
  meta:
  - {key: single_end, value: false}
  - {key: strandedness, value: reverse}
```

Getting `strandedness` wrong is the classic way to produce a counts matrix that is quietly
mostly zeroes; `tests/test_counts.py` exists because of it. It is the single value in this file
with the largest effect on the result, and it is the only value in the file that carries no
provenance whatsoever.

Two things are lost that the registry already holds:

- `registry/measurements/strandedness.yml` declares
  `cite: "Signal et al. 2022, doi:10.1186/s12859-022-04572-7"`. It reaches no artifact.
- `single_end: false` is `paired: true` inverted, declared honestly as data in
  `registry/measurements/paired.yml` (`meta_key`/`meta_values`). The artifact shows only the
  inverted result. A reader who wrote `paired: true` and finds `single_end: false` must work out
  that these are the same fact spelled inside out.

Also unstated: **which step reads it.** `meta` is attached to the entry channel, and nothing says
that `SUBREAD_FEATURECOUNTS` is what turns it into `-s 2`. A biologist cannot discover from
`pipeline.yml` that this pipeline will run stranded counting.

### What it would take

`MetaEntry` gains a `why: Why` — tier 3 or tier 1 depending on `ValueSource`, `source` copied from
`Measured.source` (which already distinguishes `goal` from `measured`), `reason` from the
measurement's `description` and `cite`. Everything needed is already declared; nothing is carried.

---

## A81 — two real decisions reach the tools as bare positional literals with `why: null`. **Important. CONFIRMED. Shape (i).**

`docs/reference/pipeline-schema.md` states the rule plainly: *"A literal and an empty placeholder
each carry a `why`: a positional choice is a decision"* — and shows an example:

```yaml
      - {literal: false, why: {tier: 1, source: resolver,
                               reason: "no GTF-free splice-junction path in this spine"}}
```

The shipped registry cannot produce that. `audit-tmp/base/pipeline.yml`:

```yaml
- id: star_align
  call:
  - {ports: [], literal: false, empty_width: null, why: null}
- id: samtools_sort
  call:
  - {ports: [], literal: null, empty_width: 3, why: {tier: 1, …, reason: the reference is
      only needed to write CRAM; this emits BAM}}
  - {ports: [], literal: bai, empty_width: null, why: null}
```

The `empty_width` placeholder has its `why` — because `NfInput.empty` **requires** a `because`.
Both literals have `why: null`, because nothing requires one for a literal.

What those literals are, read out of the vendored modules:

- `vendor/modules/nf-core/star/align/main.nf`: `val star_ignore_sjdbgtf`. `false` means *use the
  GTF to build splice junctions*. This is a methodological choice about annotation-guided
  alignment.
- `vendor/modules/nf-core/samtools/sort/main.nf`: `val index_format`. `'bai'` selects BAI over
  CSI. BAI cannot index a reference sequence longer than 512 Mbp, so this silently constrains
  which genomes the pipeline works on.

Both appear in `main.nf` as bare tokens:

```groovy
STAR_ALIGN(TRIMGALORE.out.reads, STAR_GENOMEGENERATE.out.index, ch_annotation_gtf, false)
SAMTOOLS_SORT(STAR_ALIGN.out.bam, Channel.value([[:], [], []]), 'bai')
```

Neither is in `decisions:`, neither is in `needs_review()`, neither carries a tier. The mechanism
exists and is unused: `pipeline._call` already reads `spec.because` for **any** `NfInput`, so
adding `because:` beside `literal:` in the contract materialises a `Why` today. Nothing requires
it, and the shipped registry supplies it for zero of two literals.

### What it would take

`NfInput` validator: `because` required whenever `literal` is set, exactly as it already is for
`empty`. The argument that carried `empty` — that two different situations looked identical in
YAML and in the emitted Groovy, and `-stub-run` cannot tell them apart — applies verbatim to
`literal`, which is likewise invisible to every gate.

---

## A82 — `ext_args` reaches the tool with no `why`, and its recorded premise is graph-contingent. **Important. CONFIRMED. Shape (i) + (ii).**

`Step.ext_args` is documented as deliberate:

> Not a `Setting`: nothing resolved it and there is no decision behind it, so giving it a `why`
> would invent provenance.

I engage that argument rather than restating it. It conflates *tier* with *reason*. The docstring
itself supplies the reason in the next breath — "`--readFilesCommand zcat` because TrimGalore
emits `.fq.gz` and STAR cannot read gzip" — and the contract author wrote the same sentence as a
YAML comment. Recording it would not invent provenance; it would copy a sentence that already
exists. What does not exist is a tier, and `Why` requires one, so "no tier" forced "no reason".

The stronger half is that the premise is a fact about **this graph**, and the contract is static.

### Demonstration

One goal edit — a laboratory declaring its reads are already trimmed, which
`docs/reference/goal-schema.md` documents as the supported way to skip the trimmer:

```yaml
have:
  - type_id: fastq.reads
    states: [trimmed]
```

```
$ uv run mendel build --goal audit-tmp/goal-trimmed.yml --out audit-tmp/trimmed
4 modules, 1 requiring review
```

TrimGalore is gone. `--readFilesCommand zcat` is not:

```
$ grep withName audit-tmp/trimmed/nextflow.config
    withName: STAR_ALIGN { ext.args = '--readFilesCommand zcat' }
$ grep STAR_ALIGN audit-tmp/trimmed/main.nf
    STAR_ALIGN(ch_fastq_reads, STAR_GENOMEGENERATE.out.index, ch_annotation_gtf, false)
```

STAR now reads the laboratory's own files directly, and is unconditionally told to decompress
them. The flag's justification — the only place it is written down — names a module that is not
in this pipeline. Nothing in `pipeline.yml` states the flag's reason, so nothing can notice it has
stopped being true, and no gate can: `--gate test` uses gzipped nf-core test data, so the premise
holds under test and may not hold in the laboratory. (That an uncompressed input would then fail
at run time is **PLAUSIBLE** — `zcat` on a non-gzip file errors — and I did not run it. The
provenance defect is CONFIRMED independently of the runtime consequence.)

This is a recorded reason that has since stopped being true, which the brief names as the good
kind of finding.

### What it would take

Either `Step.ext_args` becomes a list of fragments each with a `because` (tier 1, source
`resolver`, reason from the contract), or `ModuleContract.ext_args` gains a `because` and `Why`
gains the ability to carry a reason without asserting a tier. The graph-contingency needs more:
a fragment whose premise is "an upstream module produced this format" is a claim about an
*edge*, and there is currently no way to say so.

---

## A83 — tier 4 labels emptiness as ambiguity. **Important. CONFIRMED. Shape (ii).**

`CLAUDE.md` draws the distinction itself, in *Gotchas*:

> **Emptiness and deadness are different problems.** Few parameters and no defaults is
> *emptiness*, and it is the forge's job […] A resolved value reaching no tool is *deadness*.

The tier ladder has a label for deadness (issue #10, closed by `via:`) and none for emptiness. A
parameter that nothing decided because the question is genuinely open, and a parameter that
nothing decided because nobody has yet written a default, both exit at tier 4 with review level
`required`.

### Demonstration — the two are indistinguishable in output

A genuine routing ambiguity, produced by an overlay that raises HISAT2's priority to STAR's and a
goal that has not measured read length (`audit-tmp/tie/`, `audit-tmp/goal-nolen.yml`):

```
$ uv run mendel build --goal audit-tmp/goal-nolen.yml \
    --registry registry/ --registry audit-tmp/tie --out audit-tmp/tiebuild
5 modules, 3 requiring review
  REVIEW  hisat2_align.seq_platform
  REVIEW  hisat2_align (module)
  REVIEW  hisat2_align.producer:alignment.bam
```

Both kinds of tier 4 in one build. In `decisions:` they differ in exactly one field:

```yaml
- key: hisat2_align.seq_platform          # emptiness
  tier: 4, resolved_by: flag-only, confidence: 0.0
  candidates: [null]
  chosen: null
- key: hisat2_align.producer:alignment.bam # genuine ambiguity
  tier: 4, resolved_by: flag-only, confidence: 0.0
  candidates: [nf-core/hisat2/align@2.2.2, nf-core/star/align@1.11.0]
  chosen: nf-core/hisat2/align@2.2.2
```

Same tier, same review level, same `resolved_by`, same confidence, same `REVIEW` line. The only
signal is that `candidates` is `[null]` — a "choice" among one option that is nothing — and the
reason sentence, *"selected the first of 1 candidates without judgement"*, is a description of a
choice that did not occur.

### Why it matters more later, not less

The registry today holds one under-specified parameter and produces one such flag. The forge's
declared job is to draft contracts from nf-core `meta.yml`, which types parameters and rarely
supplies defensible defaults. Every one of those becomes a `required`-review tier-4 entry. The
mechanism that makes tier 4 meaningful — invariant 6, *always flagged, even at high model
confidence* — is the mechanism that will fill the queue with non-decisions, and a queue that cries
wolf is the failure mode `cli.py` already argues against for `ANSWERED` and `OVERLAY`.

**Partly known, and I say so:** that `Param` has no declared domain is recorded in `resolve.py`
under A33 and deferred to Plan 2 Task 11, which is about making the tier-4 site's fallback
symmetric. What is not recorded is the *partition* consequence — that with a domain or without
one, "unfilled" is not "ambiguous", and the four tiers have nowhere to say so. A fifth state, or a
`ParamDecision` sub-kind, is a design decision Plan 2 will otherwise make by accident.

---

## A84 — "the only contract that produces this" does not say what "this" is. **Important. CONFIRMED. Shape (ii).**

The most natural question a bench scientist asks of a pipeline is *why is this step here*. For
four of the five steps in the shipped spine, `pipeline.yml` answers:

```yaml
- id: trimgalore
  why: {tier: 1, source: resolver, reason: the only contract that produces this, …}
```

The referent is missing. The router knows it — `RouteStep.satisfies` holds the type id, and
`satisfy()` is called with the exact `(type_id, states)` that forced the insertion — but
`satisfies` appears nowhere outside `router.py`:

```
$ grep -rn "satisfies" packages/comeni-core/src packages/mendel-compiler/src
(two unrelated matches in docstrings)
```

It is dropped between `RoutePlan` and `PipelineIR`, so the artifact cannot say *"inserted to
produce `fastq.reads[trimmed]`, required by `star_align.reads`"* — which is the whole answer, and
one sentence long.

A reader can reconstruct it by scanning every other step's `inputs[].source` for a reference back.
That is a join, and the file exists to remove joins: *"the answer sits beside the value instead of
in a decision record you had to join by hand."*

### What it would take

Thread `RouteStep.satisfies` (and the requesting node/port, which `satisfy()` also has in hand)
onto `IRNode.selection` and render it into `Why.reason`. No new concept, one field, and it turns
the majority of the spine's reasons from a tautology into a sentence.

---

## A85 — the review count over-reports open questions. **Minor. CONFIRMED. Shape (i).**

From the tie build above: `5 modules, 3 requiring review`, listing `hisat2_align (module)` and
`hisat2_align.producer:alignment.bam`. These are **one** decision — the module selection and the
`ProducerDecision` recording it. There are two open questions and the headline says three.

`ir.needs_review()` carries a de-duplication guard, `decision.key not in flagged`, which works for
parameters (`ParamAsked.key()` is `node.subject`, matching the parameter spelling) and can never
fire for a producer, because the node spelling is `f"{node.id} (module)"` and the record's key is
`f"{node.id}.producer:{type}"`. The two lines are deliberate and documented — *"a reviewer reading
'which modules need looking at' should not have to join the two"* — and I do not dispute the two
lines. The **count** is a different claim, and it is the number a reviewer carries away.

Fix: count distinct decisions, list both spellings.

---

## A86 — a shadowed contract leaves no per-step displacement record. **Minor. CONFIRMED. Shape (i).**

`Why.displaced_layer` is documented as *"Set when a lower layer offered something this one beat."*
In the A76 overlay build, the base `subread/featurecounts` contract was offered by a lower layer
and beaten — by module-key shadowing rather than by ranking — and the step reads:

```yaml
- id: subread_featurecounts
  why: {…, from_layer: acme-lab, displaced_layer: null}
```

`router._displaced_layer` reads `candidates` after shadowing has already removed the loser from
the registry, so nothing was "beaten" in its sense. The asymmetry is the finding: a **rule**
overlay does record it per step (`audit-tmp/nocite-build/pipeline.yml`:
`displaced_layer: comeni-registry-examples`), a **contract** overlay does not, and both are
invariant 11's "never let an installed overlay reroute a pipeline silently".

Severity is minor because `registry.displaced` and the `OVERLAY` block both report the event
correctly; a reader consulting the per-step field alone is the one misled.

---

## Confirmations of known issues

Recorded as confirmations, not findings, per the brief.

**Issue #1 — routing ties should ask a human.** Reached from the ordinary-use direction. With two
equally-ranked aligners the build emits a complete, runnable `main.nf` that silently uses
HISAT2 (first by id), prints `REVIEW`, and exits 0. Nothing stops the pipeline being run before
the tie is looked at. `audit-tmp/tiebuild/`. The design's own posture — *"a tie is ambiguity, not a
coin flip"* — is honoured in the record and not in the control flow.

**Issue #2 — `sealed` must block tier-3 decisions on asserted measurements.** Reached the same
way. `examples/rnaseq-goal.yml` asserts `read_length: 150` with `source: goal`; the aligner choice
is labelled tier 3 *data-profiled*, review level *advisory*, on a number a person typed. One
addition worth carrying into `ProfilePolicy`: the step's `why.reason` says *"matched read_length
>= 70"* and does not say the read length was asserted rather than measured. The provenance is in
`goal.profile.measurements[].source` — a different section, and a join. Even after `sealed` blocks
it, `guarded` will still print a sentence that reads as though something was measured.

---

## Clean — attacked and held

Each of these was attacked with the intent of breaking it, and did not break.

**Determinism (invariant 10) holds, including for `pipeline.yml` itself.** Four builds of the
shipped goal — same process, and `PYTHONHASHSEED` 1 and 98765 — produced byte-identical
`main.nf`, `nextflow.config` **and** `pipeline.yml`:

```
76355bbf…  audit-tmp/{base,det1,det2,det3}/main.nf
e55a67f7…  audit-tmp/{base,det1,det2,det3}/pipeline.yml
```

The claim is stronger than `ARCHITECTURE.md` §8 states: the artifact digest is stable too, not
only the generated code.

**"Same goal in → same pipeline out" survives re-spelling the goal.** Permuting `have:` and
`profile:` key order (`audit-tmp/goal-reorder.yml`) produced a byte-identical `main.nf`. The
`pipeline.yml` differed only in the echoed goal and therefore in `from_digest` — correct
behaviour: the file records what was asked, and it was asked differently.

**One goal edit moves what it should and nothing else, twice over.** Changing `strandedness:
reverse` to `forward` changed exactly two lines outside digests: the goal echo and
`channels[].meta`. Changing `read_length: 150` to `60` flipped the aligner and — correctly and
structurally — the index builder that feeds it, dropped the port the new aligner does not consume,
and changed nothing else. Both diffs are in `audit-tmp/` and both are readable end to end. This is
the part of the claim the design most clearly earns.

**A note on that second diff, which I checked and cleared:** flipping to HISAT2 also drops the
GTF from the aligner's inputs and replaces it with an empty splice-sites channel. That looked at
first like a material change nobody asked for, and it is one — but it is *stated*, in the
`empty_width: 2` call argument with `why.reason: "splicesites are optional;
HISAT2_EXTRACTSPLICESITES is not vendored"`. The design recorded exactly the thing I went looking
for. (What it does not do is attach a citation to the choice that caused it — that is A79, not
this.)

**The overlay machinery reports itself.** A private layer replacing a contract printed an
`OVERLAY` block, populated `registry.displaced` with kind, key, winning and displaced layer, and
set the step's `from_layer` correctly. Invariant 11's "never silently" holds at the layer level;
A76 and A86 are about the *value* and *step* levels beneath it.

**Invariant 8 holds as written.** A genuine tie produced an `Ambiguity`, a `DecisionRecord` with
both real candidates, a tier-4 `IRNode.selection`, and a `REVIEW` line. No coin flip, and the
record names what was on the table.

**The tier-4 answer round trip works.** `settings[].value` → `emit` → the flag reaches
`nextflow.config`; `upgrade` replays it, promotes it to `source: human`, prints `ANSWERED`, and
takes the review count to zero. A46's two-homes defect is genuinely closed. A77 is about the
*reason*, not the value — the value path is sound.

**`emit` needs no registry and refuses divergence.** `MD0213` fired on every hand-edited
`pipeline.yml` I re-emitted, named the right file, and cured itself. I could not get a stale
`main.nf` past it.

**The measurement-to-`meta` translation is declared data, not compiler knowledge.** I went looking
for a hardcoded `paired → single_end` inversion in the emitter and found it declared in
`registry/measurements/paired.yml` as `meta_key` + `meta_values`. The `ARCHITECTURE.md` claim that
the compiler has no built-in idea what a FASTQ is holds at this point. (That the translation is
not *explained* in the artifact is A80.)

**No free text and no path escaped into the goal or the artifact.** I did not attack the egress
guards — out of scope — but every artifact I produced was checked by eye for laboratory paths and
identifiers, and `pipeline.yml` carries layer names rather than paths throughout, as invariant 15
requires.

---

## Verdict

**It holds with named repairs.**

The reproducibility half of the claim is earned. "Same goal in → same pipeline out" survived
every ordinary-use attack I could construct: hash seeds, re-spellings, one-thing-changed edits,
overlays, and the answer round trip. The diffs are minimal and readable, and where a change
propagated it propagated for a stated structural reason.

The explanation half is not yet earned, and the gap is systematic rather than incidental. Ranked
by what a repair buys:

1. **A77** — give a human somewhere to say why, and stop `upgrade` deleting it. Without this the
   one tier that exists to be honest publishes a sentence that contradicts its own `source` field.
2. **A76** — tier 2 must be able to cite its document, or stop claiming one. Half the ladder
   currently answers "why" with "because".
3. **A78 + A79** — make a tier-3 justification mandatory and stop a block's citation being
   borrowed by a row it does not justify. The shipped registry emits a false attribution today.
4. **A80, A81, A82, A84** — four values that reach a tool with no reason, each with a cheap fix
   and each already holding the information it needs somewhere upstream.
5. **A83** — decide, before the forge fills the registry, whether "nobody wrote a default" is
   tier 4. It is a design decision that will otherwise be made by accident.

None of these requires a different architecture. Every one is a field that does not exist, or a
sentence that is discarded between the stage that knows it and the file that should carry it —
which is the same shape the four guard rounds kept finding one level down, and is the reason this
audit exists.

---

## Artifacts left behind

`audit-tmp/` in this worktree, 12 MB, untracked. Nothing in it is expensive to recreate, but the
hand-written layers are the slow part:

| Path | What |
|---|---|
| `goal-*.yml` | five goal variants: `rl60`, `fwd`, `trimmed`, `reorder`, `nolen` |
| `base/` `det1..3/` | the baseline and the three determinism builds |
| `rl60/` `fwd/` `trimmed/` `reorder/` | the one-thing-changed builds |
| `lab/` + `overlay/` | **A76** — the layer changing `min_mqs` default, and its build |
| `nocite/` + `nocite-build/` | **A78** — the uncited rule layer and its build |
| `rowbecause/` + `rowb/` `rowb60/` | **A79** — the row-`because` layer and both branches |
| `tie/` + `tiebuild/` | **A83**, issue #1 — the priority-tie layer and its build |
| `answer/` `answer-up/` `reasoned/` `reasoned-up/` | **A77** — the four-step answer-and-lose-the-reason sequence |

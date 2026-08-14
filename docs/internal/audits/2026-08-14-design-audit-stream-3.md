# Design audit — Stream 3: the artifact as the interface

**Findings A104–A117.** Cold reviewer, no session context. Run 2026-08-14 against `main`
(`346eeac`) in a worktree. Brief: `docs/internal/audits/2026-08-14-design-audit-brief.md`.

Baseline established before anything was attacked: `make verify` **green, exit 0** — 608 fast
tests, the 3 slow `test_counts.py` tests, 27 guards, `ruff check` clean. Every finding below was
produced by running the shipped verbs on real files. Experiment files are under
`audit-tmp/` in this worktree — see *What was left behind*.

---

## Findings

| # | Severity | Shape | What | Status |
|---|---|---|---|---|
| **A104** | **Critical** | (i) | A hand-edited `settings[].value` keeps the `why:` written for the value it replaced. `min_mqs` edited 0→30 emits `-Q 30` and still reads `tier: 2, source: resolver, reason: contract default for min_mqs`. `mendel publish` certifies it, exit 0. | **CONFIRMED** |
| **A105** | High | (i)+(ii) | `emit` and `upgrade` build **different pipelines from the same file** — `-Q 30` vs `-Q 0` — and neither says a human's edit was discarded. Only a tier-4 answer is durable, and nothing in the artifact says which values those are. | **CONFIRMED** |
| **A106** | High | (i)+(ii) | Five of the seven values that reach the generated Nextflow carry **no `why:` at all**, against the file's own header. Two of the three flags the repo advertises as proof of the claim (`-s 2`, `-p`) are among them. | **CONFIRMED** |
| **A107** | High | (i) | The registry's only plain-English explanation of its only tier-3 decision **never reaches the artifact**: `Pin.because()` prefers `cite` over `because`, so authoring a citation deletes the sentence. | **CONFIRMED** |
| **A108** | High | (ii) | Tier 3 is `advisory` — "check the premise" — and the artifact carries no premise. The measured value, whether it was *measured* or *asserted*, and the branch not taken are all absent from the step's `why:`. `ReviewLevel.ADVISORY` is consumed by nothing. | **CONFIRMED** |
| **A109** | Medium | (i) | Root G, second instance: `steps[].inputs[].states` reads three ways — the producer's emitted states, an unset default, and (to a reader) the port's requirement. The shipped spine cannot distinguish them. | **CONFIRMED** |
| **A110** | Medium | (ii)+(iii) | `decisions[].confidence` is undocumented in the artifact's own spec, has no null, and `0.0` means both "never filled in" and "no confidence". Plan 2 puts a model behind that number. | **CONFIRMED** (spec gap) / **PLAUSIBLE** (Plan 2 consequence) |
| **A111** | Medium | (i) | After `upgrade` replays a person's answer, `why.source: human` sits on `why.reason: "…selected the first of 1 candidates without judgement — please review"`. The **recorded reason** for carrying the reason verbatim has stopped being true. | **CONFIRMED** |
| **A112** | Medium | (ii) | `decisions[].human_override` reads two ways: `pipeline-schema.md` says it is not writable and is derived; `MD0220`'s message says *"Set the decision's human_override to the value"* and refuses the honest edit otherwise. | **CONFIRMED** |
| **A113** | Low | (i) | Tier-1 `reason: "the only contract that produces this"` is a claim about registry contents wearing the tier CLAUDE.md defines as *"no choice exists — inputs force it"*. | **CONFIRMED** |
| **A114** | Low | (ii) | `mendel publish` — the door with no undo — never mentions an open tier-4 review. A pipeline with `chosen: null` is stamped and exits 0. | **CONFIRMED** |

Numbers **A115–A117** are unused.

---

## A104 — an edited value keeps the reason written for the value it replaced

**Critical. Shape (i): the claim breaks. CONFIRMED.**

`docs/reference/pipeline-schema.md` line 3: *"This is the pipeline. **Read it, edit it**, and
rebuild the Nextflow from it."* No line in that document restricts editing to tier-4 settings.

### Demonstration

```bash
uv run mendel build --goal examples/rnaseq-goal.yml --out audit-tmp/b1 --gate lint
cp -r audit-tmp/b1 audit-tmp/b13-mqs
# edit exactly one character: min_mqs 0 -> 30
uv run mendel emit audit-tmp/b13-mqs/pipeline.yml --out audit-tmp/b13-mqs
```

`audit-tmp/b13-mqs/nextflow.config`:

```groovy
withName: SUBREAD_FEATURECOUNTS { ext.args = '-Q 30' }
```

`audit-tmp/b13-mqs/pipeline.yml`, unchanged beside it:

```yaml
  - name: min_mqs
    value: 30
    via: ext
    key: args
    template: -Q {value}
    why:
      tier: 2
      source: resolver
      reason: contract default for min_mqs
```

All three lines of that `why:` are now false. The tier is not 2 — no convention settled 30.
The source is not the resolver. And 30 is not any contract's default:
`registry/contracts/nf-core/subread-featurecounts.yml` declares `default: 0`, with a comment
saying *"0 is featureCounts' own documented default"*.

Then:

```bash
uv run mendel publish audit-tmp/b13-mqs/pipeline.yml --gate lint   # gate lint: PASS, exit 0
```

The door with no undo certified an artifact that positively asserts a false provenance for a
value that changes the result — featureCounts discards every read below MAPQ 30, so the counts
matrix is materially different from the one the file claims to describe.

### Why this is a design finding and not a bug

The design **already has** the concept of cross-checking a value against its recorded
provenance — that is exactly what `MD0218` and `MD0220` do. Both are scoped to `ParamDecision`,
and a `ParamDecision` exists only for a tier-4 ambiguity. So the check is present on the values
that are flagged for review and absent on every value that is not.

Worse, the guard runs in the wrong direction. `MD0220` refuses a reader who *overstates* human
involvement (`source: human` with no recorded answer). Nothing refuses a reader who
*understates* it — a human's number wearing a machine's justification. For a product whose claim
is "nothing was guessed silently", understating is the dangerous direction: the reader of a
published `pipeline.yml` is told a convention decided something a person made up.

`emitted.from_digest` does not catch it: `emit` recomputes it. `emitted.files[].digest` does not
catch it: the bytes on disk are exactly what was written.

### Named repair

`Why` has no field that could detect the divergence, so this is also shape (ii). The cheapest
fix needs no registry, which matters because `emit` has none by design: give `Why` a
`for_value:` — the value the reason was written about — and refuse at load when
`settings[].value` differs from it. That turns every value in the file into the tier-4 case
that already works, and it is a load check, so it fires on all four verbs.

---

## A105 — `emit` and `upgrade` build different pipelines from the same file

**High. Shape (i) with a shape-(ii) rider. CONFIRMED.**

Continuing from A104's `audit-tmp/b13-mqs`:

```bash
uv run mendel upgrade audit-tmp/b13-mqs/pipeline.yml --out audit-tmp/b13-up
```

```
the generated pipeline differs: nextflow.config
  CHANGED   subread_featurecounts.min_mqs: 30 -> 0  (tier 2) contract default for min_mqs
1 decisions replayed, 0 newly asked
5 modules, 1 requiring review
```

exit **0**. `audit-tmp/b13-up/nextflow.config` carries `-Q 0`.

So one `pipeline.yml` produces `-Q 30` under `emit` and `-Q 0` under `upgrade`. The `CHANGED`
line reads as *the registry moved* — it is the same wording `upgrade` uses when a contract
genuinely changes — and there is no `ORPHANED`, no `STALE`, no non-zero exit. A person who
edited a number, emitted, ran the pipeline, and then upgraded a month later has silently lost
the edit and been told about it in the vocabulary of registry drift.

The behaviour is defensible on its own terms: `upgrade` re-resolves from the goal, and only a
recorded `human_override` survives. But `human_override` lives on a `DecisionRecord`, and a
`DecisionRecord` exists only for an ambiguity. **A tier-1, tier-2 or tier-3 value has nowhere in
the artifact to be marked as a human's override** — that is the shape-(ii) half. A laboratory
that wants MAPQ 30 must change the goal or overlay the contract; the artifact invites them to
edit the file instead, and then quietly declines to remember.

Nothing in `pipeline.yml` or in `pipeline-schema.md` distinguishes a durable value from a
volatile one. Five settings in the shipped spine are identical in shape; the only discriminator
is `why.tier`, whose documented meaning is *how it was settled*, not *whether your edit
survives*.

---

## A106 — five of the seven values that reach the tool carry no `why:`

**High. Shape (i), with shape (ii) for two of the five. CONFIRMED.**

The generated file's own header, written by `mendel build`:

> Every value carries a `why:` — the tier it exited at, who settled it, which registry layer
> it came from, and the citation behind it. **That is the point of the file.**

Every value in `audit-tmp/b1` that reaches the generated Nextflow:

| value | where it lands in the emitted pipeline | carries a `why:`? |
|---|---|---|
| `--readFilesCommand zcat` | `withName: STAR_ALIGN { ext.args = … }` | **no** |
| `false` | `STAR_ALIGN(reads, index, gtf, false)` | **no** |
| `'bai'` | `SAMTOOLS_SORT(bam, …, 'bai')` | **no** |
| `single_end: false` | `meta` → featureCounts `-p` | **no** |
| `strandedness: reverse` | `meta` → featureCounts `-s 2` | **no** |
| `min_mqs: 0` | `SUBREAD_FEATURECOUNTS { ext.args = '-Q 0' }` | yes (tier 2) |
| `empty_width: 3` | `SAMTOOLS_SORT(…, Channel.value([[:],[],[]]))` | yes (tier 1) |

Two of seven. `CLAUDE.md` advertises the shipped spine as *"featureCounts invoked with
`-s 2 -p -Q 0`"* — the proof that the machinery works. Two of those three flags travel through
`channels[].meta`, the one part of the artifact with no provenance at all.

### The sharpest case: `single_end`

`vendor/modules/nf-core/subread/featurecounts/main.nf:24`:

```groovy
def paired_end = meta.single_end ? '' : '-p'
```

`registry/measurements/paired.yml` declares `meta_key: single_end` and a value inversion
(`{when: true, then: false}`). So the goal's `paired: true` becomes the artifact's
`single_end: false`. On the page a reader sees, 250 lines apart:

```yaml
    - measurement: paired
      value: true          # goal.profile
...
  meta:
  - key: single_end
    value: false           # channels[]
```

Those read as a contradiction. They are the same fact, spelled inside out by a declared
translation the artifact never mentions. `MetaEntry` has exactly two fields, `key` and `value`
(`pipeline.py:151`) — there is nowhere to say which measurement produced it, or that it was
inverted. Shape (ii).

### `ext_args` — the recorded reason, engaged

`Step.ext_args`' docstring records the decision: *"Not a `Setting`: nothing resolved it and there
is no decision behind it, so giving it a `why` would invent provenance."* `ModuleContract.ext_args`
adds: *"Carries no tier, deliberately. A tier is for a decision. Labelling this tier 1 would be
defensible and would dilute what a tier means."*

Three arguments against, in the design's own terms:

1. **The product claim is not "every *decision* traces"** — it is *"every decision in it can be
   traced to **a constraint**, a convention, a measurement, or an explicitly flagged judgement
   call"* (`docs/design/mendel.md` §1). A constraint-forced value is the *first* item on that
   list, and tier 1 is where the design puts it: "no choice exists — inputs force it".
   `--readFilesCommand zcat` is exactly that, and the design already gives that class a `Why`
   everywhere else.
2. **The design already contradicts itself one field over.** `NfInput.empty` gets a `because`,
   materialised into a tier-1 `Why` with `source: resolver`. That value — an empty placeholder —
   is no more a decision than `ext_args` is. Two structurally identical facts about how a module
   is called; one carries provenance, one does not.
3. **The reason exists and is written down where the biologist will never see it.** The
   explanation is in a YAML comment in `registry/contracts/nf-core/star-align.yml`:
   *"TrimGalore emits .fq.gz and STAR reads plain text unless told otherwise."* Comments do not
   survive parsing. The reader who needs it gets `ext_args: --readFilesCommand zcat`.

### `call[].literal` — the mechanism exists and nothing requires it

`CallArg.why`'s docstring: *"'every choice carries its provenance' cannot have an exception for
the one route that had no artifact."* `pipeline-schema.md` agrees: *"A literal and an empty
placeholder **each** carry a `why`."* Its worked example shows
`{literal: false, why: {tier: 1, source: resolver, reason: "no GTF-free splice-junction path in
this spine"}}`.

The shipped spine has neither. `star_align` writes `literal: false, why: null`; `samtools_sort`
writes `literal: bai, why: null`. The guard in `tests/test_runnable.py:82` is
`if spec.empty and not spec.because` — literals are outside it, and `NfInput.because`'s own
docstring scopes itself to `empty` (*"Why `empty` is empty"*).

The `false` is not cosmetic: it is STAR's `ignore_sjdbGTFfile` positional, and flipping it
changes whether the GTF is used for splice junctions — an RNA-seq result, not a formatting
detail. The artifact does not name it, type it, or explain it.

**Proof the mechanism works and only the data is missing** — an overlay adding a `because` to
the literal (`audit-tmp/lab-because/`):

```bash
uv run mendel build --goal examples/rnaseq-goal.yml \
  --registry registry --registry audit-tmp/lab-because --out audit-tmp/b9-because --gate lint
```

```yaml
  - ports: []
    literal: bai
    why:
      tier: 1
      source: resolver
      reason: samtools sort writes a .bai companion index; CSI is for contigs over 512 Mb
```

Named repair: widen `test_runnable.py`'s condition from `spec.empty` to
`spec.empty or spec.literal is not None`, and author the four missing sentences. Roughly an hour.

---

## A107 — authoring a citation deletes the plain-English reason

**High. Shape (i). CONFIRMED.**

`registry/rules/rnaseq.yml` — the entire tier-3 surface of the shipped registry — is authored
with both halves of an explanation:

```yaml
  - decides: {producer_of: alignment.bam}
    because: "read length determines which aligner is appropriate"
    cite: "Dobin et al. 2013, doi:10.1093/bioinformatics/bts635"
```

The `because:` is the sentence a bench scientist can act on. It never reaches the artifact.
`audit-tmp/b1/pipeline.yml`:

```yaml
    reason: 'rule producer_of:alignment.bam matched {''read_length'': ''>= 70''}: Dobin et al. 2013,
      doi:10.1093/bioinformatics/bts635'
```

`mendel_resolver/rules.py:137` — a method named `because()` that returns the citation:

```python
    def because(self) -> str:
        """The most specific justification available, row before block."""
        return (
            self.row.cite or self.decision.cite
            or self.row.because or self.decision.because or ""
        )
```

`cite` outranks `because` unconditionally, so any rule authored to the standard the design asks
for — with a citation — loses its prose.

**Demonstration** (`audit-tmp/layer-nocite/registry-copy/`, the registry with `cite:` deleted):

```bash
uv run mendel build --goal examples/rnaseq-goal.yml \
  --registry audit-tmp/layer-nocite/registry-copy --out audit-tmp/b4-nocite --gate lint
```

```yaml
    reason: 'rule producer_of:alignment.bam matched {''read_length'': ''>= 70''}: read length determines
      which aligner is appropriate'
```

The only way to surface the explanation is to remove the citation — trading one half of "traced
to a measurement" for the other.

Shape (ii) rider: `Why.reason` is a single `Line`, so there is nowhere to put both. Repair is
either `reason` + `cite` as two fields on `Why`, or a join in `Pin.because()` — but the artifact
needs the field split, because a reader wants to see which half is which.

There is a second, smaller reader failure in the same string: `matched {'read_length': '>= 70'}`
is a Python dict `repr` written into a shareable artifact, and it is documented as the intended
form in `docs/reference/rule-schema.md:106`. It also does not say what `read_length` **was**
(150) — see A108.

---

## A108 — tier 3 says "check the premise" and the artifact carries no premise

**High. Shape (ii): the claim cannot be stated. CONFIRMED.**

`CLAUDE.md`: *"Tier 3 is yellow rather than silent on purpose: a rule match is only as good as
the measurement behind it. **Yellow means 'the machinery worked, check the premise.'**"*
`comeni_core/tiers.py` maps `Tier.DATA_PROFILED → ReviewLevel.ADVISORY`.

Three things are missing from the step a reader is asked to check:

1. **The measured value.** The `why` says the rule "matched `{'read_length': '>= 70'}`". It does
   not say the value was 150.
2. **Whether that value was measured or asserted.** This is the whole of the clinical argument —
   `ValueSource.MEASURED` vs `ValueSource.GOAL`, and it is what issue #2's `sealed` policy is
   meant to check.
3. **The branch not taken.** `registry/rules/rnaseq.yml` declares the alternative
   (`nf-core/hisat2/align@2.2.2` below 70bp). The artifact records neither the alternative nor
   the threshold's direction, so a reader cannot see how close the call was.

### Demonstration of (2)

`audit-tmp/goal-measured.yml` differs from `examples/rnaseq-goal.yml` in exactly one thing:
`read_length: 150` arrives with `source: measured, by: comeni/profile/fastqc@0.12.1` instead of
being asserted.

```bash
uv run mendel build --goal audit-tmp/goal-measured.yml --out audit-tmp/b5-measured --gate lint
diff audit-tmp/b1/pipeline.yml audit-tmp/b5-measured/pipeline.yml
```

```
45,46c45,46
<       source: goal
<       by: null
---
>       source: measured
>       by: comeni/profile/fastqc@0.12.1
313c313
<   from_digest: sha256:2d90a…
---
>   from_digest: sha256:ac9b2…
```

The whole `steps:` block is **byte-identical**. "STAR was chosen because a tool measured your
reads at 150 bp" and "STAR was chosen because somebody typed 150 into a file" produce the same
sentence at the decision. The distinguishing fact is recorded 250 lines away, unjoined, in a
section the same document declares *inert*.

`Why` has five fields — `tier`, `source`, `reason`, `from_layer`, `displaced_layer`. `source`
means *who settled the decision* (`resolver`), never *how the premise was established*. There is
no field for the premise. Shape (ii).

### `ReviewLevel.ADVISORY` is consumed by nothing

```
$ grep -rn "ADVISORY" packages/ | grep -v test
packages/comeni-core/src/comeni_core/tiers.py:55:    ADVISORY = "advisory"
packages/comeni-core/src/comeni_core/tiers.py:62:    Tier.DATA_PROFILED: ReviewLevel.ADVISORY,
```

It is produced and never read. `PipelineIR.needs_review()` lists `ReviewLevel.REQUIRED` only
(`ir.py:239`); `review_level` does not reach `pipeline.yml`; no CLI verb prints an advisory line.
Yellow exists in the documentation and in an enum, and nowhere a user can see it.

**Relation to issue #2:** adjacent, not the same. #2 asks the `sealed` profile to *block* a
tier-3 decision resting on an assertion, and is blocked on Plan 2's `ProfilePolicy`. This is
that a reader of *any* profile, on *any* pipeline, cannot see the distinction at the decision —
a legibility gap, and one whose repair (`Why` carrying the premise) is what #2's check would
need to consult anyway.

---

## A109 — root G, second instance: `steps[].inputs[].states`

**Medium. Shape (i). CONFIRMED.**

The brief asks for a second field that reads two ways. This one reads three.

`comeni_core/pipeline.py:640–656` materialises `StepInput` down two branches:

```python
        if edge is not None:
            inputs.append(StepInput(port=…, source=…, states=sorted(edge.states)))
        else:
            inputs.append(StepInput(port=port.name, channel=port.type_id))
```

and `resolve.py:130–146` sets `IREdge.states` from `source[3]` — **the producer's emitted
states**, not the consumer's requirement.

So:

- on the `source:` branch, `states:` is *what the upstream step emits*;
- on the `channel:` branch, `states:` is the field default `[]` — *not recorded*, which is a
  different fact from "no states";
- and to a reader, sitting under `inputs:` next to `port:`, it reads as *what this port
  requires* — which is the thing routing actually turned on and the thing the artifact never
  records.

**In the shipped spine all three readings coincide**, on every one of the four wired inputs.
That is the root-G hazard exactly: nothing in the repository distinguishes them.

### Demonstration that they diverge

`audit-tmp/lab-indexed/` overlays `samtools/sort` to produce
`state: [coordinate_sorted, indexed]`. featureCounts' contract requires only
`state_required: [coordinate_sorted]`.

```bash
uv run mendel build --goal examples/rnaseq-goal.yml \
  --registry registry --registry audit-tmp/lab-indexed --out audit-tmp/b12-indexed --gate lint
```

```yaml
- id: subread_featurecounts
  inputs:
  - port: bam
    source: samtools_sort.bam
    states:
    - coordinate_sorted
    - indexed
```

A reader concludes featureCounts requires an indexed BAM. It does not. In a registry with
alternative producers — v2's stated breadth — the two readings diverge on every step where a
producer emits more than was asked for, which is the normal case (`producers_of` matches on
superset by design).

Named repair: two fields, `states:` (what arrives) and `required:` (what the port asked for),
with the second populated on both branches. The router already computes `required` in
`_source_for` and discards it.

---

## A110 — `decisions[].confidence` is undocumented and has no "not applicable"

**Medium. Shape (ii), and shape (iii) for Plan 2. CONFIRMED (spec gap) / PLAUSIBLE (Plan 2).**

Every leaf key written into three real `pipeline.yml` files, checked against the artifact's own
spec (`audit-tmp/keys.py`):

```
$ uv run python audit-tmp/keys.py audit-tmp/b1/pipeline.yml \
    audit-tmp/b8-overlay/pipeline.yml audit-tmp/b10-fastp/pipeline.yml
KEYS WRITTEN: 96

LEAF NAME NEVER APPEARS IN pipeline-schema.md:
  decisions.confidence
  registry.displaced.displaced_keys
  registry.displaced.winning_key
  registry.displaced.winning_layer
```

92 of 96 documented is a good result and is recorded in *Clean* below. `confidence` is the one
that matters:

- It is `float = 0.0` (`decision.py:114,146`), not `float | None`, so there is **no way to say
  "not applicable"**. `FlagOnlyResolver` never sets it, so every decision in every shipped
  pipeline reads `confidence: 0.0`.
- A reader of a published artifact sees a decision annotated *0.0 confidence* and concludes the
  system had none. What is true is that nothing measured it.
- `docs/concepts/tiers.md:73` tells the reader confidence is a real quantity: *"Tier 4 is always
  flagged, even at high model confidence."*
- It crosses door 4 into publication.

**Shape (iii), PLAUSIBLE — I did not build it.** Plan 2 puts a model behind
`AmbiguityResolver`, and a model reports confidence. On that day `0.0` means both "the model was
certain this is wrong" and "flag-only, never measured", in the same field, in files already
published. Making it `float | None` costs one line now and is a schema migration afterwards.

The three `Displacement` keys are a smaller instance of the same thing: `pipeline-schema.md`
says *"what an overlay displaced"* and never shows the record's shape, so a reader meeting
`winning_key` and `displaced_keys` for the first time is reading an undocumented structure in
the file the docs call the product.

---

## A111 — a `why:` whose two halves describe different moments, on a reason whose justification expired

**Medium. Shape (i), and a recorded reason that has stopped being true. CONFIRMED.**

Answer the tier-4 question the documented way and upgrade:

```bash
cp -r audit-tmp/b1 audit-tmp/b2-answer      # settings[].value: null -> illumina
uv run mendel emit    audit-tmp/b2-answer/pipeline.yml --out audit-tmp/b2-answer
uv run mendel upgrade audit-tmp/b2-answer/pipeline.yml --out audit-tmp/b2-up
```

```
1 tier-4 question(s) answered by a human — still tier 4, and still recorded:
  ANSWERED star_align.seq_platform = 'illumina'
5 modules, 0 requiring review
```

`audit-tmp/b2-up/pipeline.yml`:

```yaml
  - name: seq_platform
    value: illumina
    why:
      tier: 4
      source: human
      reason: no rule covered 'seq_platform'; selected the first of 1 candidates without judgement
        — please review
```

`source: human` — a person answered. `reason:` — the machine picked it without judgement, please
review. The same five-line block, contradicting itself. `needs_review()` returns 0, so the file
asks for a review nothing will ever list again. This survives `publish`.

`source` is recomputed on replay; `reason` is carried verbatim. They describe different moments
of the same value's life and the file presents them as one statement.

### The recorded reason has expired

`mendel_resolver/replay.py:65–78` records why the reason is carried verbatim:

> The recorded reason, verbatim. Prefixing it with "replayed from a recorded decision" was the
> plan's wording, and it cannot survive: **`reason` is emitted into `main.nf` as the comment
> above the parameter**, so prefixing it makes an upgraded pipeline differ from the published one
> by exactly that string — and federation §4.1 says loading a locked pipeline reproduces
> byte-identical Nextflow. **Nothing is lost.** The comment answers "why is this value what it
> is", which replaying did not change.

Both halves have stopped being true.

1. **`reason` is no longer emitted into `main.nf`.** Plan 1.10 replaced the `params.<x>` lines
   (which carried the reason as a comment) with `ext.args` in `nextflow.config`. Neither
   generated file contains any reason string:

   ```
   $ grep -n "no rule covered\|selected the first" audit-tmp/b1/main.nf audit-tmp/b1/nextflow.config
   (no output)
   ```

   Federation §4.1 promises byte-identical **Nextflow**, and `reason` no longer reaches it. The
   constraint the decision was made under does not exist.

2. **"Replaying did not change why the value is what it is" is false in the branch that sets
   `source: HUMAN`.** That branch fires only when `record.human_override is not None`, and
   `_chosen()` then returns the override rather than `chosen`. Replaying changed *what the value
   is* — from `None` to `illumina` — so the reason describes a value that is no longer there.
   The `source: HUMAN` branch is A56's fix, shipped in Plan 1.12; the argument above predates it.

Named repair: on the `HUMAN` branch only, replace the reason with one describing the override.
Byte-identity of the Nextflow is unaffected.

---

## A112 — `human_override`: the reference says do not write it, the diagnostic says write it

**Medium. Shape (ii). CONFIRMED.**

`docs/reference/pipeline-schema.md`, § `decisions`:

> `human_override` **records** a person's answer […] but it is **not where you *write* one**. The
> single writable home of a tier-4 answer is `settings[].value`; `human_override` is derived from
> it.

Following that exactly — set `value: illumina`, correct the now-false `why` to
`source: human` with an honest reason, leave `human_override` alone
(`audit-tmp/b6-human-only`):

```
mendel: this goal is not valid —
  Value error, MD0220: star_align.seq_platform says source: human, but no decision records a
  person answering it — its human_override is null or absent. […] Set the decision's
  human_override to the value, or restore the source that resolution gave it.
```

`mendel explain MD0220` confirms it is intended: *"A genuine override sets **both**."*
Setting both (`audit-tmp/b7-both`) loads and emits cleanly.

So the field reads two ways depending on which document you consulted, and the two readings are
not compatible: the reference doc's route leaves `why.source: resolver` on a human's value
(A104/A111), and the diagnostic's route requires editing a field the reference doc says is
derived. `Pipeline.replayable_decisions()` *does* derive it for `upgrade`, which is why the
reference doc is half right — but the derived value is never written back, so `emit` leaves the
stored `human_override: null` and the file on disk records no answer.

Repair is a documentation decision, not a code one: pick one writable home and make both
documents say the same thing. If it is `settings[].value`, `emit` should write the derived
`human_override` back and update `why`; if it is both fields, `pipeline-schema.md` § `decisions`
is wrong as written.

---

## A113 — "the only contract that produces this" is a fact about the registry wearing tier 1

**Low. Shape (i). CONFIRMED. Overlaps stream 4's territory; filed on the artifact's sentence.**

Four of the five steps in the shipped spine carry:

```yaml
  why:
    tier: 1
    source: resolver
    reason: the only contract that produces this
```

`CLAUDE.md` defines tier 1 as *"no choice exists — **inputs force it**"*, review level `none`,
UI `silent`. A biologist reads "the only contract that produces this" at tier 1 and concludes
the inputs forced TrimGalore. What is true is that this registry declares one producer of
`fastq.reads[trimmed]`. fastp and cutadapt exist and are standard; the artifact does not say
they were not considered, or that the search space was one directory.

**Demonstration** — `audit-tmp/lab-fastp/` adds a single contract declaring the same
produces/consumes and the same `priority`:

```bash
uv run mendel build --goal examples/rnaseq-goal.yml \
  --registry registry --registry audit-tmp/lab-fastp --out audit-tmp/b10-fastp --gate lint
```

```
5 modules, 3 requiring review
  REVIEW  fastp (module)
  REVIEW  fastp.producer:fastq.reads
```

```yaml
  why:
    tier: 4
    source: resolver
    reason: 'nothing distinguishes nf-core/fastp@0.24.0, nf-core/trimgalore@0.6.10; …'
```

The analysis did not change. The data did not change. The goal did not change. The same step
moved from *silent, no review, "no choice exists"* to *tier 4, required review* because a
directory grew by one file. That is honest routing (invariant 8 held — see *Clean*), and it is
the proof that the tier-1 sentence was never a statement about the analysis.

Repair is one sentence: *"the only contract in this registry stack that produces this"*, which
is both true and actionable — it tells the reader the thing to check is whether their registry
is complete.

**Overlap declared:** stream 4 is asked whether "adding a contract can make the pipeline worse"
is real. It is, and this is the same mechanism seen from the artifact side. Their finding is
about routing; this one is about the sentence a reader acts on. If both land, merge.

---

## A114 — `publish` is silent about the open question it is certifying

**Low. Shape (ii). CONFIRMED.**

```bash
cp -r audit-tmp/b1 audit-tmp/b3-unanswered      # seq_platform still value: null
uv run mendel publish audit-tmp/b3-unanswered/pipeline.yml --gate lint
```

```
gate lint: PASS
```

exit **0**. The file it stamped contains:

```yaml
- key: star_align.seq_platform
  tier: 4
  candidates: [null]
  chosen: null
  human_override: null
  reason: no rule covered 'seq_platform'; … — please review
```

`mendel build` prints `REVIEW star_align.seq_platform`. `mendel upgrade` prints the review
count. `mendel publish` — the one verb that stamps a verdict onto an artifact other people will
read, and the one the design calls *the door with no undo* — prints only the gate line.

`_publish_verb`'s docstring is narrow and internally consistent: *"Certification asks one
question — do the files on disk pass the gate."* That is a defensible promise. The finding is
that it is the *only* promise, and no verb that reads an existing `pipeline.yml` ever answers
"what in this pipeline still needs a human". `emit` does not. `publish` does not. The review
queue is in the file, and the reader has to know to look for it.

A70 was found by asking what `publish` promises. Asking the same question of the review queue
gives: the artifact carries it, and no verb hands it to you at the moment it matters most.
One line in `_publish_verb` — the `needs_review()` list, before the gate runs — closes it.

---

## Also reached, already known — confirmations, not discoveries

Recorded so the synthesiser can see what was examined rather than filing noise.

- **"contract default for `min_mqs`" is circular** — it says who decided, not why. The brief
  hands this to **stream 1** explicitly. Confirmed from the artifact side: it is the only reason
  string in the shipped spine that names no fact, no document and no citation, and A104 shows it
  survives being made false.
- **`candidates: [null]`** appears verbatim in `decisions[]` and in `pipeline-schema.md`'s own
  example with no explanation. It is documented in code (`resolve.py`: a `Param` has no declared
  domain until Plan 2 Task 11) and is **stream 1's** question. Confirmed as a reader failure:
  the artifact tells a biologist there was one candidate and it was `null`.
- **Issue #2** — reached from the other direction by A108, filed as distinct and marked so.
- **Issue #11** (the module count) — the shipped spine is 5 processes for this goal, not 10 or
  15–20. Not filed: known, undecided, and out of stream.

---

## Clean — attacked and held

Everything below was attacked deliberately and survived. Commands and outputs are real.

1. **A55's shape generalised to `ext_args`.** The brief asks whether the shape that produced A55
   was examined. `settings[].value` was patched by `MD0221`; `Step.ext_args` is the same shape —
   a string in a shareable file that lands in Nextflow config, and `_ext_scope` turns any
   fragment containing `${` into a host-evaluated closure. It is **guarded**, by a different
   mechanism: `NfTemplate` refuses any interpolation that is not `${meta.*}`/`${task.*}`.
   ```
   $ # ext_args edited to "--readFilesCommand zcat --x ${System.getProperty('user.name')}"
   $ uv run mendel emit audit-tmp/b1-extargs/pipeline.yml --out audit-tmp/b1-extargs
   MD0204: ${System.getProperty('user.name')} is not an allowed interpolation. A template may
   reference only ${meta.<id>} or ${task.<id>}; anything else is arbitrary Groovy reaching the
   generated config.
   ```
   Refused at load, before `emit` reads it — the same layering `MD0221` was given. Held.

2. **An overlay changing a contract default.** Invariant 11 says never let an installed overlay
   reroute a pipeline silently. `audit-tmp/lab-overlay/` changes `min_mqs`' default to 30. The
   build prints an `OVERLAY` line; `registry.displaced` records a full `Displacement`
   (`winning_layer`, `displaced_layer`, `displaced_keys`); `steps[].module.digest` moves; and
   `steps[].why.from_layer` moves from `comeni-registry-examples` to `acme-lab-overlay`. The
   whole diff against the base build is 10 lines, every one of them explaining the next. Held,
   and it is the best-told story in the artifact.

3. **A tied producer is not a coin flip.** `audit-tmp/lab-fastp/` adds a contract identical on
   surplus and priority. Result: tier 4, a `ProducerDecision` listing **both** candidates and the
   one taken, `REVIEW fastp (module)` *and* `REVIEW fastp.producer:fastq.reads` on stderr, plus
   `MD0100` for the unvendored module and a failing lint gate because its source is absent.
   Invariant 8 held under a real registry edit, and conformance caught the fixture in the same
   run.

4. **The orphan lifecycle.** `audit-tmp/lab-noparam/` removes `seq_platform` from the contract;
   `upgrade` is run on a pipeline where a person had answered it:
   ```
     DRIFT   nf-core/star/align@1.11.0 has been edited since it was locked
     DRIFT   the layer stack changed: locked [comeni-registry-examples], now […, noparam-probe]
   the generated pipeline differs: nextflow.config
     CHANGED   star_align.seq_platform: illumina -> (no longer a setting)  (tier 4) the contract no longer declares it
   0 decisions replayed, 0 newly asked
     ORPHANED star_align.seq_platform — your edit no longer applies to anything
   mendel: MD0203: 1 recorded override(s) answer questions this re-resolution does not ask. Nothing was written.
   ```
   exit **2**, nothing written. Drift, change, orphan and refusal are four distinct statements a
   person can act on, and the verb declines rather than guessing. This is the lifecycle story
   working. Held.

5. **`MD0213` staleness.** Every edit-then-forget in this audit was caught, on every verb, and
   `emit` cured it while `publish` and `upgrade` refuse. Attacked incidentally a dozen times;
   never once did a stale directory pass unremarked. Held.

6. **`MD0220` against relabelling.** Claiming `source: human` with no recorded answer is refused
   (A112's demonstration). The dishonest direction is closed; A104 is that the *other* direction
   is open.

7. **Determinism of the artifact.** Two independent builds of the same goal produce a
   byte-identical `pipeline.yml` **and** `main.nf`, including `emitted.from_digest`. Held.

8. **Shareability.** The shipped `pipeline.yml` contains no filesystem path, no username, no
   timestamp and no hostname — checked by grep against the worktree path, the operating user and
   ISO date/time patterns. Invariant 15's "a shape, not data" holds at the artifact boundary.
   Held.

9. **`mendel profile` reports what it cannot do.** `--have fastq.reads` prints
   `NOT MEASURED n_samples, paired, strandedness — declared, but no contract in this registry
   produces them`, and writes `value: null` because it emitted a pipeline and did not run one.
   An honest verb. Held.

10. **The artifact's spec covers the artifact.** 92 of 96 leaf keys written by three real builds
    appear in `docs/reference/pipeline-schema.md`. For a document of this size that is a good
    result and worth saying; A110 is the residue.

11. **`MD0215`, `MD0211`, `MD0212`, `MD0208`, `MD0218`** all fired or were structurally
    unreachable during the edits above; none was found to be inert. Not attacked systematically
    — that is round-four's work and out of scope here.

---

## Reading it as a bench scientist — the summary judgement

The file is close. A molecular biologist can open `audit-tmp/b1/pipeline.yml` and follow the
shape of the pipeline: five steps, what feeds what, which container, pinned by digest, which
registry layer, what the laboratory has to supply, and one flagged question. That is more than
any chat window gives them, and the `steps[].inputs[].source` chain in particular reads cleanly.

What fails is the *why*, and it fails in one direction consistently: **every place the design
has a plain-English explanation, the artifact drops it and keeps the machine-readable half.**

- the rule's `because:` is dropped in favour of its `cite:` (A107)
- the contract's YAML comment explaining `--readFilesCommand zcat` is dropped, and the flag
  arrives with no `why:` at all (A106)
- the measurement's declared inversion `paired → single_end` is dropped, leaving two lines that
  read as a contradiction (A106)
- the measured value behind a tier-3 match is dropped, and so is whether anyone measured it
  (A108)
- the alternative not taken is dropped (A108)
- and where a human edits a value, the machine's old reason stays and reads as current (A104)

The residue a reader is left with — `producer_of:alignment.bam`, `{'read_length': '>= 70'}`,
`candidates: [null]`, `confidence: 0.0`, `literal: bai`, `empty_width: 3` — is Mendel's internal
vocabulary. None of it is wrong. All of it requires knowing how Mendel works to read.

The claim under audit is *"in an age where AI leads, humans must still be able to follow"*. The
artifact currently lets a human **verify** — digests, layers, gates, pins, all excellent — and
does not yet let them **follow**. Those are different products, and the first one is the one
that is finished.

Every repair named above is small and none is architectural: one field on `Why`, one field on
`MetaEntry`, a reordering in `Pin.because()`, one widened test condition, one extra field on
`StepInput`, and four sentences authored into the registry.

---

## What was left behind

All under `audit-tmp/` in this worktree, preserved for re-verification.

| path | what it is |
|---|---|
| `b1/` | the baseline build — `--goal examples/rnaseq-goal.yml --gate lint` |
| `b1-extargs/` | Groovy injected into `ext_args`; refused by `MD0204` (Clean 1) |
| `b2-answer/`, `b2-up/` | tier-4 answered via `settings[].value` only; and upgraded (A111) |
| `b3-unanswered/` | published with an open tier-4 question (A114) |
| `b4-nocite/` | built against a registry with `cite:` removed (A107) |
| `b5-measured/` | `read_length` as `source: measured` (A108) |
| `b6-human-only/` | `source: human` with no override — `MD0220` (A112) |
| `b7-both/`, `b7-up/` | the honest two-field edit (A112) |
| `b8-overlay/` | overlay changing a contract default (Clean 2) |
| `b9-because/` | a literal with a `because` (A106) |
| `b10-fastp/` | a tied second producer (A113, Clean 3) |
| `b11-orphan/`, `b11-out/` | the orphaned-override lifecycle (Clean 4) |
| `b12-indexed/` | producer emitting more states than required (A109) |
| `b13-mqs/`, `b13-up/` | **A104 and A105** — the hand-edited tier-2 value |
| `b14-repeat/` | determinism re-run (Clean 7) |
| `p1/` | `mendel profile --have fastq.reads` (Clean 9) |
| `lab-overlay/`, `lab-because/`, `lab-fastp/`, `lab-noparam/`, `lab-indexed/`, `layer-nocite/` | the probe registry layers |
| `goal-measured.yml` | the measured-provenance goal |
| `keys.py` | artifact keys vs. `pipeline-schema.md` (A110) |

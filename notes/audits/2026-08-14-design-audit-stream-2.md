# Design audit — Stream 2: the compiler, as a compiler

**Reviewer:** cold, no session context. **Block:** A90–A103 (A90–A97 used; A98–A103 unused).
**Date:** 2026-08-14. **Tree:** worktree off `main` at `346eeac`.
**Brief:** `notes/audits/2026-08-14-design-audit-brief.md`, § *Stream 2*.

Baseline established before any probe: `make verify` green (608 fast + 3 slow + 27 guards,
`ruff check` clean), and `uv run mendel build --goal examples/rnaseq-goal.yml --out … --gate lint`
produces the five-process spine with one item requiring review.

Prior artifacts at `.audit-artifacts/stream-2-2026-08-13/` were read before probing. The
non-nf-core layer (`nonf/`) and the collision probe (`coll/`) were reused as leads; every finding
below was reproduced first-hand in this worktree from a fresh layer.

---

## Findings

| # | Shape | Severity | Verdict | What |
|---|---|---|---|---|
| **A90** | (ii)+(i) | high | CONFIRMED | `call[].literal` carries no `why`, cannot be resolved, and a human edit to it is silently reverted by `upgrade` |
| **A91** | (ii)+(i) | **critical** | CONFIRMED | No `via:` reaches a `val` positional input. 3 of 10 vendored modules have one, each a real analysis decision. Routing one `via: meta` builds clean and disagrees with what the tool reads |
| **A92** | (ii)+(i) | **critical** | CONFIRMED | Two ports sharing one channel are joined with `.combine()` — a cross product. Two samples in, four processes out, half of them mismatched. `NfInput` has nowhere to declare a join key |
| **A93** | (ii)+(i) | high | CONFIRMED | `via: meta` hardcodes nf-core's `[meta, …]` first-input shape. Nothing declares it, nothing checks it, and no route can carry a resolved value to a non-nf-core module at all |
| **A94** | (i) | high | CONFIRMED | `_default_entry` derives `params.<name>` from the type id's **last segment**, so `tumour.bam`/`normal.bam` collide onto one parameter and both channels read the same files. Exit 0, no diagnostic |
| **A95** | (i) | medium | CONFIRMED | Conformance checks tuple width only for `empty` placeholders. A contract that drops a consumed port from `nf_inputs` passes all nine diagnostics, `lint` and `-preview`, and dies at run time |
| **A96** | (ii)+(i) | high | CONFIRMED | `Goal` cannot ask for one type in two states. Asking for both silently yields one, with no diagnostic and no review flag, and `pipeline.yml` records the unsatisfied goal verbatim |
| **A97** | (iii) | medium | CONFIRMED | A contract can appear at most once in a pipeline. nf-core/rnaseq runs FASTQC twice. Forced by hand, `emit` writes a duplicate `include` — caught by `nextflow lint`, so loud, not silent |

**Root, stated once.** Six of these eight are the same thing: **the emitter knows facts about the
target that the contract cannot declare.** `.combine` for a multi-port channel, `[meta, …]` for the
`via: meta` route, the last URL-ish segment for a parameter name, the process name for a `withName:`
scope and for an `include`, one channel per type id. Each is a correct guess about nf-core and a
silent wrong answer about anything else. `ModuleContract.nf_inputs` exists *because* "a contract
port is not a process argument" — the same argument applies one level down and was not made there.

---

## A90 — a positional literal is a decision with nowhere to record it, and `upgrade` eats an edit

**Shape (ii), then (i). CONFIRMED.**

`NfInput.literal` is how a contract fills a `val` slot the type system does not model. `_call()` in
`comeni_core/pipeline.py` materialises it into a `CallArg` — and attaches a `why` **only if the
contract wrote a `because`**, which `tests/test_runnable.py:82` requires only `if spec.empty`. So a
literal has no forced provenance and, in the shipped registry, none at all.

### Demonstration

```
$ uv run mendel build --goal examples/rnaseq-goal.yml --out audit-tmp/spine --gate lint
5 modules, 1 requiring review
  REVIEW  star_align.seq_platform
gate lint: PASS
```

`audit-tmp/spine/pipeline.yml`, `samtools_sort`:

```yaml
  call:
  - ports: [bam] …
  - ports: []
    empty_width: 3
    why:
      tier: 1
      source: resolver
      reason: the reference is only needed to write CRAM; this emits BAM
  - ports: []
    literal: bai
    empty_width: null
    why: null            # <-- 'bai' is SAMTOOLS_SORT's `val index_format`
```

and `star_align`:

```yaml
  - ports: []
    literal: false
    why: null            # <-- false is STAR_ALIGN's `val star_ignore_sjdbgtf`
```

Both are real analysis decisions. `index_format: bai` vs `csi` is *required* to be `csi` for a
genome with a chromosome over 512 Mbp. `star_ignore_sjdbgtf: false` decides whether the annotation
informs splice-junction detection (`vendor/modules/nf-core/star/align/main.nf:47`). Neither carries
a tier, a reason, a layer or a citation. The `empty` placeholder beside them carries all four.

`docs/reference/pipeline-schema.md` states the opposite, with this exact literal as its example:

> `{literal: false, why: {tier: 1, source: resolver, reason: "no GTF-free splice-junction path in this spine"}}`
> … *A literal and an empty placeholder each carry a `why`.*

The shipped spine writes `why: null` there.

### The second half: an edit is reverted in silence

`settings[].value` is documented as editable. `call[].literal` is not documented either way, and it
is editable in practice:

```
$ cp -r audit-tmp/spine audit-tmp/litprobe
$ sed -i 's/literal: bai/literal: csi/' audit-tmp/litprobe/pipeline.yml
$ cd audit-tmp/litprobe && uv run mendel emit pipeline.yml --out .
MD0213: pipeline.yml has changed since the Nextflow was generated from it. Regenerating.
$ grep SAMTOOLS_SORT main.nf
    SAMTOOLS_SORT(STAR_ALIGN.out.bam, Channel.value([[:], [], []]), 'csi')
```

The edit reaches the tool — with no tier, no `why`, no `decisions` entry, no `needs_review()` line,
and no `MD0220` (which only guards `settings[].why.source: human`). Then:

```
$ uv run mendel upgrade pipeline.yml --out ../litupg --root ../..
the generated pipeline differs: main.nf
  but no recorded change explains it. …
1 decisions replayed, 0 newly asked
$ echo $?          # 0
$ grep "literal:" ../litupg/pipeline.yml | grep -c csi     # 0 — reverted to bai
```

`diff_pipeline` compares `module`, `settings` and `inputs` (`mendel_resolver/diff.py:54–93`). It
does **not** compare `call`. The only thing that noticed is `_verdict`'s blind-spot warning, which
names no value and exits 0.

### What would have to change

`NfInput` needs `because` on `literal` as it has on `empty` (a one-line change to
`tests/test_runnable.py:82` plus three registry contracts), and `diff_pipeline` needs a
`_call_changes`. Neither makes the literal *resolvable* — that is A91.

---

## A91 — the fourth destination: a `val` positional input, and no `via:` reaches it

**Shape (ii), then (i). CONFIRMED. This is the brief's first Stream 2 question answered.**

The brief asks whether `ext`/`meta`/`directive` is a complete partition of "where a value can go".
It is not, and the missing case is in the vendored registry today:

```
$ python3 …  # bare `val` inputs in the input block of each vendored module
hisat2/align       ['val save_unaligned']
samtools/sort      ['val index_format']
star/align         ['val star_ignore_sjdbgtf']
```

Three of ten. Each is a positional process argument, and `Via` has three members, none of which
emits into a call position. `NfInput.literal` is the destination — but it is a **contract constant**,
not a `Param`, so it cannot carry a tier, cannot be the `then` of a tier-3 rule, cannot be a goal
override, and cannot be answered by a reviewer.

### Demonstration — the two-values-one-name build

I gave STAR's own parameter the only route that would accept it.
`audit-tmp/regmeta/contracts/nf-core/star-align.yml`:

```yaml
  - name: star_ignore_sjdbgtf
    tier_hint: 4
    via: meta
```

```
$ uv run mendel build --goal examples/rnaseq-goal.yml --registry audit-tmp/regmeta \
    --out audit-tmp/metaprobe --root . --gate lint
5 modules, 2 requiring review
  REVIEW  star_align.seq_platform
  REVIEW  star_align.star_ignore_sjdbgtf
gate lint: PASS
```

No conformance diagnostic. I then answered it the way the schema doc says to — set
`settings[].value: true` — and re-emitted:

```groovy
STAR_ALIGN((TRIMGALORE.out.reads).map { it -> [ it[0] + [star_ignore_sjdbgtf: true] ] + it[1..-1] },
           STAR_GENOMEGENERATE.out.index, ch_annotation_gtf, false)
```

**One emitted call, two values named `star_ignore_sjdbgtf`, disagreeing.** The one with a full
`why:` — tier 4, answered, review cleared — is `meta.star_ignore_sjdbgtf = true`, which STAR never
reads. The one STAR reads is the trailing `false`: the A90 literal, with `why: null`.
`pipeline.yml` says the GTF is being ignored. The pipeline uses it. `gate lint` passes.

`MD0108` — the check that exists precisely to refuse a route the module does not read — covers
`ext` keys only (`conformance.py:_dead_ext_routes`, and its own docstring says so). `via: meta`
deadness is unchecked.

### Why this is the sharpest finding in this stream

`seq_platform` is the design document's own worked example of a tier-4 parameter
(`docs/design/mendel.md` §5.1). It happens to route to `ext.args`. The parameter *beside it in the
same module* cannot be routed at all, and the design records that as a contract constant with no
reason. "Nothing was guessed silently" is false for three of the ten modules in the registry, and
the guess is invisible because it never enters the tier ladder.

### What would have to change

A fourth `Via` (`positional`, keyed by the `nf_inputs` index or by a named slot), or `NfInput.literal`
becoming a `Param` binding. Either way `CallArg` grows a settings-shaped field and `_argument()` must
read a resolved value rather than a contract constant. This is a `pipeline.yml` `version:` bump.

---

## A92 — two ports in one channel are cross-produced, and no join key can be declared

**Shape (ii), then (i). CONFIRMED by a real Nextflow run. This is the highest-severity finding.**

`emit._argument()`:

```python
    # Several semantic ports share one channel — featurecounts wants
    # tuple(meta, bams, annotation). Combine drops the second tuple's meta.
    head, *rest = expressions
    joined = "".join(f".combine({expr}.map {{ it[1] }})" for expr in rest)
```

`.combine()` is a Cartesian product. It is correct in the shipped spine only because the second
port is a single reference file — `N × 1 = N`. `NfInput` declares `ports`, `literal`, `because`,
`empty`. There is **no field that says how two per-sample channels are matched**, and `emit`
therefore cannot do anything else.

### Demonstration

Fresh layer at `audit-tmp/join/`. Module `PAIRUP` takes `tuple val(meta), path(a), path(b)`;
contract declares `nf_inputs: [{ports: [a, b]}]` — the `SUBREAD_FEATURECOUNTS` shape exactly.

```
$ uv run mendel build --goal goal.yml --registry layer --out build --root . --gate lint
1 modules, 0 requiring review
gate lint: PASS

$ grep PAIRUP build/main.nf
    PAIRUP(ch_a_tsv.combine(ch_b_tsv.map { it[1] }))
```

Two samples in each channel, run under Nextflow 25.10.4:

```
$ nextflow run main.nf --a "$PWD/data/*.a.tsv" --b "$PWD/data/*.b.tsv"
[e8/bbd23e] Submitted process > PAIRUP (1)
[9b/20955d] Submitted process > PAIRUP (2)
[3e/943448] Submitted process > PAIRUP (3)
[63/9a570d] Submitted process > PAIRUP (4)

$ find work -name '*.paired.txt' -exec grep -H "" {} \;
…/s1.a__s1.b.paired.txt:A=s1.a.tsv B=s1.b.tsv
…/s1.a__s2.b.paired.txt:A=s1.a.tsv B=s2.b.tsv     <-- sample 1 with sample 2
…/s2.a__s1.b.paired.txt:A=s2.a.tsv B=s1.b.tsv     <-- sample 2 with sample 1
…/s2.a__s2.b.paired.txt:A=s2.a.tsv B=s2.b.tsv
```

**Two samples in, four analyses out, half of them pairing one sample's data with another's.**
Green run, exit 0, no warning.

### Why nothing in the design catches it

- Every static gate passes: conformance has no check on this, `nextflow lint` sees valid Groovy,
  `-preview` builds the DAG.
- `--gate test` is the only gate that runs tools on data, and the nf-core RNA-seq test dataset has
  **one sample**. `1 × 1 = 1`, so the v1 criterion cannot see this class at all.
- The shipped spine is accidentally safe. It stops being safe the moment a second per-sample port
  exists — BAM + BAI (`samtools/idxstats`, `samtools/stats` with a reference index), tumour +
  matched normal, reads + per-sample adapter file. All of those are ordinary v2 shapes.

### What would have to change

`NfInput` needs a join declaration — minimally `join_on: meta.id` vs the current implicit `combine`,
with `combine` remaining the honest answer for a broadcast reference. `emit._argument()` then emits
`.join(…)` or `.combine(…)` from a declared fact instead of one hardcoded guess. Registry contracts
must state which they mean; a default is what produced this.

---

## A93 — `via: meta` hardcodes nf-core's channel shape, and no route reaches a non-nf-core module

**Shape (ii), then (i). CONFIRMED. This is the brief's second Stream 2 question answered.**

`ARCHITECTURE.md` §5a and `CLAUDE.md`'s gotchas both claim the design works for "a pegi3s image or
an in-house process too", and cite `entry_channel` living in the vocabulary as the reason. That half
is true (see *Clean*, below). The **configuration** half is not.

`emit._meta_injection()` emits `.map { it -> [ it[0] + [k: v] ] + it[1..-1] }`, with a docstring that
states the assumption plainly — *"nf-core's convention is that the first input tuple is `[meta, …]`"*.
Nothing declares that a module honours it; nothing checks it.

### Demonstration

Fresh layer at `audit-tmp/metabare/`. Module `PLAINSUM` takes a bare `path table` — no meta map, no
container, no stub block, no `task.ext.args`. Its contract declares one param, `via: meta`.

```
$ uv run mendel build --goal goal.yml --registry layer --out build --root . --gate lint
1 modules, 1 requiring review
  REVIEW  plainsum.assay
gate lint: PASS
```

Answer the tier-4 question in `settings[].value`, re-emit:

```groovy
PLAINSUM((ch_t_tsv).map { it -> [ it[0] + [assay: 'rnaseq'] ] + it[1..-1] })
```

Static gates, all three:

```
$ nextflow lint main.nf            # 0 errors
$ nextflow run main.nf -preview -profile stub_data   # exit 0
```

Actually running it:

```
$ nextflow run main.nf --t "$PWD/data/*.t.tsv"
ERROR ~ Unknown method invocation `getAt` on UnixPath type
 -- Check script 'main.nf' at line: 14
```

### The boundary, stated exactly

For a module that is not nf-core-shaped, **no resolved value can reach the tool**:

| route | outcome |
|---|---|
| `ext` | correctly refused — `MD0108` fires (verified below in *Clean*) |
| `meta` | accepted unchecked; dies at launch if the first input is not `[meta, …]`, and is a silent no-op if it is a tuple whose module never reads the key |
| `directive` | Nextflow's own scope. Reaches the executor, never the tool |

So the registry can hold a non-nf-core contract, route it, emit it and run it — and that contract
can carry **zero** tier-2, tier-3 or tier-4 settings. That bounds what the forge can ever ingest,
which is the reason the journal gives for running this stream first.

### What would have to change

The `[meta, …]` shape has to become a declared property. Either a vocabulary-level statement (the
`entry_channel` already declares the shape it builds — `meta` could be read from there rather than
assumed), or a contract-level `meta_tuple: true/false` with an `MD01xx` that reads the module's
input block, which `modulespec.py` already parses. Plus an `MD0108` sibling that refuses a `via:
meta` key no module reads — the same check `_dead_ext_routes` already makes for `ext`.

---

## A94 — two entry types can collide onto one `params.<name>`, silently

**Shape (i). CONFIRMED. Independently reached by the prior stream (`coll/`), reproduced fresh here.**

`comeni_core/pipeline.py:_default_entry()`:

```python
    param = type_id.rsplit(".", 1)[-1]
    return f"Channel.fromPath(params.{param}, checkIfExists: true).map {{ f -> [ [:], f ] }}"
```

The parameter name is the type id's **last segment**. Two entry types sharing one — `tumour.bam` and
`normal.bam`, `assay.panel` and `control.panel`, `p.data` and `q.data` — produce two channels reading
the same parameter.

### Demonstration

Fresh layer at `audit-tmp/collide/`, one module consuming `p.data` and `q.data`:

```
$ uv run mendel build --goal goal.yml --registry layer --out build --root . --gate lint
1 modules, 0 requiring review
gate lint: PASS
```

```groovy
    ch_p_data = Channel.fromPath(params.data, checkIfExists: true).map { f -> [ [:], f ] }
    ch_q_data = Channel.fromPath(params.data, checkIfExists: true).map { f -> [ [:], f ] }

    TWO(ch_p_data, ch_q_data)
```

`nextflow.config`:

```
params {
    data = null
}
```

**One parameter for two declared inputs.** Both channels read the same files; there is no way for
the laboratory to supply two different ones. No diagnostic, exit 0.

### Why this one stings

`emit._channel_name()` carries this docstring:

> `fastq.reads` -> `ch_fastq_reads`. The last segment alone reads better but is not injective:
> `qc.report` and `multiqc.report` both became `ch_report`, so one assignment shadowed the other and
> two ports were fed the same channel, silently.

The exact bug, found and fixed, in the function next door. The fix went to the *symptom* that had
been observed (the Groovy variable name) and not to the *class*, and the identical non-injective map
survives in the parameter name — where it is worse, because the variable name is internal and the
parameter name is the laboratory's interface. `MD0211` cannot see it: it checks `params:` against
`expression:` **within one channel**, and both channels are internally consistent.

The shipped registry escapes only by accident of naming.

### What would have to change

`_default_entry` uses the full type id (`params.p_data`), and `_channels()` refuses two channels
claiming the same parameter — one line, in the place `MD0211` already lives. Existing pipelines that
rely on `params.gtf`/`params.fasta` would need those names declared in the vocabulary's
`entry_channel`, which most already are.

---

## A95 — conformance checks tuple width only where the contract admits it is guessing

**Shape (i). CONFIRMED. This is the brief's fourth Stream 2 question — "what disagreement can still pass all nine?"**

`MD0102` compares the *number* of channels. `MD0103` compares the *width* of a slot — but only
`if entry.empty`. A slot filled with real ports is never width-checked, and a consumed port that
appears in **no** `nf_inputs` entry is never noticed at all.

### Demonstration

`audit-tmp/join/layer2/` — the A92 contract with `nf_inputs: [{ports: [a, b]}]` changed to
`[{ports: [a]}]`, against the unchanged `PAIRUP` module (`tuple val(meta), path(a), path(b)`).

```
$ uv run mendel build --goal goal.yml --registry layer2 --out build2 --root . --gate lint
1 modules, 0 requiring review
gate lint: PASS
```

`build2/pipeline.yml` declares the port and never passes it:

```yaml
  inputs:
  - {port: a, channel: a.tsv}
  - {port: b, channel: b.tsv}      # declared…
  call:
  - ports: [a]                     # …and absent from the call
```

`build2/main.nf` builds `ch_b_tsv` and never uses it. `--gate preview` **passes**. Then:

```
$ nextflow run main.nf --a … --b …
WARN: Input tuple does not match tuple declaration in process `PAIRUP`
      -- offending value: [[id:s1.a], …/s1.a.tsv]
ERROR ~ Error executing process > 'PAIRUP (1)'
Caused by:
  Path value cannot be null
```

That is verbatim the failure `NfInput.empty`'s own docstring exists to prevent. The check that
prevents it applies only to placeholders.

### What would have to change

`_against()` already has `slot.width` from `modulespec.py`. A non-empty entry's emitted width is
`len(entry.ports) + 1` for a port list and `1` for a literal, so the same comparison generalises —
and a consumed port named in no `nf_inputs` entry is a one-line set difference. Both fit inside
`MD0103` or a new `MD0109`.

---

## A96 — a `Goal` cannot ask for one type in two states, and asking for both loses one silently

**Shape (ii), then (i). CONFIRMED.**

`Goal.want` is `list[TypeId]`. States come from `Constraints.required_states`, and
`Constraints.states_for()` **unions every row for a type id**:

```python
    def states_for(self, type_id: str) -> frozenset[StateName]:
        return frozenset(state for required in self.required_states
                         if required.type_id == type_id for state in required.states)
```

So "QC the reads as they arrived **and** after trimming", "sort by coordinate **and** by name",
"align to the genome **and** to the transcriptome" have no representation. Asking for both merges
into one requirement.

### Demonstration

`audit-tmp/regtwice/` — the shipped registry plus a `nf-core/fastqc-trimmed` contract producing
`qc.report[post_trim]` from `fastq.reads[trimmed]`, and `post_trim` added to the vocabulary. Each
half routes correctly on its own:

```
$ # want: [qc.report]   (no constraints)
1 modules, 0 requiring review
    FASTQC(ch_fastq_reads)

$ # want: [qc.report]   required_states: qc.report -> [post_trim]
2 modules, 0 requiring review
    TRIMGALORE(ch_fastq_reads); FASTQC(TRIMGALORE.out.reads)
```

Ask for both:

```yaml
want: [qc.report, qc.report]
constraints:
  required_states:
    - {type_id: qc.report, states: []}
    - {type_id: qc.report, states: [post_trim]}
```

```
$ uv run mendel build --goal audit-tmp/qc-goal2.yml --registry audit-tmp/regtwice \
    --out audit-tmp/twice2 --gate lint
2 modules, 0 requiring review
gate lint: PASS

$ grep FASTQC audit-tmp/twice2/main.nf
    FASTQC(TRIMGALORE.out.reads)
```

**The raw-reads QC is simply gone.** No diagnostic, no decision record, nothing in `needs_review()`.
And `audit-tmp/twice2/pipeline.yml` records the goal faithfully:

```yaml
  want: [qc.report, qc.report]
  constraints:
    required_states:
    - {type_id: qc.report, states: []}
    - {type_id: qc.report, states: [post_trim]}
```

A pipeline file that states a goal it does not satisfy, and says nothing about the difference.
"Same goal in → same pipeline out" survives; "nothing was guessed silently" does not — an entire
requested output was dropped without comment.

### What would have to change

`want` must carry states — `list[GoalInput]` rather than `list[TypeId]`, which is the shape `have`
already uses — and `route()` must key its `emitted` set on `(contract_id, requested_states)` rather
than `contract_id` (see A97). Minimally, and much cheaper: refuse two `required_states` rows for one
type id at load, so the goal that cannot be expressed fails loudly instead of half-resolving.

---

## A97 — a contract can appear at most once in a pipeline; nf-core/rnaseq runs FASTQC twice

**Shape (iii) — the design cannot carry known load. CONFIRMED. Fails loudly, not silently.**

Four independent places encode "one step per contract, named after its process":

- `router.route()`: `if chosen.id not in emitted:` — a contract is added to the plan once.
- `router._node_id()`: `return contract.nf_process.lower()` — step identity **is** the process name.
- `emit`'s template: `include { {{ node.process }} } from …` — no `as` alias, and `Step` has no
  field that could hold one.
- `emit._port_expression()` → `_process_of()`: a wiring reference resolves node id → process name,
  so `X.out.y` cannot distinguish two instances even if the include were aliased.
- `emit._ext_scope()` / `_directive_scope()`: `withName: {step.process}` — settings are keyed on the
  process, and `_process_scope` deduplicates identical blocks precisely because "a contract used
  twice must not emit its block twice".

The v1 target is the RNA-seq spine and this does not bite. The named v2 breadth is nf-core/rnaseq,
which runs **FASTQC on raw reads and again on trimmed reads**, `SAMTOOLS_SORT` in two branches, and
MULTIQC over per-stage inputs.

### Demonstration

`audit-tmp/dup/` — a hand-authored `pipeline.yml` with two steps, distinct ids (`fastqc`,
`fastqc_raw`), sharing `process: FASTQC`. `MD0212` refuses duplicate step *ids*; it does not look at
processes. `mendel emit` accepted it:

```groovy
include { FASTQC } from './modules/nf-core/fastqc/main'
include { FASTQC } from './modules/nf-core/fastqc/main'

    TRIMGALORE(ch_fastq_reads)
    FASTQC(TRIMGALORE.out.reads)
    FASTQC(ch_fastq_reads)
```

```
$ nextflow lint main.nf
Error main.nf:11:1: `FASTQC` is already included
```

**Credit where due: this fails loudly.** `nextflow lint` is `--gate lint` and part of `make static`,
so the failure mode is a refused build, not a wrong result. The finding is that the *design* has no
shape for a decision the target pipeline actually contains, and that the workaround a registry author
will reach for — a second contract with the same `nf_process` — produces an unbuildable pipeline
rather than a diagnostic naming the real problem.

### What would have to change

`Step` gains an `alias: NfIdentifier | None`; the template emits `include { X as X_2 }`;
`_process_of` returns the alias; `_ext_scope` keys `withName:` on the alias; `route()`'s `emitted`
set keys on `(contract_id, requested_states)`. That is a `pipeline.yml` `version:` bump and touches
every file in `mendel_compiler/`. It is much cheaper before Plan 2 than after.

---

## Clean — attacked and held

Listed so a reader can tell what was examined rather than only what broke.

**Determinism holds, including under hash-seed variance.** Four builds of the shipped spine, two in
sequence and two under `PYTHONHASHSEED=1` and `=99`:

```
76355bbf…  det1/main.nf   76355bbf…  det2/main.nf
76355bbf…  det3/main.nf   76355bbf…  det4/main.nf
6297073c…  det1/pipeline.yml   6297073c…  det2/pipeline.yml
```

Byte-identical, `main.nf` and `pipeline.yml` both. "Same goal in → same pipeline out" is the half of
the claim this stream could not break.

**A55's fix (`MD0221`) holds against the prior stream's live exploit.** The preserved
`.audit-artifacts/…/nonf/buildinj/pipeline.yml` carries
`value: ${new File('audit-tmp/PWNED-BY-MENDEL.txt').text = …; 'sample'}` on an untemplated
`ext.prefix`. In this tree it is refused at load, before `emit` reads it, with the `MD0221` message.
(One cosmetic note, below the bar for a finding: the CLI prefixes it `mendel: this goal is not
valid`, which is A41's mislabelling one file type over — the input was a `pipeline.yml`.)

**`MD0108` is a real check with real negatives.** Routing `via: ext, key: args` to a hand-written
module whose script never mentions `task.ext.args` was refused with the module path and the missing
string quoted. Nothing was emitted. This is the check the whole `via:` design rests on and it works
on a module the authors never saw.

**The digest chain is real.** Editing `pipeline.yml` and re-emitting produced `MD0213` and cured it;
copying a foreign `pipeline.yml` into a built directory produced `MD0214` with a message naming
`pipeline.yml` as the file to change. I verified independently that
`.audit-artifacts/…/nonf/build2/`'s recorded `emitted.files` digests match `sha256sum` of the files
on disk — the mechanism is not decorative.

**`_verdict`'s blind-spot warning earned its place.** It is the *only* thing in the system that
noticed my A90 literal edit, and it did so by admitting it could not explain a difference rather
than by claiming there was none. A guard that reports what it cannot see is the right shape; the
finding against it (A90) is that it exits 0 and names no value, not that it lies.

**Non-nf-core *wiring* holds — the `entry_channel` claim is true.** A hand-written contract for a
module with no container, no `meta` map, no stub block, no `task.ext.args`, a bare `path` input and
a plain `path … emit:` output routed, materialised, emitted, passed `--gate lint`, passed
`--gate stub` (which does not require a `stub:` block), and ran green under Nextflow 25.10.4
producing correct output. `ModuleContract.nf_inputs` and vocabulary `entry_channel` genuinely do
take the nf-core assumption out of the compiler for everything structural. The failure is confined
to configuration (A93), and that distinction is worth keeping intact when A93 is repaired.

**`MD0213` and `MD0214` fire as documented, observed first-hand.** `MD0213` on an edited
`pipeline.yml` (reported and cured by `emit`, as the schema doc says); `MD0214` verbatim —
*"main.nf changed since it was generated, and re-emitting would overwrite that. Make the change in
build4/pipeline.yml…"* — when I copied a foreign `pipeline.yml` into a built directory. `MD0212`
(duplicate step id) and `MD0215` (exactly one of `source`/`channel`) I verified by reading their
validators while constructing probes around them; I did not trigger them, and say so rather than
claim it.

**Attacked and not substantiated as a finding: `cli.py`'s size.** It is 747 lines and it does contain
work that is not disk-touching — `_frozen_against_moved_contracts`, `_verdict` and `_displacement_line`
are pure functions over `Pipeline` values, and `_verdict` calls `emit()` twice to compare digests.
I could not produce the second half the brief requires: nothing breaks *because* they are there. They
are reachable, they are exercised by the CLI-level tests, and moving them would be tidying. Recorded
as examined and negative.

**Not attacked (out of scope or out of budget):** the three guards (brief §*Scope boundaries*), the
toolchain, the registry's emptiness, `--gate test` beyond what `make verify` runs, `mendel publish`,
`mendel profile`, and the `_ext_scope` GString/closure branch.

---

## Verdict for this stream

**It holds with named repairs**, and two of them are load-bearing before Plan 2.

The compiler is a compiler where it was designed to be one: materialisation, the digest chain,
determinism, `nf_inputs` as a declared call signature, `entry_channel` in the vocabulary, `MD0108`.
Those are not template-renderer properties and they work on modules the authors have never seen.

But `emit` still holds **five facts about the target that no contract can state** — the join for a
multi-port channel (A92), the `[meta, …]` first-input shape (A93), the parameter name for an entry
type (A94), the process name as step identity (A97), and the untyped positional `val` (A90/A91).
Each is right for nf-core and silently wrong elsewhere, and two of them (A92, A94) produce a green
run with wrong data rather than an error.

Ordered by what they cost if deferred:

1. **A92** — silent cross-product. Wrong results, green pipeline, invisible to `--gate test` because
   the test dataset has one sample. Repair before any contract with two per-sample ports is written.
2. **A91 + A90** — the `val` positional. Repair before the forge drafts contracts, because every
   drafted contract will freeze these as unexplained literals and the corpus is where they become
   expensive.
3. **A94** — parameter collision. One line, and the fix is already written down in the docstring of
   the function next door.
4. **A93** — the `meta` shape. Bounds what the forge can ingest; the journal's own reason for running
   this stream first.
5. **A96, A97, A95** — expressiveness and check depth. Each is a `version:` bump or a new diagnostic,
   and each is cheaper before Plan 2 than after.

None of these says the design cannot deliver the claim. All of them say the same thing about how it
currently delivers it: **the contract declares what a module *is*, and the emitter still decides how
it is *called*.** Every finding above is one more fact that needs to move across that line.

---

## Experiment files left behind

All under `audit-tmp/` in this worktree, untracked. Preserve `join/`, `metabare/`, `collide/` and
`regmeta/` — they are small, self-contained registry layers with hand-written non-nf-core modules,
and they are the slow part to recreate.

| path | what |
|---|---|
| `audit-tmp/join/` | **A92, A95.** `PAIRUP` module + layer; `build/` (correct contract, ran, 4 outputs from 2 samples), `layer2`+`build2` (dropped port), `layer3` (MD0108 refusal), `buildstub` (stub gate on a stub-less module) |
| `audit-tmp/metabare/` | **A93.** `PLAINSUM` bare-`path` module + layer; `build/` runs and dies on `getAt` |
| `audit-tmp/collide/` | **A94.** `TWO` module + layer; `build/` shows `params.data` serving `p.data` and `q.data` |
| `audit-tmp/regmeta/` + `audit-tmp/metaprobe/` | **A91.** Registry with `star_ignore_sjdbgtf` routed `via: meta`; the two-values-one-name `main.nf` |
| `audit-tmp/regtwice/`, `qc-goal*.yml`, `twice{,2,3}/`, `dup/` | **A96, A97.** The `fastqc-trimmed` contract, the three goals, and the hand-authored duplicate-process `pipeline.yml` |
| `audit-tmp/spine/`, `litprobe/`, `litupg/`, `det{1..4}/` | **A90** and the determinism check |
| `audit-tmp/prior-nonf/`, `prior-coll/` | copies of the 2026-08-13 stream's artifacts, read as leads |

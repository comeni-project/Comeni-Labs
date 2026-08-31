# What a pipeline takes — channels, cardinality, and the samplesheet

*Written 2026-08-31, after the operator asked for three things on the builder canvas and all
three turned out to be one blocker.*

> **This is Part B of Plan 5, and it runs second.**
> [`2026-08-31-the-registry-and-the-modules.md`](2026-08-31-the-registry-and-the-modules.md) is
> Part A: it takes `vendor/` out of this repository and gives the curated registry a stated,
> checked layout. Both halves edit `registry/`, and doing them in the other order means editing
> the same files twice — `entry_channel` becomes a template *in the new layout*, not in the old
> one and then again.
>
> **The registry is a separate repository.** `registry/` is a submodule of `comeni-registry`,
> pinned at `v0.4.0-2-ga677753`, with its own CC-BY-4.0 licence, signed tags and CI. Eight type
> files, **three of which declare `entry_channel`** — `fastq.reads`, `annotation.gtf`,
> `genome.fasta`. §1.3 and §2.1 are a comeni-registry pull request plus a submodule bump here,
> and §9 says what to watch when the two land together.
>
> **The forge is deferred** by the operator's instruction of 2026-08-31 and this plan does not
> touch it. Part A §5 lists what a registry change does to it, so that it is a recorded
> consequence rather than a later discovery.

---

## 0. The three asks, and the one sentence underneath them

The operator asked, in order:

1. **Rename inputs and outputs** with custom names, and *"there can be multiple outputs"*.
2. *"A pipeline needs to have two same type inputs."*
3. *"It needs to handle batch inputs — a folder/list of fastas, or a list of reads with their
   respective annotations."*

The first is a label and is cheap. The second and third are the same defect, and it is this:

> **A channel's identity and its cardinality are properties of the TYPE, not of the pipeline.**

`registry/types/annotation.gtf.yml` declares

```yaml
entry_channel: "Channel.fromPath(params.gtf, checkIfExists: true).map { gtf -> [ [id: gtf.baseName], gtf ] }"
```

Three things are fused into that one string, and each of them is a decision that belongs to a
*pipeline* rather than to a type:

| Fused in the type | Should belong to | Consequence today |
|---|---|---|
| the param name `params.gtf` | the channel | two `annotation.gtf` inputs are one hole |
| the cardinality `fromPath` (one value) | the channel | a GTF cannot vary per sample |
| the fan-out `fromFilePairs` (per sample) | the channel | reads *must* vary per sample |

And the artifact agrees with the type rather than with the drawing:

- `Goal.have` is a `list[GoalInput]` **deduplicated by `type_id`** (`materialise.goal_of`), so the
  spine's three `annotation.gtf` consumers are one input.
- `StepInput.channel` is a **`TypeId`**, so a port that reads an entry channel names it *by type*.
  Two channels of one type are unaddressable in `pipeline.yml`.
- `_channel_name(type_id)` in `emit.py` derives the Nextflow variable from the type, with a
  docstring already explaining that the *last segment alone* was not injective. The full type id
  is injective over types and is not injective over **channels**, which is the same bug one level
  up.

**The canvas already disagrees with all of this**, and that is what made it visible: it draws one
socket per unwired *port* — five on the spine, three of them `annotation.gtf` — while the goal
holds one input and the emitted workflow has one `params.gtf`. Nothing was wrong on screen until
somebody tried to name them.

### 0.1 Why this is not a UI change with a backend chore attached

The tempting version of this work is: let the canvas draw several inputs, label them, and leave
the resolver alone. That produces a screen saying *liver annotation* and *reference annotation*
above an emitted pipeline that feeds both from one `params.gtf`.

**That is the exact failure this product exists to prevent** — an interface asserting something
the artifact cannot back up. `CLAUDE.md`: *a person reading a value with no reason sees a blank
and asks; a model sees a blank and fills it.* A label over a merged channel is worse than a
blank: it is a filled-in blank that is wrong.

So the resolver changes first, and the labels arrive on top of a model that can hold them.

---

## 1. What a channel becomes

**A `Channel` is a thing the pipeline has, with a name, a param and a scope.** A type stops
declaring *its* channel and starts declaring *how a channel of this type is built*.

### 1.1 `Channel` gains a name and a param

```python
class Channel(BaseModel):
    name: ChannelName          # NEW — `gtf`, `gtf_2`, `reads`. The pipeline's own id.
    type_id: TypeId            # unchanged
    param: NfIdentifier        # NEW — the hole this reads: `params.<param>`
    scope: Scope               # NEW — SAMPLE or RUN, see §2
    params: list[PortName]     # unchanged — what the expression references, MD0211
    expression: GroovyExpression
    meta: list[MetaEntry]
    test_data: list[TestDataRef]
```

`name` is **derived, never typed.** The operator's constraint on 2026-08-31 was explicit —
*"yes it's a label, does not change the actual keys"* — so a person's words never reach a
Groovy identifier, a param name or a file on disk. §5 is where their words do go.

Derivation: the type's last segment, then `_2`, `_3` … in channel order. `annotation.gtf` →
`gtf`, `gtf_2`. Two rules make that safe:

- **Order is the graph's, not the dictionary's.** Channels are numbered by
  `(rank of the first consuming node, node id, port name)`, which is stable under everything
  except a change to the graph that genuinely reorders them. Byte-identical emission for the
  same drawing is a hard requirement (invariant 10) and this is the part of it at risk.
- **The last segment is not injective and the suffix does not fix that.** `qc.report` and
  `multiqc.report` both end in `report` — `_channel_name`'s docstring records that exact
  collision costing two ports the same channel silently. So the derivation is over the **full**
  type id with the suffix applied afterwards, and `MD02xx` refuses a `Pipeline` whose channel
  names are not unique. A derived value that can collide needs a check, not a convention.

### 1.2 `StepInput.channel` becomes a channel name

```python
channel: ChannelName | None = None   # was TypeId | None
```

This is the change that makes two same-type inputs *addressable*, and it is a
**`SCHEMA_VERSION` 5 → 6 break**: every existing `pipeline.yml` names its channels by type. The
migration is mechanical — one channel per type in an old file, so `annotation.gtf` → `gtf` — and
it belongs in the loader beside the other version branches rather than in a script somebody has
to remember to run.

### 1.3 A type declares a template

**This is a change to another repository.** `registry/` is a submodule of `comeni-registry`;
three type files declare an `entry_channel` and all three move. Two directions of compatibility,
and they are deliberately not symmetric:

- **An old registry read by a new resolver** — a literal `params.gtf` with no `{param}` — is a
  **clean refusal**, `MD0228`. A registry whose channel names cannot be controlled is one that
  silently merges two inputs, which is the defect this whole spec exists to remove; carrying on
  quietly would be worse than stopping.
- **A new registry read by an old resolver** — `params.{param}` reaching an emitter that does no
  substitution — must also refuse rather than emit `params.{param}` into Groovy. That check
  belongs in the *current* release, before any registry ships a template: **a version floor on
  the layer**, so an old Mendel says *this registry needs a newer Mendel* instead of writing a
  broken `.nf`. It is a small change and it has to land first or it cannot land at all.



```yaml
# registry/types/annotation.gtf.yml
declares: vocabulary
id: annotation.gtf
entry_channel: "Channel.fromPath(params.{param}, checkIfExists: true).map { gtf -> [ [id: gtf.baseName], gtf ] }"
scope: run          # NEW — the DEFAULT cardinality, overridable per channel
```

One placeholder, `{param}`, substituted at materialisation. **Not a general template language**:
the same argument as Plan 1.15's `transform` — a chain of named operations with a literal operand,
no parser and no precedence. One substitution, checked, and a diagnostic when the template does
not contain it.

`{` is legal Groovy and appears throughout these expressions (`.map { gtf -> … }`), so the
placeholder is matched literally as the seven characters `{param}` and everything else is left
alone. A test over every type in the registry asserts that substituting a known param yields
Groovy that still parses — cheaply, by `nextflow lint` on a generated stub, which the gate
already runs.

---

## 2. Cardinality: `run` and `sample`, and nothing else

**Two scopes, and the third one is a trap.**

| Scope | What it is | Nextflow | Today |
|---|---|---|---|
| `run` | one value for the whole run — a reference genome, an annotation | a value channel | `genome.fasta`, `annotation.gtf` |
| `sample` | one per sample, joined to the others by `meta.id` | a queue channel of `[meta, files]` | `fastq.reads` |

That is the whole of it, and the omission is deliberate. **There is no `group` scope** — no
"per batch", no "per lane", no arbitrary nesting. Every one of those is expressible as a
`sample`-scoped channel with a column that groups, and adding a scope for it would put a join
strategy in the vocabulary where the pipeline cannot see it. If a real case appears that this
cannot express, it arrives as a new scope with a written argument, the way `Kind` gained
exactly two members in Plan 4 phase 4 and refused a third.

### 2.1 Scope is declared by the type and overridden by the channel

A type's `scope:` is what that type *usually* is. A channel may override it, and that override is
the whole of ask (3):

> *a list of reads with their respective annotations*

is `fastq.reads` at `sample` (as always) **and** `annotation.gtf` at `sample` (overridden from
its default of `run`). Two sample-scoped channels are joined on `meta.id`, which is exactly what
nf-core modules already expect to receive.

The override is a **pipeline** decision and is recorded like every other decision: it carries a
`Why`, it exits at a tier, and it appears in `pipeline.yml`. Choosing per-sample annotations over
a shared one is a judgement about an experiment, and the product's claim is that no such
judgement is silent.

### 2.2 What the emitter does with it

**One `sample`-scoped channel** — today's spine — emits what it emits now. `fromFilePairs`, one
queue channel, no samplesheet. This case must not regress: `tests/test_counts.py` is the only
check exercising the v1 criterion and it runs this shape.

**Two or more `sample`-scoped channels** emit a **samplesheet**: `params.input` becomes a CSV
whose columns are the sample-scoped channels, and each channel is a projection of it.

```groovy
ch_rows = Channel.fromPath(params.input, checkIfExists: true).splitCsv(header: true)
ch_reads = ch_rows.map { row -> [ [id: row.sample], [ file(row.fastq_1), file(row.fastq_2) ] ] }
ch_gtf   = ch_rows.map { row -> [ [id: row.sample], file(row.gtf) ] }
```

and the join happens where the two meet a process, by `meta.id`, as nf-core modules already do.

**This means `params.input` changes meaning**, and that is the sharp edge of this spec. Today it
is *reads*: a glob or a list. Under a samplesheet it is *a table*. A pipeline that emits a
samplesheet and one that does not take different things at the same param name, which is a
footgun aimed at a laboratory rather than at us. Two candidate answers, and §7 says which:

- **(a)** `params.input` is always a samplesheet, even for one channel. Uniform, and it breaks
  the one shape that works today for every existing user.
- **(b)** `params.input` is a samplesheet **only** when there is more than one sample-scoped
  channel, and `pipeline.yml` states which form this pipeline wants, in words, next to the
  param. The artifact already carries a `why:` for everything; this is a `what:`.

**(b)**, and the reason is invariant 13's shape rather than convenience: the artifact must be
readable on its own years later, and *"`params.input` is a samplesheet with columns sample,
fastq_1, fastq_2, gtf"* written in the file is worth more than a uniform rule the reader has to
know. A generated `assets/samplesheet_schema.json` is the obvious follow-on and is **out of
scope** here.

### 2.3 What this does NOT do

**It does not read a samplesheet.** Invariant 15 is unmoved: Mendel emits a pipeline that
*references* `params.input`; it never receives one, never parses one, and never learns a sample
identifier. The column names come from **channel names**, which are derived from types. The rows
are the laboratory's and Mendel does not see them.

This is worth stating because "handle batch inputs" could be read as "let me upload a
samplesheet", and that reading is the one thing this must never become.

---

## 3. The goal stops deduplicating

```python
class GoalInput(BaseModel):
    name: ChannelName          # NEW
    type_id: TypeId
    states: frozenset[StateName]
    scope: Scope               # NEW
```

`materialise.goal_of` currently writes

```python
if all(i.type_id != alternative.type_id for i in have):
    have.append(GoalInput(type_id=alternative.type_id))
```

which is the deduplication, in one line. It becomes one `GoalInput` per **channel**, where the
set of channels is a property of the drawing (§4).

### 3.1 Routing is unaffected, and that is worth checking rather than assuming

`producers_of` matches a requirement against a contract's `produces` **by type and states**. A
channel is not a producer and never was — `StepInput` distinguishes `source` from `channel` with
`MD0215` — so nothing in the ranking `(surplus, -priority, id)` sees a channel at all.

What *does* change is `Goal.have`: a goal that says *I have two annotations* is a different goal
from one that says *I have an annotation*, so the same drawing before and after this change
resolves to a different `Goal`. That is correct and it is also a **golden-file break across the
board**. Expect every `.nf` and every `pipeline.yml` fixture to move.

### 3.2 Byte-identical emission, which is invariant 10

`Goal.have` is sorted by `type_id` today, for exactly this reason. It becomes sorted by
`(type_id, name)` — and since `name` is derived from a graph order that is itself stable, the
whole chain from drawing to `.nf` stays deterministic. The test that already asserts *same goal
in, byte-identical `.nf` out* is the one that has to keep passing, and a second one is owed:
**same drawing in, same channel names out**, over a graph whose nodes are given in a different
order.

---

## 4. Where channels come from on the canvas

Today the canvas derives sockets from unwired ports (`Sources.entryChannels`) and the goal
derives inputs from the same ports, deduplicated — two derivations, one of which the person can
see. Under this spec **the channel set is part of the draft**, because whether two GTF ports are
one channel or two is a decision only a person can make.

```python
class DraftChannel(BaseModel):
    key: str                  # `<node>.<port>`, or several of them
    ...
```

The default is **one channel per type**, which is today's behaviour and the right answer for the
spine's shared reference annotation. Splitting it is a control on the canvas — the operator's
*"multiple of the same type"* — and merging two back is the same control in reverse.

### 4.1 Outputs are drawn, and there is more than one

`goal_of` computes `want` as every unwired `produces` and **the canvas draws none of them.**
There is no output node on the builder at all; a terminal `counts.matrix` is an unwired port with
nothing marking it as the thing the pipeline is *for*. So:

- one **OUTPUT** node per terminal port, the mirror of the INPUT socket,
- several of them where there are several, which the operator asked for and which `want` has
  always supported,
- and each one labelled (§5).

This is the cheapest part of the whole spec and the most visible, and it is a phase of its own
so that it can land early.

---

## 5. Labels — the operator's words, and where they stop

```python
class DraftLabel(BaseModel):
    key: str                  # the channel's identity on the canvas
    label: Line = ""          # Mark.FREE_TEXT, one line
```

**On the draft, never in the artifact.** *"Yes it's a label, does not change the actual keys."*

| | derived | typed by a person |
|---|---|---|
| channel name (`gtf_2`) | ✓ | |
| param (`params.gtf_2`) | ✓ | |
| samplesheet column | ✓ | |
| Nextflow variable | ✓ | |
| what the canvas shows | | ✓ |

That table is the whole safety argument, and it has a second half: **a label never crosses an
egress door.** `tests/test_egress.py` holds fourteen free-text fields literally, and this adds
none — a `DraftGraph` is not a door payload, and `materialise` does not read `labels`. If a later
change wants the label in `pipeline.yml`, that is a new entry on the list of fourteen and it gets
the argument the tenth one got, in writing, before it is added.

The reason to be this careful about a *label* is invariant 15. A field a person types into, which
names an input, is one rename away from being `/data/patients/PT-4471023/`. Keeping it off the
key and out of the artifact means the worst case is a private note in a Postgres row.

---

## 6. Diagnostics

New codes in the `MD02xx` band (artifact), continuing from `MD0225`:

| Code | Refuses |
|---|---|
| `MD0226` | two channels sharing a `name` |
| `MD0227` | a `StepInput.channel` naming no declared channel |
| `MD0228` | an `entry_channel` template with no `{param}` |
| `MD0229` | a samplesheet form with fewer than two `sample`-scoped channels, or a non-samplesheet form with more than one |

`MD0229` is the one that earns its place: it is the check that `params.input`'s two meanings
(§2.2) can never both be claimed by one artifact.

Every code is declared in `diagnostics.yml` and emitted through `coded()` — never written into a
string by hand — and both directions are already tested.

---

## 7. What this spec deliberately does not do

- **No samplesheet schema file.** `assets/schema_input.json` is what nf-core ships and it is a
  natural follow-on; it is not needed to emit a working pipeline and it doubles the surface.
- **No `group` scope.** §2.
- **No reading of any samplesheet, ever.** §2.3.
- **No reachability, staging estimates or run-shape history.** The run sheet's artboard shows
  *"14 GB will be staged first, about 6 minutes"* and none of it is knowable on this side of the
  boundary. The sheet already says so by absence.
- **No change to `producers_of` or the tier ladder.** §3.1.

---

## 8. Phases

Sized so that each one ends with `make verify` green and something visible.

| Phase | What | Why here |
|---|---|---|
| **1** | **Outputs on the canvas, and labels.** `DraftLabel`, `DraftChannel` with the default one-channel-per-type, OUTPUT nodes, renaming both. No resolver change. | Visible immediately, and it is the half that cannot break an emitted pipeline. It also puts the *drawing* in a shape the later phases can read. |
| **2** | **A channel is named.** `Channel.name` + `param`, `StepInput.channel` → `ChannelName`, `_channel_name` off the name, `entry_channel` templates, `SCHEMA_VERSION` 5 → 6 with the loader migration, `MD0226`–`MD0228`. Still one channel per type. | The rename, with no behaviour change. Every golden file moves and nothing else does, which makes the diff readable. |
| **3** | **Two channels of one type.** `goal_of` stops deduplicating, `GoalInput.name`, the canvas's split/merge control, the ordering rule and its determinism test. | Ask (2), and the first phase where a drawing can express something it could not before. |
| **4** | **Scope.** `Scope`, the type's default, the pipeline's override with a `Why` and a tier, run-scoped and sample-scoped emission unchanged for one channel. | Ask (3), first half. The spine must emit byte-identically here — that is the phase's own check. |
| **5** | **The samplesheet.** Two or more sample-scoped channels, `splitCsv`, the column derivation, `params.input`'s declared form, `MD0229`. | Ask (3), second half, and the only phase that changes what a laboratory types on the command line. |

**Phase 1 is independent of 2–5** and can land on its own if the rest is deferred.

---

## 9. What to be suspicious of when executing this

- **The estimate.** `CLAUDE.md`'s rule is that an estimate wrong by more than about double is a
  decision point. Phase 5 is the one to watch: `splitCsv` over a header the artifact declares,
  joined by `meta.id`, against modules whose input arity varies — `NfInput.empty` exists because
  a 2-tuple in a 3-tuple slot dies on *"Path value cannot be null"*, and this phase creates new
  chances for exactly that.
- **`make check` is not verification here.** Every one of these phases touches `emit.py` or
  `pipeline.py`, which `CLAUDE.md` names explicitly: run **`make verify`**.
- **The stub gate cannot see a hollow input.** `-stub-run` never reads its inputs, so a
  samplesheet column wired to nothing is exactly as green as one wired correctly. Only
  `--gate test` catches it, and phase 5's checkpoint has to be a real one.
- **A guard that passes on the code it was written to reject.** Phase 4's danger: a determinism
  test that passes whether or not scope is respected, because the spine has one sample-scoped
  channel either way. Watch it fail against the specific defect, not merely watch it fail.

---

## 10. Attacking this design — a bioinformatics review

*Run 2026-08-31 at the operator's instruction: "will this be a viable shape? attack it from a
bioinformatics standpoint — what a pipeline needs." Six findings. The first is a defect in the
pipeline this repository emits **today**, and it converts `scope` from a feature into a fix.*

### 10.1 A reference is a queue channel, so the spine analyses ONE sample

**This is a live bug, not a design risk.** `tests/golden/spine/main.nf`:

```groovy
ch_annotation_gtf    = Channel.fromPath(params.gtf, checkIfExists: true).map { … }
ch_genome_index_star = Channel.fromPath(params.star, checkIfExists: true).map { … }
ch_fastq_reads       = ( … Channel.fromFilePairs(params.input, …) … )

STAR_ALIGN(TRIMGALORE.out.reads, ch_genome_index_star, ch_annotation_gtf, false)
```

`Channel.fromPath` produces a **queue** channel. A Nextflow process with several queue-channel
inputs runs as many times as the **shortest** of them. Reads has N items; the index has one; the
GTF has one. So with twenty-four samples, **`STAR_ALIGN` runs once and twenty-three samples are
silently dropped.** There is no `.collect()`, no `.first()` and no `Channel.value` anywhere in
`emit.py` — grep confirms it.

**Nobody noticed because the stub profile has one sample pair.** `params.input` is a glob over
`stub-data/*_R{1,2}.fastq.gz`, so N = 1 and the shortest channel is every channel. The gate is
green, `test_counts.py` gets its matrix, and the pipeline is wrong for every real dataset.

That is *"same goal in → same pipeline out"* producing a pipeline that quietly analyses one
sample, which is the worst shape a defect can take here.

**The fix is exactly §2's `scope`, which is why this finding is the argument for it.** A
`run`-scoped channel must be emitted as a **value channel** — `.collect()` for a set,
`.first()` for a single file — so it can be consumed any number of times. `sample`-scoped stays
a queue. The distinction is not a convenience for expressing per-sample references; it is what
makes a shared reference correct at all.

**It also has to be tested against the defect and not merely against itself.** A determinism test
over the spine passes either way, because the spine has one sample-scoped channel and one sample
in its fixture. **The check is a stub run with two sample pairs asserting the process ran twice**
— watched failing against today's emitter first.

### 10.2 There is no fan-in, and `cardinality` is declared but never emitted

`MULTIQC`'s contract consumes `qc.report` from every sample and aggregates them:

```yaml
consumes: [{name: reports, type_id: qc.report, state_required: []}]
produces: [{name: report, type_id: qc.report, state: [aggregated]}]
```

The emitter would write `MULTIQC(ch_qc_report)` — **one invocation per sample, producing N
reports where the point of the tool is to produce one.** `InputPort.cardinality` exists, defaults
to `"1"`, and has exactly one reader: `validate.py`, refusing more than one *wire*. It says
nothing about how many *items* a port consumes and nothing reaches the emitter.

This is the same axis as scope — **how many things arrive on this port** — and it belongs in the
same work rather than being discovered when somebody adds MultiQC to the spine:

- `cardinality: "1"` — one item per invocation, today's emission.
- `cardinality: "*"` — the whole channel, emitted `.collect()`, one invocation.

MultiQC is not in the spine, so nothing is broken right now; a contract for it is in the registry
and would be wrong the moment it routed. **Phase 4 is where this lands**, beside `run` scope,
because both are "make this port a value channel" with different arithmetic.

### 10.3 A samplesheet has columns that are not files — and that is the MVP-shaped gap

§2.2 derives samplesheet columns from **sample-scoped channels**, which are files. A real RNA-seq
samplesheet is not:

```csv
sample,fastq_1,fastq_2,strandedness
CONTROL_REP1,AEG588A1_S1_L002_R1.fastq.gz,AEG588A1_S1_L002_R2.fastq.gz,auto
```

`strandedness` is a **measurement**, and measurements live on `Goal.profile` — **one value for the
whole run**. So is `paired`. A dataset mixing single- and paired-end samples, or reverse- and
unstranded libraries, cannot be described, and those are ordinary rather than exotic.

**This is the finding most likely to be hit during the MVP** and it is deliberately *not* solved
here, because solving it means per-sample measurements, which means a tier-3 rule can fire
differently per sample, which means `DecisionRecord` is no longer one record per decision. That is
a larger change than this spec and it should not be smuggled in.

**What this spec does instead is refuse to half-do it**: a samplesheet carries file columns only,
`MD0229` states the form in the artifact, and the limitation is written on the run sheet where a
person can see it — *these values apply to every sample*. A pipeline that silently applied one
sample's strandedness to twenty-four would be §10.1 in a new costume.

### 10.4 `meta.id` collides when a sample is sequenced more than once

Two sample-scoped channels join on `meta.id`. A sample split across lanes or flowcells is several
rows with one sample id — nf-core's answer is `cat_fastq`, a grouping step before anything else.
Under this spec those rows collide and the join is wrong rather than refused.

**Cheap partial answer, and it belongs in phase 5:** the samplesheet's key is `(sample, *)` and a
duplicate sample id is a **refusal** with a message naming the rows. Refusing is honest and cheap;
merging is a pipeline-shape decision that needs the grouping step §10.5 cannot express either.

### 10.5 Scatter/gather is not expressible, and that is pre-existing

Split a BAM by chromosome, call variants on each, merge. The contract model is *this consumes a
type and produces a type* — there is no `groupTuple`, no `splitFastq`, no notion of a step that
changes cardinality on its way through. That limits Mendel to pipelines that are one pass per
sample plus aggregations.

**Named rather than fixed.** It does not block the RNA-seq spine, it does block variant calling,
and it is a plan of its own. What matters is that it is written down, because the difference
between *"we decided not to"* and *"nobody thought of it"* is the difference between a roadmap and
a surprise.

### 10.6 Optional inputs are not modelled

nf-core modules routinely take `path(bed), optional: true`. `NfInput.empty` exists for **tuple
width** — a 2-tuple in a 3-tuple slot dies on *"Path value cannot be null"* — and it requires a
`because`, which is adjacent to but not the same as a port that may legitimately have nothing on
it. Minor next to the rest, and worth an issue rather than a section.

### 10.7 What survives the attack

The core shape holds. **A channel with a name, a param and a scope is the right object**, and
§10.1 is the proof: the model without it emits pipelines that are wrong on real data. The two
scopes are enough for everything examined here except §10.3 and §10.5, both of which are named
and neither of which the design forecloses — a per-sample measurement is a third thing a
samplesheet column can be, and it slots into the same table.

**What changes in this spec as a result:** phase 4 absorbs `cardinality: "*"` (§10.2) and gains
the two-sample check (§10.1); phase 5 gains the duplicate-sample refusal (§10.4); §2.3 gains the
sentence about what a samplesheet may not carry (§10.3).

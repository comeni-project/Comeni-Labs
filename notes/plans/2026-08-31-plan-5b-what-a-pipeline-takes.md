# Plan 5, Part B — what a pipeline takes

**Spec:** [`../specs/2026-08-31-what-a-pipeline-takes.md`](../specs/2026-08-31-what-a-pipeline-takes.md).
Read it first, including §10–§12, which are three adversarial passes over it. Every task below
cites the section it implements.

**Runs after Part A**, which is
[`2026-08-31-plan-5a-the-registry-and-the-modules.md`](2026-08-31-plan-5a-the-registry-and-the-modules.md).
`entry_channel` becomes a template **in the new layout**, not in the old one and then again.

**Phase 1 is independent of 2–5** and can land alone — it is the visible half and it changes no
resolver behaviour.

**`make check` is not verification for phases 2–5.** They touch `emit.py` and `pipeline.py`.
Run **`make verify`**, and treat the nightly stub gate as the checkpoint for 4 and 5.

---

## Phase 1 — outputs on the canvas, and labels

*No resolver change, no artifact change, no registry change. It cannot break an emitted pipeline,
and it puts the drawing into a shape the later phases read.*

### 1.1 Outputs are drawn — spec §4.1

- [x] `goal_of` computes `want` as every unwired `produces` and **the canvas draws none of them.**
      There is no output node on the builder at all; a terminal `counts.matrix` is an unwired port
      with nothing marking it as the thing the pipeline is *for*.
- [x] One **OUTPUT** node per terminal port, the mirror of the INPUT socket — dashed, blue-edged,
      no settings, `impl-inv`'s shape for a thing that carries a type and never a path.
- [x] **Several of them where there are several.** The operator asked for it and `want` has always
      supported it.
- [x] `Sources.tsx`'s socket-gutter arithmetic applies in reverse: an output needs clear space to
      its **right**, and a node at the last rank has it by construction.

### 1.2 Labels — spec §5

- [x] `DraftLabel { key, label: Line }` on `DraftGraph`. `key` is `<node>.<port>` — **not a
      `NodeId`**: a port is not a node, and a label should survive its node being dragged but not
      its port being rewired.
- [x] **Draft-only.** Nothing in `materialise` reads it. It does not become a `params.<name>`, it
      does not reach `pipeline.yml`, and no resolver sees it — the operator's constraint was *"yes
      it's a label, does not change the actual keys."*
- [x] Renaming works on both INPUT and OUTPUT nodes, in place on the canvas.
- [x] **A guard that a label reaches nothing.** Two drafts differing only in labels emit
      byte-identical `.nf` and identical `pipeline.yml`. Watched failing against a version that
      threads the label into the channel name.
- [x] **`tests/test_egress.py` is untouched**, and that is the assertion: fourteen free-text
      fields, still fourteen. A `DraftGraph` is not a door payload.

### 1.3 Checkpoint

- [x] `make verify` green, frontend suite green.
- [x] On screen: a pipeline with several named inputs and several named outputs, and an emitted
      `.nf` byte-identical to the one before the labels were typed.

---

## Phase 2 — a channel is named

*The rename, with no behaviour change. Every golden file moves and nothing else does, which is
what makes the diff readable.*

### 2.1 The version floor, and it lands FIRST — spec §1.3

- [x] **Before any registry ships a template**, the *current* release must refuse one. A new
      registry's `params.{param}` reaching an emitter that does no substitution would write
      `params.{param}` into Groovy.
- [x] A **version floor on the layer**: `registry.yml` declares the minimum Mendel it needs, and
      an older Mendel says *this registry needs a newer Mendel* instead of emitting broken Nextflow.
- [x] It is a small change and **it has to land first or it cannot land at all.**

### 2.2 The types

- [x] `Channel` gains `name: ChannelName` and `param: NfIdentifier`.
- [x] `StepInput.channel` becomes `ChannelName | None` — was `TypeId | None`. **This is the change
      that makes two same-type inputs addressable.**
- [x] `entry_channel` becomes a one-placeholder template: `params.{param}`. **Not a template
      language** — one substitution, the same argument as Plan 1.15's `transform`. `{` is legal
      Groovy and appears throughout these expressions, so the placeholder is matched as the
      literal seven characters `{param}`.
- [x] `MD0226` two channels sharing a name · `MD0227` a `StepInput.channel` naming no declared
      channel · `MD0228` an `entry_channel` with no `{param}`.
- [x] A test over every type in the registry: substituting a known param yields Groovy that still
      parses, via `nextflow lint` on a generated stub.

### 2.3 Ordering is on SHAPE, never on identity — spec §11.2

- [x] Channels are numbered by **`(rank, order-within-rank, port index)`** — `dag-core`'s own
      layout arithmetic, and **no node id anywhere**.
- [x] **Why:** `useGraph.nextId` mints `star_align_1`, `star_align_2` … from the ids currently
      *taken*. Add two STAR nodes and delete the first and the survivor is `star_align_2`; draw one
      and it is `star_align_1`. Two structurally identical graphs, two different node ids — so any
      ordering keyed on them makes a person's `params.*` depend on the order they clicked.
- [x] Derivation is over the **full type id** with a `_2`, `_3` suffix, not the last segment:
      `qc.report` and `multiqc.report` both end in `report`, and `_channel_name`'s docstring
      records that collision costing two ports the same channel silently.
- [x] `MD0226` refuses a `Pipeline` whose channel names are not unique. **A derived value that can
      collide needs a check, not a convention.**

### 2.4 `SCHEMA_VERSION` 5 → 6, and the migration decides — spec §12.2

- [x] The loader migrates: an old file names its channels by type, one channel per type, so
      `annotation.gtf` → `gtf`. In the loader beside the other version branches, **not a script
      somebody has to remember to run.**
- [x] **The migration records that it decided.** A `Why` at a tier — *migrated from schema 5;
      name derived from the type, which is what this pipeline's behaviour already was.*
- [x] **`upgrade` replays it rather than re-deriving it.** `mendel upgrade` re-resolves against the
      current registry and replays every recorded decision so only what you touched can move —
      issue #10 closed on that property. If the migration's names and a fresh derivation's names
      differ by one, every `params.*` in a laboratory's command line renames itself on an upgrade
      they asked for to pick up a registry fix.
- [x] **The test, and it is the phase's real check:** migrate a v5 artifact, upgrade it, assert the
      emitted `.nf` is byte-identical to the v5 artifact's. Watched failing against a migration
      that assigns silently.

### 2.5 The API, which neither spec covered — spec §12.3

- [x] `BuiltPipeline` gains `channels: list[ChannelView]` — name, type, scope, the ports it feeds.
- [x] **`Sources.entryChannels()` is DELETED**, not left beside it. Two derivations of one fact is
      the defect this whole plan started from; keeping the old one "for now" is how it survives.
- [x] The canvas draws a node per **channel** rather than per unwired port. This is also what makes
      phase 3's split/merge possible at all — you cannot split a thing recomputed from scratch on
      every render.
- [x] **Why this is a task and not a footnote:** §0's finding was that the canvas derives its own
      answer and disagrees with the artifact. Part A fixes the registry and Part B fixes the
      resolver, and without this the canvas would disagree *again* — in a new way, because now
      there really are named channels for it to disagree with.

### 2.6 The registry side

- [x] Three type files change — `fastq.reads`, `annotation.gtf`, `genome.fasta`. A
      `comeni-registry` PR plus a submodule bump, **registry PR first**.
- [x] An **old registry read by a new resolver** — a literal `params.gtf`, no `{param}` — is a
      clean refusal, `MD0228`. Carrying on quietly would silently merge two inputs, which is the
      defect this plan exists to remove.

---

## Phase 3 — two channels of one type

*The first phase where a drawing can express something it could not before.*

- [x] `goal_of` stops deduplicating. It currently writes
      `if all(i.type_id != alternative.type_id for i in have)` — that one line is the whole of it.
- [x] `GoalInput` gains `name: ChannelName` and `scope: Scope`.
- [x] `Goal.have` sorts by `(type_id, name)`. It sorts by `type_id` today because a `Goal` reaches
      `pipeline.yml` and byte-identical output is a hard requirement (invariant 10).
- [x] **`DraftChannel` on the draft**: whether two GTF ports are one channel or two is a decision
      only a person can make. The **default is one channel per type**, which is today's behaviour
      and the right answer for the spine's shared reference annotation.
- [x] The canvas's **split / merge** control — the operator's *"multiple of the same type"* — and
      merging two back is the same control in reverse.
- [x] **Routing is unaffected, and that is checked rather than assumed** (§3.1): `producers_of`
      matches a requirement against `produces` by type and states; a channel is not a producer and
      never was, which `StepInput`'s `source`/`channel` split and `MD0215` already enforce.
- [x] **The determinism test §3.2 owes**: build the same pipeline twice by different routes — add
      and delete nodes on one path — and diff the emitted `.nf`. Watched failing against an
      ordering keyed on node ids.

---

## Phase 4 — scope, and the two channel bugs it fixes

*The correctness phase. Both defects are live in what this repository emits today.*

### 4.1 The scope

- [x] `Scope` with **exactly two members**, `RUN` and `SAMPLE`. **No `group` scope** — every case
      for one is expressible as a sample-scoped channel with a column that groups, and a scope for
      it would put a join strategy in the vocabulary where the pipeline cannot see it. If a real
      case appears, it arrives as a new member with a written argument, the way `Kind` gained
      exactly two in Plan 4 phase 4 and refused a third.
- [x] A type declares its **default** scope; a channel may **override** it.
- [x] The override carries a `Why`, exits at a tier and appears in `pipeline.yml`. Choosing
      per-sample annotations over a shared one is a judgement about an experiment, and the
      product's claim is that no such judgement is silent.

### 4.2 The live bug — spec §10.1

- [x] **`tests/golden/spine/main.nf` builds `ch_genome_index_star` and `ch_annotation_gtf` with
      `Channel.fromPath` — queue channels of one item.** `STAR_ALIGN` consumes three queue
      channels, and a Nextflow process runs as many times as the **shortest**. With twenty-four
      samples it runs **once** and twenty-three are silently dropped. There is no `.collect()`,
      `.first()` or `Channel.value` anywhere in `emit.py`.
- [x] Nobody noticed because the stub profile globs **one** sample pair, so N = 1 and the shortest
      channel is every channel. Green gate, correct counts matrix, wrong pipeline for real data.
- [x] **A `RUN`-scoped channel emits as a VALUE channel** — `.first()` for a single file,
      `.collect()` for a set — so it can be consumed any number of times. `SAMPLE`-scoped stays a
      queue.
- [x] **The check is a stub run with two sample pairs asserting the process ran twice**, watched
      failing against today's emitter. **Not** a determinism test over the spine: that passes
      either way on a one-sample fixture, which is the guard-that-proves-nothing shape this
      repository has already paid for twice.
- [x] The stub-data fixture gains a second sample pair.

### 4.3 Fan-in — spec §10.2

- [x] `InputPort.cardinality` exists, defaults to `"1"`, and has exactly one reader —
      `validate.py`, refusing more than one *wire*. It says nothing about how many **items** a port
      consumes and **nothing reaches the emitter**.
- [x] `cardinality: "*"` emits `.collect()`: one invocation over the whole channel.
- [x] MULTIQC's contract consumes `qc.report` from every sample. Today it would emit
      `MULTIQC(ch_qc_report)` — **one invocation per sample, producing N reports where the point of
      the tool is to produce one.** It is not in the spine, so nothing is broken right now; the
      contract is in the registry and would be wrong the moment it routed.
- [x] Same phase as 4.2 because it is the same arithmetic: *make this port a value channel*.

### 4.4 The spine changes, and that is expected

- [x] The emitted `.nf` is **not** byte-identical to phase 3's — a reference becomes a value
      channel. Golden files move. The invariant that must hold is *same goal in → byte-identical
      out*, not *the same bytes as last week*.

---

## Phase 5 — the samplesheet

*The only phase that changes what a laboratory types on the command line.*

### 5.1 The emission — spec §2.2

- [x] **One** sample-scoped channel emits what it emits now: `fromFilePairs`, one queue channel, no
      samplesheet. **This must not regress** — `tests/test_counts.py` is the only check exercising
      the v1 criterion and it runs this shape.
- [x] **Two or more** emit a samplesheet: `params.input` is a CSV whose columns are the
      sample-scoped channels, each channel a projection of it, joined at the process by `meta.id`.
- [x] Column names come from **channel names**, which are derived from types. Rows are the
      laboratory's and Mendel never sees them.

### 5.2 `input_form`, and why it is an enum — spec §11.1 and §12.1

- [x] `Pipeline.input_form: InputForm` — `SAMPLESHEET | DIRECT`. **A closed enum, not prose.**
- [x] §2.2 originally asked the artifact to say which form it wants *"in words, next to the
      param"*. `Pipeline` is door 4's payload, so **words next to a param is a fifteenth free-text
      field**, in a spec whose §5 claims it adds none. The two sentences contradicted each other.
- [x] The **words** a reader needs — *"a samplesheet with columns sample, fastq_1, fastq_2, gtf"* —
      are **generated** from `input_form` plus the channel names. Nobody authors a string, nothing
      new crosses a door, and the artifact still reads as prose because `mendel emit` writes the
      comment.
- [x] **The general rule this nearly broke, worth carrying beyond this plan:** when a fact is a
      closed choice, put the choice in the artifact and generate the sentence. A field that exists
      so a file can explain itself is how a boundary widens one entry at a time.
- [x] `MD0229`: a samplesheet form with fewer than two sample-scoped channels, or a non-samplesheet
      form with more than one. **It is the check that `params.input`'s two meanings can never both
      be claimed by one artifact.**

### 5.3 Wiener has to know — spec §12.1

- [ ] **Two same-type channels work by construction, and that is worth noticing.**
      `declared_holes` reads the artifact's **nulls**, so `params.gtf` and `params.gtf_2` are two
      nulls, Wiener asks for two files, and nothing on that side changes.
- [ ] **The samplesheet does not.** `params.input` is **one null whether it is a fastq glob or a
      CSV path**, so the run sheet asks the same question and a person answers it with the wrong
      kind of thing. The run fails inside Nextflow minutes later, and the one place that could have
      said so is the form that asked.
- [ ] `wiener_api.services.artifacts` already loads the artifact with `Pipeline.model_validate`, so
      **`input_form` is one field access away.** `declared_holes` returns holes with a *shape*;
      `input` carries `SAMPLESHEET` and its column list.
- [ ] The run sheet renders a **samplesheet builder** rather than a path box. A Wiener change
      inside a Mendel plan, and small precisely because `wiener.md` §12's design — *the browser
      posts the artifact and Wiener reads its holes back out* — already put the artifact in the
      right place.
- [ ] **Two independent arguments reached one design** — the egress boundary in 5.2 and this — and
      that is the strongest signal in the spec. Recorded rather than left as a coincidence.

### 5.4 Duplicate sample ids — spec §10.4

- [x] Two sample-scoped channels join on `meta.id`. A sample split across lanes or flowcells is
      several rows with one id, and nf-core's answer is `cat_fastq` — a grouping step before
      anything else.
- [x] **A duplicate sample id is a refusal**, with a message naming the rows. Refusing is honest
      and cheap; merging is a pipeline-shape decision needing the grouping §10.5 says the contract
      model cannot express at all.

### 5.5 The checkpoint

- [ ] **`--gate test` is the real one.** `-stub-run` never reads its inputs, so a samplesheet column
      wired to nothing is exactly as green as one wired correctly. Two modules shipped that way
      before — STAR built an index from nothing and aligned against no annotation.
- [ ] **Watch the estimate here.** `CLAUDE.md`'s rule is that an estimate wrong by more than about
      double is a decision point. `splitCsv` over a declared header, joined by `meta.id`, against
      modules whose input arity varies — `NfInput.empty` exists because a 2-tuple in a 3-tuple slot
      dies on *"Path value cannot be null"*, and this phase creates new chances for exactly that.

---

## What this plan does not do

Named so the difference between *we decided not to* and *nobody thought of it* stays visible:

- **Per-sample metadata that is not a file** (§10.3) — `strandedness`, `paired`, condition,
  replicate. They are **measurements**, and measurements live on `Goal.profile`, one value for the
  whole run. A dataset mixing single- and paired-end samples cannot be described. **This is the
  gap most likely to be hit during the MVP**, and it is not solved here because solving it means
  per-sample measurements, which means a tier-3 rule can fire differently per sample, which means
  `DecisionRecord` is no longer one record per decision. The run sheet says *these values apply to
  every sample* rather than half-doing it.
- **Scatter/gather** (§10.5) — split a BAM by chromosome, call on each, merge. The contract model
  is *this consumes a type and produces a type*; there is no step that changes cardinality on its
  way through. Blocks variant calling, not RNA-seq.
- **Optional inputs** (§10.6) — modules routinely take `path(bed), optional: true`. An issue, not a
  section.
- **A samplesheet schema file** — nf-core's `assets/schema_input.json` is a natural follow-on and
  doubles the surface.
- **Reading a samplesheet, ever** (§2.3). Invariant 15 is unmoved: Mendel emits a pipeline that
  *references* `params.input`, never receives one, never parses one, never learns a sample
  identifier. *"Handle batch inputs"* could be read as *"let me upload a samplesheet"*, and that
  reading is the one thing this must never become.

---

## Execution record

| Phase | Carried out as written? | Deviation |
|---|---|---|
| 1 | Yes, with six | See below |
| 2 | | |
| 3 | | |
| 4 | Yes, and **one of its boxes was ticked before it was done** | 4.1's third bullet — *the override carries a `Why`, exits at a tier and appears in `pipeline.yml`* — was ticked when 4.2 landed and had not been implemented. A tick means *this step was carried out*, and that one was a claim. Corrected and then done. **The egress guard refused the first design twice**, and was right both times: `IRChannel.scope` as a bare `str` is how a closed vocabulary stops being closed, and `IRChannel.why` as a `Line` would have been invariant 14's **fifteenth** free-text field. It is a `ResolvedValue` — a scope override *is* a value somebody settled, at a tier, for a reason, against an axis — so `reason` and `axis_reason` are already fields 3 and 12 and the boundary does not widen. `Scope` moved to `plan/tiers.py` beside `Tier` and `ValueSource`, because `plan/ir.py` importing from `artifact/` is backwards |
| 5 | | |


### Phase 1 — the six deviations

1. **INPUT and OUTPUT are one component, not two.** The plan says the gutter arithmetic "applies
   in reverse"; writing it twice is how the two gutters come to disagree, so `place(kind, …)`
   holds it once and `Socket` renders either side. The only thing that differs is which edge of
   the box the stub leaves from and which corner is rounded.

2. **`terminals()` was written, exported, and then folded back into the component.** It was the
   mirror of `entryChannels`, which is exported because the run sheet is a second reader — and an
   output is bound by nobody, so the mirror had no second reader at all. Shipping it would have
   been `OpenQuestion.suggested`'s shape in reverse: a producer with no consumer. Spec §12.3
   deletes `entryChannels` in phase 2 anyway.

3. **`Mark.SOCKET_KEY` and `SocketKey` are new.** The plan says `key` is `<node>.<port>` and not a
   `NodeId`; it does not say what type carries it, and a bare `str` is what `marks.py` exists to
   prevent. `SocketKey` is `_joined_identifier` restricted to `.` — narrower than `DecisionKey`,
   which also permits `:` because a `Subject` carries one.

4. **`Minimap.bounds` gained a `GUTTER`, which is a pre-existing defect this phase made visible.**
   `SOCKETS = 96` accounted for the socket overhang *below* and nothing accounted for the 240px
   gutter to the left, so *Fit* had always cut the INPUT sockets off the left edge. Nothing was
   drawn on the right, so the asymmetry was invisible until an OUTPUT socket went there.

5. **The `.nf` half of the label guard could not be watched failing against a real defect, and the
   ledger says so.** Threading a label into `ir_of`'s `selection.reason` — the smallest leak
   somebody would actually write — failed two of the six tests and correctly did not fail the
   emission one: a reason reaches `pipeline.yml` and never the workflow. The leak that test exists
   for needs `Channel.name`, which is phase 2. A probe showed the comparison is live (`True` →
   `False` when `_channel_name` changes between the two emissions), and the ledger records that
   *capable of failing* is not *watched failing*.

6. **A real bug, found by the first test written against an output.** `place()` returned a key
   called `port` holding a coordinate, spread beside the `PortView` it belonged to — so every
   socket rendered its kind and nothing else. It is `tip` now.

### Phase 1 — what the screen showed

Done, on `localhost:5173/build` against the whole stack. The spine drew **five INPUT sockets and
one OUTPUT** (`counts.matrix[gene_level]`, in the right-hand gutter at the last rank, with its
stub); two inputs and the output were renamed in place; the draft **saved**, so a label
round-trips through the API into Postgres; and no console errors.

**`make dev` could not start, and the message that stopped it advertised a fix that did not
work.** `names-free` refused because the sibling worktree owns the container names — correctly —
and told us to set the `*_CONTAINER_NAME` lines in `.env`. Doing that changed nothing, for two
reasons that are the same mistake: the check read the **shell**, which `make` never loads `.env`
into, and **five of the nine names were hardcoded** even though `docker-compose.yml` makes every
one of them overridable. It reads `docker compose config` now, which resolves `.env` the same way
`up` will, and it was watched still refusing a genuine collision.

**The run sheet is the live proof of spec §0**, and it is worth carrying into phase 2. It lists
what a person must bind, and it listed **`gtf annotation.gtf` twice and `annotation
annotation.gtf` once** — three rows for what the artifact merges into one `params.gtf`. That is
the canvas and the goal disagreeing, on the one screen where the disagreement costs a laboratory
something: bind those three separately and two of the answers go nowhere. The labels correctly do
**not** appear here — the sheet reads the artifact's holes, and a label is not in the artifact.


### Phase 2.1–2.4 — carried out, with four deviations

**2.1 is a format level, not a Mendel version.** §2.1 asks the layer to declare *"the minimum
Mendel it needs"* and there is no such number — releases here are per package and independent, so
a registry would have to name a minimum `mendel-resolver` **and** a minimum `mendel-compiler` and
get both right. The layer declares what it uses, Mendel declares what it understands. The
sentence a person reads is still §2.1's.

**A type declares its `param`, which neither spec nor plan mentions.** `fastq.reads` reads
`params.input` and every other shipped type reads its last segment. Deriving the param from the
channel name would have renamed it to `params.reads` — a change to *what a laboratory types*,
inside the phase described as *"the rename, with no behaviour change"* — and would have dissolved
the very ambiguity §12.1 says phase 5 has to solve. `nextflow.config` is byte-identical across
the whole phase, which is that decision paying off.

**2.3's `(rank, order-within-rank, port index)` key is deferred to phase 3, and the reason is
that it is not yet needed.** §11.2's defect is an order keyed on *node ids*, which are minted
from what is currently taken. `_channels` sorts by **type id**, which is a property of the shape:
while there is one channel per type the order is a pure function of the set of types the graph
consumes, and no node id reaches it. It stops being a unique key in phase 3, which is where two
channels may share a type — and phase 3 already owns the determinism test that fails without it.

**2.4's `Why` is deferred to phase 4, and this one is a disagreement with §12.2 rather than a
postponement.** §12.2 wants the migration to record that it decided, so `upgrade` replays rather
than re-derives. That is exactly right for **scope**: a v5 file has none, taking the type's
default is a genuinely new decision, and a decision appearing in a pipeline nobody re-decided is
what replay exists to prevent. **A name is not that.** A v5 file has one channel per type, so
`annotation.gtf` → `gtf` restates what the file already said; recording a `DecisionRecord` for it
would put a decision nobody made into the artifact — §12.2's own failure mode from the other
side — and `mendel explain` would owe an answer for a question that was never open.

What the property actually needs is that the migration and a fresh derivation *cannot* disagree,
and `test_the_migration_names_channels_the_way_a_fresh_build_does` asserts it by comparing them
against **each other** rather than each against a literal. That test earned its shape
immediately: the migration was written with one `taken` counter shared between names and params —
the identical bug that had just been found and fixed in `_channels` — and gave `annotation.gtf`
the param `gtf_2` while a fresh build gave it `gtf`. A test comparing either one to a hardcoded
list would have been written against whichever was in front of the author.

**What is NOT done in this commit**, and why it cannot be yet:

- **`MD0228`** — an `entry_channel` with no `{param}`. The substitution reads a template *and*
  today's literal, because the engine has to understand templates before any registry can ship
  one. It tightens in the commit that bumps the submodule.
- **A test over every registry type that a substituted expression still parses** (`nextflow
  lint` on a generated stub). Nothing to substitute until 2.6 writes the templates.
- **2.5**, the API's `channels` and deleting `Sources.entryChannels()`.

### The two bugs the goldens caught, both by reading rather than regenerating

`params.star` became `params.star_2`, because names and params shared one uniqueness counter and
`genome.index.star`'s name took `star` before its own param could. They are different namespaces
— a Groovy variable against a `params.*` key — and only a cross-channel collision is one.

And `Channel.param` said `reads` for a channel whose expression demonstrably read `params.input`,
because the param was derived while the expression was still a literal. `_param_of` asks a
literal expression what it reads, so the field and the string beside it cannot disagree.

**Both were found by reading the golden diff**, which is now the third time in this repository
that has been what caught it rather than the suite. `nextflow.config` not moving at all is the
single most useful line in that diff: it is the whole command-line interface, unchanged.


### Phase 2.5 — the seam, and the one thing it moved that the plan did not predict

`BuiltPipeline.channels` carries **no `scope`**, because `Scope` does not exist until phase 4.
The plan's task line names it; the field arrives with the type it needs. Everything else is
there — name, param, type, states, and the ports each channel feeds.

**The number is the deliverable.** The spine's five unwired input ports collapse to three
channels, and `gtf` reports feeding all three of its consumers:

    gtf    params.gtf    annotation.gtf  feeds [star_genomegenerate.gtf, star_align.gtf,
                                                subread_featurecounts.annotation]
    reads  params.input  fastq.reads     feeds [trimgalore.reads]
    fasta  params.fasta  genome.fasta    feeds [star_genomegenerate.fasta]

That is the run sheet asking for three files where it asked for five, two of which went nowhere
— which is the thing that was visible on screen at the end of phase 1 and is now not.

**A label's key changed shape, and the plan did not see it coming.** `DraftLabel.key` was
`<node>.<port>` for both sides. An input socket is a *channel* now, and a channel may feed three
ports — so keying its label on a port would give one socket three competing labels and no rule
for which wins. An input's key is a `ChannelName`; an output's is still `<node>.<port>`, because
`Goal.want` is a list of type ids and gives an output no identity of its own. `SocketKey` admits
both without widening, since a bare `gtf` is one identifier segment.

The cost is written on the field rather than left to be discovered: a channel name is derived,
so adding a second `annotation.gtf` in phase 3 makes one of them `gtf_2` and a label keyed on the
old name detaches. That is smaller than what it replaced — three ports of one channel carrying
three different names on one box — and phase 3's `DraftChannel` is where a stable key belongs.

**Outputs are still derived in the browser**, and the asymmetry is deliberate rather than
half-finished: a channel is a named object because a laboratory *binds* one, and an output is
bound by nobody. When phase 4 gives outputs an identity, that side reads the server's answer too.


### Phase 2.6 — done, and the ordering it forced

Three commits across two repositories, and none of them leaves either repository red:

1. **Comeni-Labs #90** (merged, `532ce0b`) — phases 1–2.5 plus `REGISTRY_FORMAT = 2`. The bump
   lands *before* any registry declares `requires_format: 2`, because the registry's own CI pins
   an engine commit and would otherwise refuse its own layer with `MD0020`.
2. **comeni-registry #7** (merged, `5719fa3`) — the three type files, `requires_format: 2`, and
   `ENGINE_REF` → `532ce0b` in the same commit, because those two are one fact.
3. **This one** — the submodule bump and `MD0228`, which tightens the transitional substitution
   that read both a template and a literal.

**The `ENGINE_REF` mechanism is what made the ordering solvable at all**, and it was not in the
plan: `comeni-registry/.github/workflows/ci.yml` pins Mendel by commit SHA, so "which engine does
this layer need" is already a reviewable line in that repository rather than an implicit
dependency on whatever is released.

**Verified before pushing anything**: `mendel build` against the templated layer emits a
`main.nf` and a `nextflow.config` **byte-identical** to the ones built against the literal layer,
and `mendel lint`, `mendel conformance` and `comeni-vendor check` all pass. The registry's CI then
ran all five of its steps against the pinned engine and agreed.

### MD0228 was too broad on its first draft, and the fixtures caught it

It refused any `entry_channel` without `{param}` — including `Channel.empty()`, which hardcodes
nothing and therefore has nothing a pipeline could have been deprived of. Ten tests across four
files failed, every one of them a fixture using a param-free channel to exercise some *other*
diagnostic.

The spec's own words are *"a literal `params.gtf`"*, and the check now looks for a hardcoded name
rather than for a missing placeholder. **That is the second time in this plan that an over-reach
was caught by an existing test using the feature incidentally**, rather than by a test written to
police it.

### The plan's `nextflow lint` check became something cheaper, deliberately

§2.2 asks for *"a test over every type in the registry: substituting a known param yields Groovy
that still parses, via `nextflow lint` on a generated stub"*. `make check`'s lane installs neither
Nextflow nor Docker — `CLAUDE.md` names that trap explicitly, and a test shelling out to the
linter would be green on a developer machine and red in CI.

So the test substitutes into every declared template and asserts the result is balanced and has no
placeholder left, and the **real** linter covers the same expressions where it already runs: the
spine's emitted `main.nf`, through `make static` and the nightly stub gate.


### Phase 3 — carried out, with three deviations

**`GoalInput.scope` is not here.** The task line pairs it with `name`; `Scope` is phase 4's type
and arrives with it. Adding a field now would mean choosing a default for every existing goal
before the argument for what a scope *means* has been written, which is §12.2's mistake in
advance.

**The ordering key is `(depth, contract, port name)`, computed from the IR's own edges** rather
than taken from `dag_core.layout`. §11.2 asks for `(rank, order-within-rank, port index)` and
the reason it gives is what matters — *no node id anywhere* — which this satisfies. Taking it
from `dag-core` would mean a dependency from `mendel-resolver` onto a layout package for one
integer; `_depths` is six lines.

**One place still reads a node id, and it is written on the function.** Two *isomorphic*
consumers — two identical STAR nodes at one depth, both taking a GTF — tie on every shape fact,
and the tie breaks on the sorted port keys. Whichever way it falls the two graphs describe the
same computation, so the tie is arbitrary rather than wrong. That is a weaker claim than the rest
of the ordering makes and it is stated rather than buried.

### Two guards refused the first design, and both were right

`PipelineIR.channel_of` started as a `dict[SocketKey, ChannelName]`, and `tests/test_egress.py`
refused it in two voices: *`dict` is not a declared container* and *these fields are mappings; use
a list of declared records instead*. A mapping's keys are unvalidated by construction, which is
the hole the egress boundary spent three audits closing. `IRChannel` is the list of records, and
it reads better beside `DraftChannel` and `ChannelView` — the same fact at the other two layers.

Then `tests/test_pipeline_totality.py` refused it again for a different reason: a new field on a
replaced type needs a stated home in `Pipeline`. It is `RETYPED` rather than `NOT_CARRIED`,
because the name matches and the type does not — the IR records *which sockets share a channel*
and the artifact records *what the channel is*, with the grouping surviving by inversion in
`StepInput.channel`.

### What the split actually produces

    default:   gtf    params.gtf     annotation.gtf   feeds 3 ports
    split:     gtf    params.gtf     annotation.gtf
               gtf_2  params.gtf_2   annotation.gtf   ← the split port reads this one

`ch_gtf_2` is a real line in the emitted workflow and `params.gtf_2` a real hole in
`nextflow.config`, so a laboratory binds two annotations where it could bind one. That is ask (2)
end to end.

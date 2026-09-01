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

- [ ] **Before any registry ships a template**, the *current* release must refuse one. A new
      registry's `params.{param}` reaching an emitter that does no substitution would write
      `params.{param}` into Groovy.
- [ ] A **version floor on the layer**: `registry.yml` declares the minimum Mendel it needs, and
      an older Mendel says *this registry needs a newer Mendel* instead of emitting broken Nextflow.
- [ ] It is a small change and **it has to land first or it cannot land at all.**

### 2.2 The types

- [ ] `Channel` gains `name: ChannelName` and `param: NfIdentifier`.
- [ ] `StepInput.channel` becomes `ChannelName | None` — was `TypeId | None`. **This is the change
      that makes two same-type inputs addressable.**
- [ ] `entry_channel` becomes a one-placeholder template: `params.{param}`. **Not a template
      language** — one substitution, the same argument as Plan 1.15's `transform`. `{` is legal
      Groovy and appears throughout these expressions, so the placeholder is matched as the
      literal seven characters `{param}`.
- [ ] `MD0226` two channels sharing a name · `MD0227` a `StepInput.channel` naming no declared
      channel · `MD0228` an `entry_channel` with no `{param}`.
- [ ] A test over every type in the registry: substituting a known param yields Groovy that still
      parses, via `nextflow lint` on a generated stub.

### 2.3 Ordering is on SHAPE, never on identity — spec §11.2

- [ ] Channels are numbered by **`(rank, order-within-rank, port index)`** — `dag-core`'s own
      layout arithmetic, and **no node id anywhere**.
- [ ] **Why:** `useGraph.nextId` mints `star_align_1`, `star_align_2` … from the ids currently
      *taken*. Add two STAR nodes and delete the first and the survivor is `star_align_2`; draw one
      and it is `star_align_1`. Two structurally identical graphs, two different node ids — so any
      ordering keyed on them makes a person's `params.*` depend on the order they clicked.
- [ ] Derivation is over the **full type id** with a `_2`, `_3` suffix, not the last segment:
      `qc.report` and `multiqc.report` both end in `report`, and `_channel_name`'s docstring
      records that collision costing two ports the same channel silently.
- [ ] `MD0226` refuses a `Pipeline` whose channel names are not unique. **A derived value that can
      collide needs a check, not a convention.**

### 2.4 `SCHEMA_VERSION` 5 → 6, and the migration decides — spec §12.2

- [ ] The loader migrates: an old file names its channels by type, one channel per type, so
      `annotation.gtf` → `gtf`. In the loader beside the other version branches, **not a script
      somebody has to remember to run.**
- [ ] **The migration records that it decided.** A `Why` at a tier — *migrated from schema 5;
      name derived from the type, which is what this pipeline's behaviour already was.*
- [ ] **`upgrade` replays it rather than re-deriving it.** `mendel upgrade` re-resolves against the
      current registry and replays every recorded decision so only what you touched can move —
      issue #10 closed on that property. If the migration's names and a fresh derivation's names
      differ by one, every `params.*` in a laboratory's command line renames itself on an upgrade
      they asked for to pick up a registry fix.
- [ ] **The test, and it is the phase's real check:** migrate a v5 artifact, upgrade it, assert the
      emitted `.nf` is byte-identical to the v5 artifact's. Watched failing against a migration
      that assigns silently.

### 2.5 The API, which neither spec covered — spec §12.3

- [ ] `BuiltPipeline` gains `channels: list[ChannelView]` — name, type, scope, the ports it feeds.
- [ ] **`Sources.entryChannels()` is DELETED**, not left beside it. Two derivations of one fact is
      the defect this whole plan started from; keeping the old one "for now" is how it survives.
- [ ] The canvas draws a node per **channel** rather than per unwired port. This is also what makes
      phase 3's split/merge possible at all — you cannot split a thing recomputed from scratch on
      every render.
- [ ] **Why this is a task and not a footnote:** §0's finding was that the canvas derives its own
      answer and disagrees with the artifact. Part A fixes the registry and Part B fixes the
      resolver, and without this the canvas would disagree *again* — in a new way, because now
      there really are named channels for it to disagree with.

### 2.6 The registry side

- [ ] Three type files change — `fastq.reads`, `annotation.gtf`, `genome.fasta`. A
      `comeni-registry` PR plus a submodule bump, **registry PR first**.
- [ ] An **old registry read by a new resolver** — a literal `params.gtf`, no `{param}` — is a
      clean refusal, `MD0228`. Carrying on quietly would silently merge two inputs, which is the
      defect this plan exists to remove.

---

## Phase 3 — two channels of one type

*The first phase where a drawing can express something it could not before.*

- [ ] `goal_of` stops deduplicating. It currently writes
      `if all(i.type_id != alternative.type_id for i in have)` — that one line is the whole of it.
- [ ] `GoalInput` gains `name: ChannelName` and `scope: Scope`.
- [ ] `Goal.have` sorts by `(type_id, name)`. It sorts by `type_id` today because a `Goal` reaches
      `pipeline.yml` and byte-identical output is a hard requirement (invariant 10).
- [ ] **`DraftChannel` on the draft**: whether two GTF ports are one channel or two is a decision
      only a person can make. The **default is one channel per type**, which is today's behaviour
      and the right answer for the spine's shared reference annotation.
- [ ] The canvas's **split / merge** control — the operator's *"multiple of the same type"* — and
      merging two back is the same control in reverse.
- [ ] **Routing is unaffected, and that is checked rather than assumed** (§3.1): `producers_of`
      matches a requirement against `produces` by type and states; a channel is not a producer and
      never was, which `StepInput`'s `source`/`channel` split and `MD0215` already enforce.
- [ ] **The determinism test §3.2 owes**: build the same pipeline twice by different routes — add
      and delete nodes on one path — and diff the emitted `.nf`. Watched failing against an
      ordering keyed on node ids.

---

## Phase 4 — scope, and the two channel bugs it fixes

*The correctness phase. Both defects are live in what this repository emits today.*

### 4.1 The scope

- [ ] `Scope` with **exactly two members**, `RUN` and `SAMPLE`. **No `group` scope** — every case
      for one is expressible as a sample-scoped channel with a column that groups, and a scope for
      it would put a join strategy in the vocabulary where the pipeline cannot see it. If a real
      case appears, it arrives as a new member with a written argument, the way `Kind` gained
      exactly two in Plan 4 phase 4 and refused a third.
- [ ] A type declares its **default** scope; a channel may **override** it.
- [ ] The override carries a `Why`, exits at a tier and appears in `pipeline.yml`. Choosing
      per-sample annotations over a shared one is a judgement about an experiment, and the
      product's claim is that no such judgement is silent.

### 4.2 The live bug — spec §10.1

- [ ] **`tests/golden/spine/main.nf` builds `ch_genome_index_star` and `ch_annotation_gtf` with
      `Channel.fromPath` — queue channels of one item.** `STAR_ALIGN` consumes three queue
      channels, and a Nextflow process runs as many times as the **shortest**. With twenty-four
      samples it runs **once** and twenty-three are silently dropped. There is no `.collect()`,
      `.first()` or `Channel.value` anywhere in `emit.py`.
- [ ] Nobody noticed because the stub profile globs **one** sample pair, so N = 1 and the shortest
      channel is every channel. Green gate, correct counts matrix, wrong pipeline for real data.
- [ ] **A `RUN`-scoped channel emits as a VALUE channel** — `.first()` for a single file,
      `.collect()` for a set — so it can be consumed any number of times. `SAMPLE`-scoped stays a
      queue.
- [ ] **The check is a stub run with two sample pairs asserting the process ran twice**, watched
      failing against today's emitter. **Not** a determinism test over the spine: that passes
      either way on a one-sample fixture, which is the guard-that-proves-nothing shape this
      repository has already paid for twice.
- [ ] The stub-data fixture gains a second sample pair.

### 4.3 Fan-in — spec §10.2

- [ ] `InputPort.cardinality` exists, defaults to `"1"`, and has exactly one reader —
      `validate.py`, refusing more than one *wire*. It says nothing about how many **items** a port
      consumes and **nothing reaches the emitter**.
- [ ] `cardinality: "*"` emits `.collect()`: one invocation over the whole channel.
- [ ] MULTIQC's contract consumes `qc.report` from every sample. Today it would emit
      `MULTIQC(ch_qc_report)` — **one invocation per sample, producing N reports where the point of
      the tool is to produce one.** It is not in the spine, so nothing is broken right now; the
      contract is in the registry and would be wrong the moment it routed.
- [ ] Same phase as 4.2 because it is the same arithmetic: *make this port a value channel*.

### 4.4 The spine changes, and that is expected

- [ ] The emitted `.nf` is **not** byte-identical to phase 3's — a reference becomes a value
      channel. Golden files move. The invariant that must hold is *same goal in → byte-identical
      out*, not *the same bytes as last week*.

---

## Phase 5 — the samplesheet

*The only phase that changes what a laboratory types on the command line.*

### 5.1 The emission — spec §2.2

- [ ] **One** sample-scoped channel emits what it emits now: `fromFilePairs`, one queue channel, no
      samplesheet. **This must not regress** — `tests/test_counts.py` is the only check exercising
      the v1 criterion and it runs this shape.
- [ ] **Two or more** emit a samplesheet: `params.input` is a CSV whose columns are the
      sample-scoped channels, each channel a projection of it, joined at the process by `meta.id`.
- [ ] Column names come from **channel names**, which are derived from types. Rows are the
      laboratory's and Mendel never sees them.

### 5.2 `input_form`, and why it is an enum — spec §11.1 and §12.1

- [ ] `Pipeline.input_form: InputForm` — `SAMPLESHEET | DIRECT`. **A closed enum, not prose.**
- [ ] §2.2 originally asked the artifact to say which form it wants *"in words, next to the
      param"*. `Pipeline` is door 4's payload, so **words next to a param is a fifteenth free-text
      field**, in a spec whose §5 claims it adds none. The two sentences contradicted each other.
- [ ] The **words** a reader needs — *"a samplesheet with columns sample, fastq_1, fastq_2, gtf"* —
      are **generated** from `input_form` plus the channel names. Nobody authors a string, nothing
      new crosses a door, and the artifact still reads as prose because `mendel emit` writes the
      comment.
- [ ] **The general rule this nearly broke, worth carrying beyond this plan:** when a fact is a
      closed choice, put the choice in the artifact and generate the sentence. A field that exists
      so a file can explain itself is how a boundary widens one entry at a time.
- [ ] `MD0229`: a samplesheet form with fewer than two sample-scoped channels, or a non-samplesheet
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

- [ ] Two sample-scoped channels join on `meta.id`. A sample split across lanes or flowcells is
      several rows with one id, and nf-core's answer is `cat_fastq` — a grouping step before
      anything else.
- [ ] **A duplicate sample id is a refusal**, with a message naming the rows. Refusing is honest
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
| 1 | Yes, with two corrections | **The guard moved out of `test_drafts.py`**, whose tests need Postgres and skip in CI — a guard that does not run is not a guard. It lives in `tests/test_draft_labels.py` and asserts against `materialise` directly, which is where the claim *nothing in `materialise` reads it* actually lives. **`Sources.test.tsx`'s "renders nothing at all" broke and was right to**: its fixture was a step with one output port and no inputs, which is now a step with a *terminal output* — exactly what the OUTPUT socket exists to mark. Split into three: no input socket, nothing at all for a graph with no steps, and a note that **a pipeline closed at both ends does not exist**. `make client` was needed — `DraftGraph` gained a field, and the generated client is never hand-edited |
| 2 | | |
| 3 | | |
| 4 | | |
| 5 | | |

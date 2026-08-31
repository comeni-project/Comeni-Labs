# A channel gets a name — Plan 5B, phases 1 to 3

*2026-09-01. Four pull requests across two repositories; forty of the plan's seventy boxes.*

**Read [`../plans/2026-08-31-plan-5b-what-a-pipeline-takes.md`](../plans/2026-08-31-plan-5b-what-a-pipeline-takes.md)
for the checklist and its execution record, and
[`../specs/2026-08-31-what-a-pipeline-takes.md`](../specs/2026-08-31-what-a-pipeline-takes.md)
for the argument.** This entry is what happened, what a fresh reader will get wrong, and what is
next.

---

## What is true now

**A channel is a thing the pipeline has, with a name and a param.** It was a property of the
*type*: `entry_channel: "…params.gtf…"` in `registry/types/annotation.gtf.yml` fused three
decisions that belong to a pipeline — the param name, the cardinality, the fan-out — into one
string. The first is the one that cost something. The RNA-seq spine's three `annotation.gtf`
consumers were **one hole nobody could address**, and the canvas drew five sockets above it.

Today the spine reports three channels for five unwired ports, and a person can split one:

    gtf    params.gtf     annotation.gtf   feeds star_genomegenerate.gtf, star_align.gtf,
                                                 subread_featurecounts.annotation
    reads  params.input   fastq.reads      feeds trimgalore.reads
    fasta  params.fasta   genome.fasta     feeds star_genomegenerate.fasta

Split `subread_featurecounts.annotation` off and it gets `gtf_2`, `params.gtf_2`, its own
`ch_gtf_2` line in the workflow and its own null in `nextflow.config`. That is the operator's
ask (2) — *"a pipeline needs to have two same type inputs"* — end to end.

**The canvas draws what a pipeline is for.** `goal_of` has computed `want` since Plan 3E and
nothing drew it: a terminal `counts.matrix` was an unwired port with nothing marking it as the
point. There is an OUTPUT socket per terminal port now, in the right-hand gutter the last rank
has by construction, and INPUT and OUTPUT are **one component** — the plan said the gutter
arithmetic "applies in reverse", and writing it twice is how two gutters come to disagree.

**A label names nothing.** `DraftLabel` carries what a person calls a socket; the channel name,
the param, the samplesheet column and the Nextflow variable are all derived and it reaches none
of them. `tests/test_draft_labels.py` holds that in six tests, and `tests/test_egress.py` is
untouched — a `DraftGraph` is not a door payload, fourteen free-text fields are still fourteen.

**`SCHEMA_VERSION` is 6**, with a loader migration, and **`REGISTRY_FORMAT` is 2**: a layer says
which engine it needs (`MD0020`) and an engine refuses a layer that names its own param
(`MD0228`). Those two directions are deliberately not symmetric — §1.3 — and the asymmetry is
the useful part: the floor protects old *engines* from new *layers*, and `MD0228` protects new
engines from old layers.

---

## The four things this did not predict

### 1. `fastq.reads` reads `params.input`, and nothing in the plan said what a param is

Neither spec nor plan says where a channel's `param` comes from. The obvious reading — derive it
from the channel name — renames `params.input` to `params.reads`, because `fastq.reads` is the
one shipped type that does not read its own last segment.

That is a change to **what a laboratory types**, arriving inside a phase the plan calls *"the
rename, with no behaviour change"*. It would also have dissolved the exact ambiguity §12.1 says
phase 5 has to solve — *`params.input` is one null whether it is a fastq glob or a CSV path* — and
a spec that reasons about a live problem is one whose author expects it to still be there.

So a type declares its param and `name` and `param` are separate fields: `reads` and `input`.
**`nextflow.config` came out byte-identical across the whole of phase 2**, which is the entire
command-line interface, unmoved. That is the check that the choice was right.

### 2. The registry's CI pins Mendel by commit SHA, and that is what made the ordering solvable

`comeni-registry/.github/workflows/ci.yml` carries `ENGINE_REF`, a Comeni-Labs commit. Nobody
wrote that down as part of this plan and it is the mechanism the whole cross-repo change turns on:
the layer could not declare `requires_format: 2` until its pinned engine understood 2, and that
engine could not bump the submodule until the layer existed.

Three commits, in this order, none leaving either repository red:

1. **Comeni-Labs #90** — phases 1–2.5 plus `REGISTRY_FORMAT = 2`, so the engine understands the
   format *before* any layer claims it.
2. **comeni-registry #7** — the three type files, `requires_format: 2`, and `ENGINE_REF` bumped
   to #90's merge commit **in the same diff**, because those two are one fact.
3. **Comeni-Labs #91** — the submodule bump and `MD0228`.

**Verified before anything was pushed**: `mendel build` against the templated layer emitted a
`main.nf` and a `nextflow.config` byte-identical to the ones built against the literal layer.

**The floor cannot give a good message for its own first use**, and that is inherent rather than a
defect: a Mendel predating `requires_format` has no such field, so `extra="forbid"` refuses the
file with a Pydantic error instead of `MD0020`'s sentence. There is exactly one such step and it
has been taken.

### 3. A label's key changed shape, one phase after it was designed

`DraftLabel.key` was `<node>.<port>` for both sides. Phase 2.5 made an input socket a **channel**,
and a channel may feed three ports — so keying its label on a port gives one socket three
competing labels and no rule for which wins.

An input's key is a `ChannelName` now; an output's is still `<node>.<port>`, because `Goal.want`
is a list of type ids and gives an output no identity of its own. The cost is on the field rather
than left to be found: a channel name is derived, so splitting one makes it `gtf_2` and a label
keyed on the old name detaches.

### 4. `make dev` could not start, and the message that stopped it advertised a fix that did not work

`names-free` refused because the sibling worktree owned the container names — correctly — and
said to set `*_CONTAINER_NAME` in `.env`. Doing that changed nothing: the check read the **shell**,
which `make` never loads `.env` into, and **five of the nine names were hardcoded** even though
compose makes every one overridable. It reads `docker compose config` now.

Same shape as `geometry.ts` claiming a test that did not exist: a sentence asserting a mechanism
nobody had run.

---

## What a fresh reader will get wrong

**"`sorted(type_id)` was a weaker version of the ordering rule."** It was not. §11.2's defect is an
order keyed on *node ids*, which are minted from what is currently taken; sorting by type id is a
pure function of the set of types consumed and no node id reaches it. It stopped being a *total*
order in phase 3, when two channels could share a type — which is why phase 3 owns the key, and
why the plan's own §2.3 boxes were deferred with an argument rather than skipped.

**"The channel ordering has no node id in it."** It has one, in the last tie-break, for two
*isomorphic* consumers — two identical STAR nodes at one depth, both taking a GTF. Either way the
graphs describe the same computation, so the tie is arbitrary rather than wrong. It is written on
`channels_of` and in the guard ledger, because a claim of purity with an unstated exception is
worse than the exception.

**"The migration records a `Why`, as §12.2 asks."** It does not, and that is a disagreement rather
than an omission. §12.2 is right about **scope**: a v5 file has none, taking the type's default is
a genuinely new decision, and a decision appearing in a pipeline nobody re-decided is what replay
exists to prevent. **A name is not that** — `annotation.gtf` → `gtf` restates what the file already
said, and recording a `DecisionRecord` for it would put a decision nobody made into the artifact,
which is §12.2's own failure mode from the other side. Phase 4's scope genuinely owes one.

**"Outputs read the server's answer like inputs do."** They do not. A channel is a named object
because a laboratory *binds* one; an output is bound by nobody. When phase 4 gives outputs an
identity, that side stops deriving too.

---

## What the tests taught, which is the part worth carrying

**Reading a golden diff caught two bugs that regenerating it would have blessed.** `params.star`
became `params.star_2`, because names and params shared one uniqueness counter and
`genome.index.star`'s name took `star` before its own param could — two different namespaces, and
only a cross-channel collision is one. And `Channel.param` claimed `reads` for a channel whose
expression demonstrably read `params.input`.

That is now the third time in this repository that reading the diff, rather than the suite, is
what caught it. **`nextflow.config` not moving at all was the single most useful line in it.**

**Then the migration was written with the same shared-counter bug, minutes after it was fixed in
the builder.** `test_the_migration_names_channels_the_way_a_fresh_build_does` caught it — because
it compares the two against **each other** rather than each against a literal. A test written
against a hardcoded list would have been written against whichever of the two the author was
looking at.

**Twice, an over-reach was caught by an existing test using the feature incidentally**, not by a
test written to police it. `MD0228` first refused any `entry_channel` without `{param}`, including
`Channel.empty()` — which hardcodes nothing. Ten tests across four files failed, every one a
fixture using a param-free channel to exercise some *other* diagnostic.

**Two guards refused a design and both were right.** `PipelineIR.channel_of` started as a
`dict[SocketKey, ChannelName]`; `tests/test_egress.py` refused it in two voices, because a
mapping's keys are unvalidated by construction — the hole the egress boundary spent three audits
closing. `tests/test_pipeline_totality.py` then refused the replacement until it had a stated
home. `IRChannel` is better than what it replaced and neither guard was arguing about style.

**Guard reverts are in [`../audits/guard-ledger.md`](../audits/guard-ledger.md)**, including one
that records what could *not* be watched: phase 1's `.nf` comparison had no constructible defect
until `Channel.name` existed, and a probe showing an assertion is *capable* of failing is not the
same as watching it fail.

---

## What is next

**Phases 4 and 5, and phase 4 carries a live defect.**

> **§10.1 is real and it is in what this repository emits today.**
> `tests/golden/spine/main.nf` builds its reference channels with `Channel.fromPath` — queue
> channels of one item. A Nextflow process runs as many times as its **shortest** input channel,
> so with twenty-four samples `STAR_ALIGN` runs **once** and twenty-three are silently dropped.
> Nobody noticed because the stub profile globs one sample pair, so N = 1 and the shortest channel
> is every channel. Green gate, correct counts matrix, wrong pipeline for real data.

**Do not point the spine at more than one sample until phase 4 lands.** The operator declined an
out-of-order fix on 2026-08-31 — *"no that's fine, no one is using this, keep it organized and
efficient"* — and that is the right call while nothing is in production, but it is a note for
whoever first tries real data.

Phase 4 is `Scope` with exactly two members, a `RUN`-scoped channel emitting as a **value**
channel, and `cardinality: "*"` reaching the emitter as `.collect()` so MULTIQC produces one
report rather than N. **Its check must be a stub run with two sample pairs asserting the process
ran twice**, watched failing against today's emitter — *not* a determinism test over the spine,
which passes either way on a one-sample fixture. That is the guard-that-proves-nothing shape this
repository has already paid for twice.

Phase 5 is the samplesheet, and §9 names it as the one to watch for the estimate.

**Nobody has looked at the screen since phase 1.** The builder was driven in a browser at the end
of phase 1 — five INPUT sockets, one OUTPUT, renaming in place, the draft saved — and the run
sheet then showed §0's defect live, three rows to bind for one `params.gtf`. Phases 2.5 and 3
changed that screen substantially and **the split/merge control has never been clicked by a
person**. That is the gap Plan 4 phase 6 exists because of.

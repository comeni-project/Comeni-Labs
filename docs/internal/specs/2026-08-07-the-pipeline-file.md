# The pipeline file — one artifact, every setting, every provenance

**Spec, 2026-08-07.** Closes [#10](https://github.com/comeni-project/Comeni-Labs/issues/10).
Supersedes the four-route settings surface described in `ARCHITECTURE.md`.

Verified against the code at `e9cab07`.

**This is a design spec, not an audit root.** The nine root specs
(`2026-08-07-root-*.md`) close findings in code that exists. This one changes what the code
should be.

---

## Precedence, because the ground is moving

The nine root specs are being implemented concurrently, in a separate worktree. The code this
spec cites **will have moved** by the time it runs. Two rules resolve that:

1. **Where this spec and the codebase disagree, this spec wins.** Design choices settled here
   overwrite whatever shape the code has arrived at. Every code citation below names a *symbol
   and a behaviour*, never a line number, so a citation that no longer matches is a citation to
   re-read rather than a spec to re-litigate.
2. **Where this spec and a root spec disagree, the root's guarantee survives and its location
   moves.** The roots close critical findings; this spec relocates surfaces. A guard may be
   moved by this work. It may never be weakened, deleted, or left watching a surface that no
   longer exists — that last one is A14's failure mode, and consolidating four artifacts into
   one is exactly the change that could produce it silently.

Concretely: root C says every string the emitter writes has a declared kind. This spec changes
*which* strings the emitter writes and adds one kind. Root C's rule holds; its table gains a
row. That is the pattern for every interaction below.

---

## The problem

A researcher asking "what settings does this pipeline use, and why" must read four files and
know which of four mechanisms carries each value.

| route | declared in | reaches the tool via | visible in the artifact? |
|---|---|---|---|
| `ext_args` | `ModuleContract.ext_args` | `process { withName: X { ext.args } }` | no — lives in the registry |
| `meta` map | `Measurement.meta_key` + `meta_values` | channel `.map { meta + [...] }` | as a Groovy expression in `main.nf` |
| `params.<x>` | `Vocabulary.entry_channels` | `params.input`, `params.gtf` | as `= null` in `nextflow.config` |
| `nf_inputs` literal | `ModuleContract.nf_inputs` | a positional argument | **nowhere** |

The fourth row is the sharp one. `STAR_ALIGN(reads, index, gtf, false)` — that `false` is a
tier-1 decision that appears in no artifact at all. `pipeline.ir.json` does not contain it.
Neither does the lockfile.

**And a fifth route does not work.** `ModuleContract.params` resolves to a
`params.<node>_<name>` line in `main.nf` that nothing reads:

```groovy
// tier 2 (none): contract default
params.star_align_seq_platform = 'illumina'
```

`vendor/modules/nf-core/star/align/main.nf` has no `seq_platform` — nor does
`hisat2/align/main.nf`, so both declared params are dead and not merely one. The route it *should*
take is `ext.args`, as an `--outSAMattrRGline` fragment; the exact spelling used upstream by
nf-core/rnaseq is **not verified here** and must be read out of that repository rather than out of
this spec, per the standing rule about reading process names and containers from module source and
never from a plan. So the resolver runs, emits
a tier-4 flag, records a `DecisionRecord`, prints `REVIEW star_align.seq_platform`, and the
pipeline behaves identically whatever the answer is. That is issue #10, and it is the CLAUDE.md
*deadness* gotcha with a name.

**The whole declared-param surface is two entries and all of it is dead.** Across ten shipped
contracts: `star/align` and `hisat2/align`, both `seq_platform`, both `tier_hint: 4`, both
reaching nothing. Fixing this costs nearly nothing today and gets expensive once the forge emits
params at volume.

### Three artifacts describe one pipeline

| artifact | holds | overlap |
|---|---|---|
| `pipeline.ir.json` | nodes, edges, selections, decisions, profile, layers | near-total |
| `PublishBundle` | goal + that IR + decisions + lockfile + gate | near-total, plus `goal` and `gate` |
| `mendel.lock.yml` | contract digests, layer digests | becomes per-step `digest:` |

None is human-facing. The IR for the five-module spine is ~200 lines of JSON. A build directory
contains no readable account of what was decided — the tiers and reasons survive as comments
scattered through `main.nf` and as records inside the JSON, and `needs_review()` reaches the user
as one line on stderr.

### And emission reads four inputs

`emit(ir, registry, vocab, measurements)`. A published pipeline therefore reproduces only against
the registry it was built with, at that version. Hand someone a bundle and they may get different
Nextflow. For a lab archiving a validated pipeline, "archive the registry too, and hope it still
loads" is not an answer.

---

## The design

### 1. One artifact: `pipeline.yml`

It replaces `pipeline.ir.json`, `mendel.lock.yml`, and `PublishBundle`'s on-disk form. A build
directory becomes:

```
build/
  pipeline.yml       the pipeline — read this
  main.nf            generated
  nextflow.config    generated
  modules/           vendored module source, as today
```

```yaml
# pipeline.yml — the pipeline. Edit it; `mendel emit` rebuilds the Nextflow.
version: 1

goal:                          # what was asked for. EDITING THIS TAKES EFFECT ON
                               # `mendel upgrade`, NOT on `mendel emit`.
  have: [{type_id: fastq.reads}, {type_id: annotation.gtf}, {type_id: genome.fasta}]
  want: [counts.matrix]
  constraints: {required_states: {counts.matrix: [gene_level]}}
  profile: {read_length: 150, strandedness: reverse, paired: true, n_samples: 12}

registry:                      # provenance. NOT a dependency of `emit`.
  layers: [{name: comeni-registry-examples, digest: sha256:1a4f…}]
  shadowed: []
  unverified: []

steps:
  - id: star_align
    module:  {id: nf-core/star/align@1.11.0, digest: sha256:9f2c…,
              container: "community.wave.seqera.io/library/…:ae438e9a604351a4"}
    why:     {tier: 3, source: resolver, from_layer: comeni-registry-examples,
              displaced_layer: null,
              reason: "rule producer_of:alignment.bam matched read_length >= 70:
                       doi:10.1093/bioinformatics/bts635"}
    process: STAR_ALIGN
    include: modules/nf-core/star/align/main
    inputs:
      reads: {from: trimgalore.reads, states: [trimmed]}
      index: {from: star_genomegenerate.index}
      gtf:   {from: "channel:annotation.gtf"}
    call:
      - {ports: [reads]}
      - {ports: [index]}
      - {ports: [gtf]}
      - literal: false
        why: {tier: 1, source: contract,
              reason: "no GTF-free splice-junction path in this spine"}
    settings:
      readFilesCommand:
        value: zcat
        via: ext
        key: args
        template: "--readFilesCommand {value}"
        why: {tier: 1, source: contract, reason: "TrimGalore emits .fq.gz"}
      seq_platform:
        value: illumina
        via: ext
        key: args
        template: "--outSAMattrRGline ID:${meta.id} 'PL:{value}'"
        why: {tier: 4, source: human, reason: "our sequencer"}

channels:                      # what the lab supplies, and the measured facts
  fastq.reads:
    params: [input]            # plural: one expression may reference several
    expression: "Channel.fromFilePairs(params.input, checkIfExists: true)…"
    meta: {single_end: false, strandedness: reverse}

decisions:                     # the review queue: tier 4, ties, overrides
  - key: star_align.seq_platform
    subject: seq_platform
    tier: 4
    candidates: [null]         # what was on the table
    chosen: null               # what the resolver took
    confidence: 0.0
    resolved_by: flag-only
    reason: "no rule covered 'seq_platform'"
    human_override: illumina   # replayed by `upgrade`

gate: test                     # the strongest gate this pipeline actually passed
```

Four properties are load-bearing:

**`why:` on every step and every setting.** Tier, who settled it, which layer, and the citation,
in one place. This is the legibility the four-file split cannot provide.

**`goal:` is inert to `emit`, and the file says so in a comment.** It is input to *resolution*, and
`emit` reads none of it — the facts emission needs are already materialised into `channels[].meta`.
So editing `profile:` or `want:` changes nothing until `mendel upgrade`. Two reasons to state it
rather than leave it implicit. A reader who finds `profile: {strandedness: reverse}` in a file they
were told to edit will reasonably expect changing it to matter. And `emit` *cannot* honour it even in
principle: validating a profile requires the measurement registry —
`test_a2_upgrade_refuses_a_bundle_carrying_an_undeclared_measurement` is that guard on the upgrade
path — and `emit` has no registry by design. Better an inert section with a comment explaining it
than a section that silently means something on Tuesdays.

**`call:` materialises `nf_inputs`**, including the tier-1 literal that appears in no artifact
today. It carries a full `why:` rather than `NfInput`'s bare `because:` — a positional literal is
as much a decision as a flag is, and "every choice carries its provenance" cannot have an
exception for the one route with no artifact at all. The hollow-input lesson (`NfInput.empty`
requiring a reason, because `-stub-run` cannot see a hollow input) survives into the readable
artifact instead of living only in the registry.

**`inputs:` replaces the flat edge list**, keyed under the consuming step. Lossless — an
`IREdge` has exactly one consuming port — and it makes "where does this step's GTF come from"
answerable without scanning a separate list. Root D's finding that `diff_ir` ignored `ir.edges`
is the reason edges must be prominent rather than tucked away.

**`gate:` lives inside the file.** Root D's title is *the verdict comes from the artifact*; this
is that, structurally. The evidence and the pipeline are one document, so a bundle whose gate
claim was edited away is a bundle whose digest moved.

### 2. `emit` reads one file

```python
# comeni-core — pure; the interface Wiener consumes
class Pipeline(BaseModel):
    """Everything `emit` reads. The on-disk form is pipeline.yml."""
    model_config = ConfigDict(extra="forbid")

    version: int
    goal: Goal
    registry: RegistryProvenance
    steps: list[Step]
    channels: list[Channel]
    decisions: list[DecisionRecord]
    gate: Gate | None = None

    @classmethod
    def of(cls, ir: PipelineIR, registry: Registry,
           vocab: Vocabulary, measurements: MeasurementRegistry) -> "Pipeline": ...

# mendel-compiler — was emit(ir, registry, vocab, measurements)
def emit(pipeline: Pipeline) -> str: ...
def emit_config(pipeline: Pipeline) -> str: ...
```

**The mapping must be total, and a test must say so.** The YAML above is illustrative, and the
first three drafts of it silently dropped five fields that exist today:

| dropped | why it mattered |
|---|---|
| `LockedContract.container` | its own docstring says *"the `sealed` profile's digests-required rule depends on it"* |
| `ResolvedValue.displaced_layer` | A5 and A15 — what a lower layer offered and this one beat |
| `DecisionRecord.candidates` | what was on the table, which is what a tier-4 reviewer needs first |
| `DecisionRecord.chosen` | what the resolver actually took, as distinct from the override |
| `DecisionRecord.confidence` | the model's own number, once Plan 2 supplies one |

Losing `container` is the serious one: a consolidation meant to *strengthen* reproducibility would
have quietly dropped the field the clinical protection profile depends on.

So the requirement is not a longer example. **A test asserts that every field of `PipelineIR`,
`IRNode`, `ResolvedValue`, `DecisionRecord`, `Lockfile`, `LockedContract`, `LockedLayer`, `Goal` and
`DataProfile` has a declared home in `Pipeline`** — mechanically, over `model_fields`, with an
explicit allowlist for anything deliberately not carried. This is root D's finding applied to
consolidation rather than to diffing: `diff_ir` enumerated the fields it knew about, so every field
added to the IR became a silent blind spot, and Plan 1.8 added four. A hand-written mapping between
three types and one has exactly that shape, and reviewing it by eye already failed five times.

`Pipeline.of()` is **the only validating constructor**, enforced the way
`MeasurementRegistry.profile()` already is — by `tests/test_construction.py`, which exists
because deleting one call let `profile: {sample_name: ...}` build cleanly. Same reasoning:
materialisation must not be bypassable by a caller assembling a `Pipeline` by hand with the
contract-derived fields empty.

`PipelineIR` and `Lockfile` survive as internal types. `resolve()` still returns an IR;
`Lockfile.of()` still computes digests, which land as `steps[].module.digest` and
`registry.layers[].digest`. They stop being **artifacts**. Neither `pipeline.ir.json` nor
`mendel.lock.yml` is written.

### 3. Four verbs

```bash
mendel build --goal g.yml --registry registry/ --out build/   # resolve, then emit
mendel emit  build/pipeline.yml --out build/                  # no registry, no network
mendel verify build/pipeline.yml --registry registry/         # frozen values vs. digests
mendel upgrade build/pipeline.yml --registry registry/ --out next/   # never in place
mendel publish build/pipeline.yml
```

**`build` emits from the round-tripped file, not the in-memory object.** Write `pipeline.yml`,
parse it back, emit from the parsed result. One extra parse; in exchange, what you built and what
anyone else re-emits are the same bytes *by construction*. This is earned, not speculative:
`ResolvedValue._drop_computed` exists because `PipelineIR.model_validate_json(ir.model_dump_json())`
raised, and — in that field's own words — *"nothing noticed, because nothing read an IR back
until now."* Making the round trip load-bearing on every build retires that whole bug class.

**A `pipeline.yml` is generated, never hand-authored from nothing.** Resolution needs a registry
and always will. The file is the output of resolution that you may then edit; it is not an
alternative front door. `mendel build --goal` (and, from Plan 2, the prompt door) remains the
only way to make one.

**`upgrade` must never write over the file it read.** `tests/test_upgrade.py` already asserts this
of a bundle — `test_upgrade_never_writes_over_the_bundle_it_read` — and consolidation makes the rule
*more* important while making it easier to break. Today the input is a bundle and the output is a
report, so there is nothing to collide. With one artifact, the natural implementation updates
`pipeline.yml` in place, and that destroys the only record of what you had: the replayed overrides,
the previous digests, the gate evidence. `mendel upgrade` therefore requires `--out` and refuses to
resolve it to the input's directory. The existing test keeps its meaning and gains a second subject.

**The archive unit is the directory, not the file** — say it precisely, because the loose version of
this claim is wrong. `pipeline.yml` is sufficient to regenerate `main.nf` and `nextflow.config`
byte-for-byte with no registry and no network. It is *not* sufficient to produce a runnable
pipeline: `cli.py` copies module source from `<root>/vendor/modules` at **build** time, and `emit`
has no source to copy from. So a `pipeline.yml` alone regenerates text whose `include` statements
point at files that may not be there.

`pipeline.yml` + `modules/` is the archive, and both are already written side by side into `--out`.
The right claim is that **emission no longer depends on the registry** — which is the one that
matters for reproducing a decision, since `modules/` is inert vendored source while the registry is
the thing that resolves differently as it changes. `mendel emit` refuses when `modules/` is absent
rather than writing a `main.nf` that cannot run.

### 4. Settings: `via:` is mandatory and closed

An earlier draft of this spec claimed three `via:` values were **exhaustive over Nextflow's
destinations**. That was checked against the vendored modules and is false. `task.ext.prefix`
appears in 8 of the 10 shipped modules and `task.ext.when` in all 10, and neither is `ext.args`:

```groovy
// vendor/modules/nf-core/samtools/sort/main.nf
when:
    task.ext.when == null || task.ext.when
script:
    prefix = task.ext.prefix ?: "${meta.id}"
```

So the `ext` scope is not one destination but a **keyspace**, and the correct claim is about
*emission sites*, of which there are three:

```python
class Via(StrEnum):
    EXT       = "ext"        # → process { withName: X { ext.<key> = … } }
    META      = "meta"       # → channel .map { meta + [k: v], files }
    DIRECTIVE = "directive"  # → process { withName: X { cpus = 12 } }

class ExtKey(StrEnum):
    ARGS   = "args"          # and args2, args3 — multi-tool modules
    ARGS2  = "args2"
    ARGS3  = "args3"
    PREFIX = "prefix"        # names outputs; NOT appended to args
```

Three emission sites, because those are the three places the compiler writes into — the `ext`
scope, the channel's meta map, and the directive scope. That is verifiable against the emitter
rather than being a prediction about Nextflow, which is why it is the claim worth making.

`via: ext` requires `key:`. A `directive` requires a name from the compiler's directive list, which
is code rather than registry data for reasons §9 sets out under `M0119`.

**A setting without `via:` fails to load.** That makes a dead setting structurally impossible
rather than merely detectable, and it closes #10 by removing the possibility rather than by
adding a warning.

Composition is deterministic per key: for `ext.args`, the contract's static `ext_args` first, then
each `via: ext` / `key: args` setting in **name-sorted** order. `prefix`, `meta` and `directive`
take a single value and refuse a second writer (`M0118`).

**`ext.when` is deliberately absent, and refused.** It is a boolean that skips a process
entirely, so a setting could switch off a step while `steps:` and `inputs:` still describe it
running. That is a second routing mechanism competing with resolution, and it would make the
file's DAG a claim rather than a description. Whether a step exists is decided by resolving the
goal. A `pipeline.yml` naming `key: when` is refused by `M0115`.

### 5. `{value}` is validated, not escaped

```yaml
template: "--outSAMattrRGline ID:${meta.id} 'PL:{value}'"
```

Two interpolation systems meet in that line, and conflating them is how this goes wrong:

- **`{value}` is Mendel's**, substituted at emit time. The only one.
- **`${meta.id}` is Groovy's**, evaluated by Nextflow at run time. Passed through verbatim. A
  literal dollar is written `\$`.

`{value}` must not go through `_render_literal`, which returns a *quoted* Groovy literal and
would turn `'PL:{value}'` into `'PL:'illumina''`. Escaping-for-context is precisely the trap root
C exists to close. So instead: **`{value}` accepts a closed character class** —
`[A-Za-z0-9_.:+-]*`, `int`, `float`, `bool` — and anything else fails to load. No escaping, no
injection surface, and it takes root C's own stance on identifiers: validated, or it is not one.
Every real case fits (`illumina`, `10`, `true`), and it composes with the declared-legal-values
work `marks.py` already anticipates for Plan 2 Task 11.

**`template:` is legal only where the destination is an argument string** — `key: args`, `args2`,
`args3`. `prefix`, `meta` and `directive` each take one typed value and emit it directly; a
template there has nothing to compose into, and `cpus = "--cpus 12"` is not a thing. `M0114`
therefore covers both halves of the same mistake: a template that never mentions `{value}`, and a
template on a route that takes none.

One consequence: `ext.args` must be emitted as a **double-quoted** Groovy string so `${meta.id}`
interpolates, where `_render_literal` single-quotes it today.

An earlier draft said *"every golden file moves, as a reviewable diff."* **There is one golden
file — `tests/golden/spine/main.nf` — and it is not the one this change writes into.** `grep -rn
"nextflow.config" tests/` returns nothing: no golden, no assertion, no coverage of any kind. The
`ext.args` block is where this entire mechanism lands, and it is emitted into an ungoverned file.

**A golden `nextflow.config` is therefore a prerequisite of this work, not a step within it** —
first commit, before any behaviour changes, so the quoting change and the composition change arrive
as diffs against something. Root C found this same file *"also injectable"*, as the second surface
nobody was guarding; it is the second surface nobody is testing either, and for the same reason —
`main.nf` goes through Jinja and looks like output, while `nextflow.config` is assembled by
f-strings and looks like plumbing.

### 6. A goal pin and a file edit are different acts

`resolve.py` returns a goal-pinned param as `tier=Tier.STRUCTURAL` with
`source=ValueSource.GOAL`, and `review_level` is *derived* from tier — so it carries review
`none`. **That is deliberate and must not be changed.** `ValueSource`'s own docstring makes the
argument: *"A user who pins a parameter has legitimately removed the ambiguity, so the tier is
still structural — but a reviewer needs to see that Mendel did not derive it."* Resolution never
faced an ambiguity, so tier 1 is honest, and `source` is the axis that records who.

Editing `pipeline.yml` is a **different act**. Resolution did face the ambiguity, flagged it tier
4, and emitted a `DecisionRecord`; a human then answered it in the artifact. Collapsing that to
tier 1 would erase the fact that the pipeline contains a question someone had to answer — and
`needs_review()` would go quiet on a pipeline that is *more* in need of review than before, not
less.

So this spec adds a member rather than relabelling one, and invents no fifth tier:

- **`ValueSource.HUMAN`** — set on a value edited in `pipeline.yml`. `GOAL` keeps its current
  meaning and its tier-1 treatment.
- A `HUMAN` setting **keeps the tier of what it displaced**, so `seq_platform` stays tier 4 with
  `source: human`. An override answers an ambiguity; it does not abolish it.
- `needs_review()` gains a sibling **`overrides()`**, keyed on `source is ValueSource.HUMAN`, so
  "what did a person change" and "what still needs looking at" are separate questions with
  separate answers.
- **`needs_review()` excludes a setting that carries an override**, and `overrides()` lists it
  instead. Otherwise the count never reaches zero: you answer the question, the pipeline changes, and
  the CLI still says `REVIEW star_align.seq_platform` forever. `lockfile.py` makes this argument
  about a different list — *"a lockfile that cries wolf gets ignored"* — and it applies exactly.
  Invariant 6 still holds: the tier stays 4, the value is still flagged, and it is flagged in the
  list that describes what actually happened to it. Answered and unanswered are different states,
  and one list cannot mean both.

This is what closes [#10](https://github.com/comeni-project/Comeni-Labs/issues/10) properly. That
issue is *"answering a tier-4 parameter clears the flag without changing the pipeline"* — both
halves wrong in the same direction. Here, answering **changes the pipeline** (via `template:`) and
**moves the flag** rather than clearing it.

**And it decides an open question about `sealed`.** CLAUDE.md's protection-profile table says
`sealed` makes tier 4 *block the build*. With overrides keeping tier 4, a `sealed` lab could never
build a pipeline containing an answered tier-4 setting — it would be blocked permanently by a
question someone had already answered. So **`sealed` blocks on `needs_review()`, not on tier**: an
unanswered tier-4 value blocks, an answered one does not. That is what `sealed` is for — nothing
ambiguous goes unreviewed — and an override *is* the review, recorded, attributable, and visible in
`overrides()`. The `needs_review()`/`overrides()` split is what makes this expressible at all.

This is adjacent to A3 but not the same finding. A3 was a path reaching `main.nf` through an open
`dict`, and its fix (`HumanParamValue`, `PortName`) stands. What A3's docstring noted in passing
— that the override *suppressed the tier-4 flag it replaced* — is the part this section addresses,
and only for edits to the artifact.

### 7. Replay reports five categories, and refuses on one

`mendel upgrade` keeps `goal` plus every value with `source: human`, re-resolves against the new
registry, materialises a fresh `Pipeline`, and reapplies them:

```
$ mendel upgrade build/pipeline.yml --registry registry/ --out next/

drift      2  digest changed, resolved value unchanged
              nf-core/star/align@1.11.0   sha256:9f2c… → sha256:c418…
changes    1  the resolver now decides differently
              samtools/sort   tier 1 → tier 3 (a rule now covers it)
replayed   1  your edits, reapplied
              star_align.seq_platform = 'illumina'
ORPHANED   1  your edit no longer applies to anything
              hisat2_align.seq_platform — that step is gone
              → refused. remove the override, or pin the module.
```

**Most of this exists**, and an earlier draft of this section described it as new.
`mendel_resolver/replay.py` has `ReplayingResolver`: `_chosen()` already prefers
`record.human_override` over `record.chosen`, and it already tracks `replayed` and `fresh`. Two
things follow that the draft got wrong.

**Replay must keep the recorded `reason` verbatim.** `replay.py` carries a comment explaining that
the plan's wording — prefixing "replayed from a recorded decision" — *cannot survive*, because
`reason` is emitted as the comment above the parameter in `main.nf`, so prefixing it makes an
upgraded pipeline differ from the published one by exactly that string, and federation §4.1 requires
byte-identical Nextflow. That constraint applies unchanged here, and it is a trap this spec walks
straight past: `why.reason` is still emitted as a comment.

**`_still_applies` and `M0113` are two different cases, and the draft merged them.**

- **Stale** — the candidate set moved, so the record answers a question nobody is asking.
  `_still_applies` returns `False` and the existing code falls back to `FlagOnlyResolver`, which its
  docstring defends: *"replaying would assert a decision between options that no longer exist —
  worse than asking again, because it would look decided."* **That is right and stays.** What is
  wrong is that it currently vanishes into a `fresh` count with no statement that an override was
  discarded. It becomes its own reported category.
- **Orphaned** — the step or setting is gone entirely. `ReplayingResolver.resolve()` is *never
  called* for it, because there is no ambiguity to resolve, so no resolver hook can see it. It needs
  a post-resolution sweep comparing every recorded `source: human` value against the fresh
  `Pipeline`. **This is the genuinely new check**, and `M0113` is only about this case.

So `upgrade` reports **five** categories, not four:

```
drift      2  digest changed, resolved value unchanged
changes    1  the resolver now decides differently
replayed   1  your edits, reapplied verbatim
STALE      1  your edit no longer answers the question that is being asked
              star_align.seq_platform — candidates moved; re-asked, flagged tier 4
ORPHANED   1  your edit no longer applies to anything
              hisat2_align.seq_platform — that step is gone
              → refused, M0113
```

Stale re-asks and flags; orphaned refuses. The difference is whether there is still a question. An
override that silently stops applying is the same failure as a guard that silently stops guarding —
A14's shape — and today the stale half of it is silent. Drift and changes stay separate because Plan
1.7 established that distinction and it earns its keep: a digest moving is not the same event as a
decision moving.

### 8. Mappings are written, lists are stored

`tests/test_egress.py` forbids mappings anywhere a payload can reach, because a `dict` key
type-checks while saying nothing about whether the key was ever declared — which is why
`RequiredStates` is a record. `Constraints._accept_mapping` set the precedent that the ergonomic
form and the safe representation need not be the same decision.

A `model_validator(mode="before")` normalises mapping → list for: `settings`, `channels`,
`inputs`, `channels[].meta`, `goal.profile`, `goal.constraints.required_states`.

**No positional shorthand in `call:`.** The three `NfInput` shapes are written out explicitly.
Root G's rule is that a file can be read only one way, and `call:` is the field where a second
reading produces a silently miswired pipeline rather than a parse error.

**`channels[].params` is stored *and* derived, deliberately, and `M0121` is the price.** It is
extractable from `expression` — that is what `entry_params` does today, with `re.findall(r"params\.
(\w+)")` over Groovy. Storing it duplicates a fact, which root G is right to be suspicious of. It is
stored anyway, because taking a regex over arbitrary Groovy *out* of the emitter is a large part of
what materialisation buys, and `expression` is the one field this spec leaves unbounded. So the
duplication is accepted and then checked: `Pipeline.of()` validates the list against the extraction,
and `M0121` refuses a hand-edited file where the two have diverged. It is plural because
`entry_params` returns a set — one expression may legitimately reference several params, and the
shipped registry happening to be 1:1 today is not a schema guarantee.

### 9. Diagnostics

`Diagnostic.contract_id` generalises, because these point at a place in a file rather than always at
a contract. One type, one renderer, one flat `explain` namespace; `fix` stays required.

**The new field is `where:`, not `subject:`.** An earlier draft said `subject`, which collides:
`marks.py` already declares `Subject = Annotated[str, "subject"]` and `DecisionRecord.subject` uses
it for *the thing being decided* (`seq_platform`). A diagnostic's location is a different string
kind pointing at a different sort of thing, and reusing one mark for both is exactly what root C
exists to stop — the failure there was never that a string was unvalidated, it was that nobody had
written down which kind it was.

| band | what it covers |
|---|---|
| `M0100`–`M0107` | conformance — a contract disagrees with its module (**exists**) |
| `M0108`–`M0109` | reserved for conformance |
| `M0110`–`M0129` | the pipeline file — a setting, an override, or the format |

The pipeline band is twenty wide rather than ten. Reviewing this spec's own claims produced two
new codes before a line was written; a band sized to the first draft would already be full.

An earlier draft's column said *"refuses: build"* on almost every row. That is wrong now that four
verbs read `pipeline.yml`: **a load-time check must fire wherever the file is loaded**, or `mendel
emit` on a hand-edited file succeeds where `mendel build` would have refused. So the column is which
verbs a code fires on, and *any load* means all four.

| code | fires on | catches |
|---|---|---|
| `M0108` | build | `via: ext` / `key: args` on a module whose source never reads `task.ext.args` |
| `M0110` | any load | a setting with no `via:` |
| `M0111` | any load | `{value}` outside the closed character class |
| `M0112` | `verify` — **reports, does not refuse** | a frozen value disagrees with the contract's current digest |
| `M0113` | `upgrade` | an orphaned override. Only re-resolution can know, so no other verb can raise it |
| `M0114` | any load | a `template:` with no `{value}`, **or** a template on a route that takes none |
| `M0115` | any load | `via:` is not one of the three, or `key:` is not a legal `ExtKey` — including `when` |
| `M0116` | build | the file `build` wrote does not parse back to the same object |
| `M0117` | any load | `version:` is newer than this Mendel understands |
| `M0118` | any load | two writers for one destination — a `meta` key, a `prefix`, or a directive |
| `M0119` | any load | `via: directive` names something Nextflow will silently ignore |
| `M0120` | `emit` | `modules/` is absent, so the emitted `include` paths would point at nothing |
| `M0121` | any load | `channels[].params` disagrees with what `expression` actually references |
| `M0122` | any load | two settings on one step share a name, or two steps share an `id` |

`M0108` is build-only because it needs module source, which `emit` does not read. `M0120` is
emit-only because that is the verb that would otherwise write an unrunnable `main.nf`.

`M0108` costs nothing: `modulespec.py` already parses `reads_ext_args` as
`"task.ext.args" in source`. A setting claiming that route for a module that ignores it is a
checkable lie, and it lands in the reserved conformance band on day one. The same parse extends to
`key: prefix` — `task.ext.prefix` is present in 8 of the 10 shipped modules and absent from
`star/genomegenerate` and `samtools/index`, so the check has real negatives to find.

Four deserve their reasoning recorded:

**`M0114`** is the subtle one. `key: args` with a template that forgets `{value}` produces a
setting that looks wired, renders real flags, and discards the value. Deadness wearing a bridge
is *harder* to spot than today's honest no-op.

**`M0116`** is what makes the round trip load-bearing rather than decorative.

**`M0122`** is A11 arriving in a new type. `ModuleContract` already rejects a duplicate `Param`
name, because `IRNode.set_param` appends and a duplicate there *"died here with an uncaught
TypeError"* when the emitter's sort fell through to comparing two `ResolvedValue`s. The mapping form
of `settings:` makes this easier to hit, not harder: `yaml.safe_load` keeps the last of two
duplicate keys silently, which is root G's finding, so a duplicate would be *collapsed* rather than
caught. Written as a list it must be rejected explicitly.

**`M0118`** exists because `via: meta` and a `Measurement.meta_key` write to the same map. The
collision is a **Python** one before it is a Groovy one: `meta_for()` returns `dict[str,
ParamValue]` and `_render_meta` renders its sorted keys, so a setting and a measurement both
claiming `single_end` collide in that dict and one is gone before any Groovy is written. `prefix`
and each directive have the same property for the same reason. Two writers for one destination is
a refusal, not a precedence rule nobody remembers.

**`M0119`** is the one that costs something, and the premise was tested rather than assumed. A
pipeline whose config contained `process { withName: FOO { cpuz = 4 } }` ran to **exit 0 with no
diagnostic** on Nextflow 25.10.4 — no error, no warning, nothing. An unknown directive is silently
ignored, which is the exact failure this design exists to eliminate, so omitting the check would be
incoherent.

An earlier draft said the list of legal directive names *"belongs in the registry vocabulary as
data, not in the compiler as code"*. **That was wrong on both halves.** `Vocabulary` is strictly
per-type — one file per type id carrying `states`, `entry_channel` and `test_data` — and a flat
list of directive names is not a type. Putting it in a layer would mean a fifth member beside
`contracts/`, `rules/`, `vocabularies/` and `measurements/`, which collides directly with root B.

And the invariant-7 analogy does not hold. Vocabularies are closed because **a contract using an
undeclared biological state must fail**, and new states arrive through the forge as reviewed
domain knowledge. Nextflow's directive set is not domain knowledge; it is a fact about the
toolchain, it changes on Nextflow's release cycle rather than a laboratory's, and no lab should be
able to add `cpuz` to it by approving a data change. `modulespec.py` already encodes toolchain
facts in code for the same reason.

**So the list lives in `mendel-compiler`, as code, versioned with the Nextflow version it was read
against.** That is a genuine cost — a new Nextflow directive needs a release — and it is the right
one.

Rendered, with `where:` pointing into the file rather than at a contract id:

```
$ mendel upgrade build/pipeline.yml --registry registry/ --out next/

M0113  build/pipeline.yml → steps[hisat2_align].settings[seq_platform]
  Your override no longer applies to anything.
  This file records `source: human` for hisat2_align.seq_platform, but
  re-resolving the goal no longer produces a step called hisat2_align.
  fix: remove the override, or pin the module under `steps[].module` so the
       step survives re-resolution.
       `mendel explain M0113` for the long form.

1 diagnostic. Nothing emitted.
```

`where:` is a path into the document — `steps[<id>].settings[<name>]`, `channels[<type_id>]`,
`decisions[<key>]` — because a diagnostic about a file that does not say *where in the file* makes
the reader grep for it. `Diagnostic.render()` already lays out summary/detail/fix in that order and
needs no change beyond the field.

A test asserts every code the compiler can emit has an `EXPLANATIONS` entry. Fourteen new codes is
where `mendel explain M0118` answering *"not a diagnostic this version emits"* becomes likely.

### 10. What measurements do, so nobody "fixes" it

A `Measurement` has two jobs and only one of them is a route. `strandedness` and `paired` declare
`describes` + `meta_key` and reach the tool through the meta map. `read_length` and `n_samples`
declare neither, and correctly reach no tool — they are inputs to **rules**, which route
decisions rather than carrying values. A measurement with no `meta_key` is not a dead setting,
and `M0110` must not be extended to cover it.

---

## How this composes with the other roots

- **Root A (egress allowlist).** `Pipeline` becomes door 4's payload, replacing `PublishBundle`'s
  shape, so the guard walks it: no `Any`, no bare `str`, no mappings, every string a declared
  alias or `FreeText`. The mapping rule is stricter than it looks — `test_no_payload_carries_a_mapping`
  tests against `abc.Mapping`, not `dict`, because A6 found `Mapping[MeasurementId, …]` is a
  *superclass* of dict and slipped through. The free-text count must not change: the two permitted
  fields stay `PromptRequest.prompt` and `GateFailure.tool_message`. `tests/test_egress.py` holds its
  lists literally on purpose, so editing it is the intended friction.

  **One premise this change could invalidate silently.** `registry.py` carries a mapping and says
  it is legal *because* `Registry` is not reachable from a payload — *"a mapping is legal here in a
  way it is not on the IR."* Materialisation must therefore **copy values into `Step`** and never
  hold a `Registry`, a `ModuleContract` or a `Vocabulary` on `Pipeline`. If it did, that mapping
  becomes an egress violation and the guard would be reporting on a premise that no longer holds.
  `Pipeline.of()` takes a registry as an *argument*; `Pipeline` must not have a field for one.

- **Retiring `PublishBundle` is not one line.** The name appears in eight docstrings across
  `marks.py`, `ir.py`, `goal.py`, `registry.py`, `gates.py` and `mendel_resolver/goal.py`, and in
  every case it is *load-bearing rationale* — why `Goal` lives where it does, why `RequiredStates`
  is a record, why `comeni-core` owns `Gate`, why a mapping is legal on `Registry`. Those
  explanations must be rewritten to name `Pipeline`, not left pointing at a type that no longer
  exists. A rationale that cites a deleted type is worse than no rationale: it reads as authoritative
  and cannot be checked.
- **Root C (nothing is interpolated).** `template` is a **new string kind**, and it renders into
  Groovy — so it takes `entry_channel`'s discipline, not `reason`'s. Root C's table gains a sixth
  row. In exchange, `channels[].expression` becomes the *only* unbounded-Groovy field in the only
  emitted-from file, which is a better position than root C's current five kinds across two
  surfaces. If root C lands first, this spec's new markers must be added to its `Mark` enum, not
  invented beside it.
- **Root D (the verdict comes from the artifact).** `gate:` moves inside `pipeline.yml`. The
  sequencing here needs care, because root D is **actively rewriting `diff_ir(before: PipelineIR,
  after: PipelineIR)`** and this spec changes what it compares.

  **Root D lands first, as specified, against `PipelineIR`.** It closes a critical finding and must
  not wait. This spec then re-targets it to `Pipeline`, and root D's own tests are what verify the
  replacement did not regress — its test suite is the acceptance criterion for the change, not
  collateral.

  The prize is worth the ordering. Root D's finding is that `diff_ir` enumerates the fields it knows
  about, so every field added to the IR is a silent blind spot — Plan 1.8 added four. A **total**
  `Pipeline` makes the diff complete *by construction*: if every field of every replaced type has a
  declared home (§2), then a recursive walk over `model_fields` cannot miss one, because there is
  nowhere for a field to hide. Root D gets a guarantee it cannot reach by enumeration.

  Which means **§2's totality test and root D's completeness fix are the same idea twice** — one
  applied to construction, one to comparison. They should share a mechanism rather than each growing
  a hand-maintained field list, since a hand-maintained list is the defect in both cases.
- **Root B (a layer is one thing).** `registry.layers` and `registry.shadowed` are that
  provenance, carried on the artifact. Root B reports when an overlay replaces an
  `entry_channel`; this spec puts the resulting expression in the file, so the replacement is
  visible in the thing you read rather than only in a build-time message.
- **Root G (a file reads only one way).** `pipeline.yml` is a **new file format**, so it inherits
  root G's duplicate-key problem on arrival rather than acquiring it later. Root G's loader
  discipline applies to it from the first commit — this is why `call:` takes no shorthand.
- **Root I (every guard is watched failing).** The table below.
- **A14.** This spec touches `resolve.py` and `mendel_compiler/cli.py` — two of the four files
  CLAUDE.md names as requiring **`make verify`** rather than `make check`. That section exists
  because Plan 1.8 changed all four and reported each task verified on `make check` alone. Not to
  be repeated here.

  It also touches `emit.py`, which is *not* on that list — and on this change it should be. The
  list names the files whose breakage `make check` cannot see, and `tests/test_counts.py` is the
  only check that proves a setting reaches a tool. Rewriting `emit()`'s signature and its
  `ext.args` composition is precisely a change `make check` would wave through. **The plan should
  add `emit.py` to that list in CLAUDE.md**, rather than treating this spec as an exception to it.
- **A16 / Plan 2 Task 11.** Override replay reads `DecisionRecord.human_override`, and A16 is the
  `DecisionRecord.chosen` type conflation. This spec does not fix A16 and does not depend on it
  being fixed, but the plan should sequence after it if both are in flight, since replay is the
  code that would have to change twice.

---

## Verification

Root I applies. Each probe added, watched failing, reverted.

| probe | expected |
|---|---|
| a setting with `via:` removed | refused at load, `M0110`, naming the setting |
| `seq_platform: "illumina'; println 'X'; //"` | refused at load, `M0111`. **Root C's own attack, on the new surface** |
| `template: "--flag fixed"` with no `{value}` | refused, `M0114` |
| an override for a step that re-resolution does not produce | refused, `M0113` — **not warned, not dropped** |
| an override whose candidate set moved | re-asked and reported `STALE`; **not** refused, and **not** silent as it is today |
| a setting answered by an override | absent from `needs_review()`, present in `overrides()`, still tier 4 |
| `upgrade` replaying an override | the recorded `reason` emitted **verbatim** — byte-identical `main.nf`, federation §4.1 |
| `mendel upgrade --out` pointed at the input's own directory | refused — the existing never-overwrite test, with a second subject |
| `via: meta` on `single_end` while `paired` is also measured | refused, `M0118` |
| a `Pipeline` hand-built with `process: ""` | refused by `tests/test_construction.py` |
| a `Pipeline` field added with no `field_serializer` on a `frozenset` | refused at build, `M0116` |
| `via: directive` naming `cpuz` | refused, `M0119` |
| `version: 2` in a `pipeline.yml` | refused, `M0117` |
| **a step carrying two `key: args` settings, with the name-sort reverted** | **byte-identity must fail** |
| `key: when` on any setting | refused, `M0115` — a step's existence is resolution's call |
| `key: prefix` on `star/genomegenerate`, whose source has no `task.ext.prefix` | refused, `M0108` |
| the shipped registry, built then re-emitted from its own `pipeline.yml` | **byte-identical `main.nf` and `nextflow.config`** |
| `mendel emit` with no `--registry` and no network, `modules/` present | **succeeds** |
| `mendel emit` on a `pipeline.yml` with `modules/` deleted | refused, `M0120` — never a `main.nf` that cannot run |
| the emitted `nextflow.config`, against a golden file | **byte-identical** — a file with no coverage today |
| a measurement with no `meta_key` (`read_length`) | **still routes nothing, and is not flagged** |
| a field added to `PipelineIR` or `DecisionRecord` with no home in `Pipeline` | the totality test fails, naming the field |
| a `Registry` or `ModuleContract` field added to `Pipeline` | refused — `registry.py`'s mapping premise must hold |
| any `frozenset`-typed field on `Pipeline` | refused — `digest_of` is not stable over one |
| a hand-edited `pipeline.yml` with a bad setting, run through `mendel emit` | refused — a load check fires on **every** verb, not only `build` |
| `mendel verify` on a `pipeline.yml` built before `Param` gained `via` | reports drift on `star/align` and `hisat2/align` only — **expected, not a bug** |
| `GateFailure.tool_message` with newlines | **still accepted** — regression guard for root C's split |
| `tests/test_counts.py` with one real `key: args` setting on the spine | **the flag reaches the tool and changes observable output** |

Three rows carry most of the weight.

**The two-settings row is the one I expect to be got wrong.** With a single `key: args`
setting the name-sort is unobservable, so a test that reverts the sort still passes — a guard
that cannot see its own subject. This is the `frozenset`-has-no-stable-order trap in a new place.

**The counts row is a hard requirement, not a nice-to-have**, and what it covers today is narrower
than an earlier draft claimed. `test_counts.py` asserts `-s 2` and `-p`, and its own docstring says
why: *"Strandedness arrives through meta now."* So it proves the **meta** route reaches a tool and
says nothing about `ext.args`.

The `ext.args` route is proven only *implicitly*: `star/align` carries `--readFilesCommand zcat`,
TrimGalore emits `.fq.gz`, and STAR cannot read gzip without it — so dropping the route breaks the
spine and the counts test fails. Real coverage, but incidental, and it covers the **static**
`ext_args` string rather than the new thing. **Nothing at all covers a resolved param composing
into `ext.args`**, which is the mechanism this spec adds.

And `M0114` catches a template that ignores `{value}`; *nothing* catches a template whose flag is
wrong, because the flag goes to the tool and not to the module — the same limit that makes
`-stub-run` blind to a hollow input. So the spine must grow one real `key: args` setting whose
effect is visible in output, and `test_counts.py` must assert it took effect. Without that row the
routing mechanism is verified only by unit tests of its own machinery.

**The last-two-rows pattern from root C applies here too**: the byte-identical row and the
still-accepted rows are what catch over-correction. A fix that moves the spine's output, or that
breaks `entry_channel`, has gone too far.

---

## Blast radius

- **New:** `comeni_core/pipeline.py` — `Pipeline`, `Step`, `Setting`, `Channel`, `CallArg`,
  `RegistryProvenance`, `Via`, `ExtKey`, `Pipeline.of()`.
- `comeni_core/contract.py` — `Param` gains `via` (required), `key`, and `template`.
- `comeni_core/tiers.py` — `ValueSource.HUMAN`, beside `GOAL` and with its own rationale.
- `comeni_core/ir.py` — `overrides()` beside `needs_review()`.
- `comeni_core/egress.py` — door 4's payload becomes `Pipeline`; `PublishBundle` retires, and the
  eight docstrings that cite it by name are rewritten rather than orphaned.
- `comeni_core/marks.py` — the `NfTemplate` kind and its validator.
- `mendel_resolver/resolve.py` — an override keeps the displaced tier and sets `source: human`.
- `mendel_resolver/replay.py` — **extended, not written.** `ReplayingResolver` already prefers
  `human_override` and tracks `replayed`/`fresh`; it gains a reported `stale` list where
  `_still_applies` returns `False`, and the post-resolution orphan sweep that no resolver hook can
  perform. `_chosen()` and the verbatim-`reason` rule stay exactly as they are.
- `mendel_compiler/emit.py` — `emit(pipeline)`; `ext.args` composition and double-quoting;
  `via: directive` and `via: meta` emission.
- `mendel_compiler/conformance.py` — `where` replaces `contract_id`; `M0108`, `M0110`–`M0122`.
- `mendel_compiler/cli.py` — `emit`, `verify`, `upgrade` reworked; `build` round-trips. **And
  `mendel profile`, which the first draft of this radius missed**: it shares `build`'s emitter path,
  so it moves with the signature. It writes `pipeline.yml` *and* `profile.yml` — two files, correctly,
  because `profile.yml` is an instruction sheet for the laboratory rather than a description of the
  pipeline. "One artifact" is a claim about what describes the pipeline, not a cap on output files.
- `mendel_compiler/` — the legal Nextflow directive names, as code, carrying the Nextflow version
  they were read against. Not registry data; see `M0119`.
- `registry/` — `via:`, `key:` and `template:` on both `seq_platform` params; one real `key: args`
  setting on the spine for the counts assertion.
- **Tests, and one of them comes first.** A golden `tests/golden/spine/nextflow.config` is a
  **prerequisite commit** — that file has no coverage at all today and is where this mechanism
  emits. Then: `tests/golden/spine/main.nf` moves; `tests/test_egress.py` is edited for the new
  payload type; `tests/test_construction.py` gains `Pipeline`; `tests/test_counts.py` gains the
  reaches-a-tool assertion for a resolved param, which nothing covers now.

### Two things checked and found safe, recorded so nobody re-derives them

**Materialising `include:` does not break the no-path rule.** `test_publish_holds_no_filesystem_path`
asserts `str(ROOT) not in text` — an *absolute repo path*, not a slash. `modules/nf-core/star/align/main`
is a relative fragment, which is root C's `NfPath` kind, and it passes. The test does need
re-pointing: it names `pipeline.bundle.json` and `mendel.lock.yml` literally, and both retire.

**`Pipeline.of()`-only does not block A11's pathological-input test.**
`test_construction.py` walks `packages/*/src` and nothing else, so tests may hand-build a `Pipeline`
freely. That matters because `test_a11_the_emitter_never_compares_two_resolved_values` deliberately
constructs a node with duplicate params to prove the emitter survives one, and a sole-constructor
rule that covered `tests/` would have made that test unwritable. It does not.

Unlike root C, **the registry does change** — two contracts gain `via:`/`template:`, and the
spine gains a setting. So "byte-identical output" is a check on the *unchanged* parts only, and
the plan must say which golden diffs are expected before they appear, or the expected diff will
be used to wave through an unexpected one.

### Two digest consequences the spec had not accounted for

`digest_of` hashes `model.model_dump_json()`, and Pydantic dumps defaults as well as set fields. So:

**Adding `via`, `key` and `template` to `Param` moves the digest of every contract that has one.**
That is exactly two — `star/align` and `hisat2/align`. The other eight declare `params: []`, hold no
`Param` instance, and keep their digests. Narrow, but it invalidates any existing lockfile or bundle
pinning those two, and `mendel verify` will correctly report drift on a file built before this
change. The plan needs a line about that being expected rather than a bug report.

**`Pipeline` must respect the `frozenset` rule from birth.** `digest.py` states it outright:
*"Anything new that serialises a set needs the same treatment or it silently breaks this function and
every lockfile made with it."* `Pipeline` will be digested — it is what publish ships — so
`Step.inputs[].states`, which comes from `IREdge.states` (a `frozenset` carrying a `field_serializer`),
must be a **sorted `list[StateName]` fixed at materialisation**, not a set. Every other set-shaped
field on `Pipeline` needs the same, and the totality test above is the natural place to assert that
no field of `Pipeline` is a bare `frozenset`. This is the CLAUDE.md gotcha — `frozenset` has no
stable order — arriving in a new type that was designed after the lesson and could still miss it.

---

## What this spec does not cover

- **The `via: directive` vocabulary's exact shape.** That it is registry data rather than
  compiler code is decided; which file and what schema is a plan question.
- **Whether `mendel verify` should also re-resolve**, or only compare digests. Digest comparison
  is specified; a full re-resolve is what `upgrade` does, and whether `verify` should be a dry-run
  of it is open.
- **Issue [#2](https://github.com/comeni-project/Comeni-Labs/issues/2)** — `sealed` blocking
  tier-3 decisions on asserted measurements. Untouched. `ProfilePolicy` is still Plan 2.
- **Issue [#16](https://github.com/comeni-project/Comeni-Labs/issues/16)** — signed bundles. One
  self-contained file makes detached signing *easier* (sign `pipeline.yml`, ship the signature
  beside it), and the egress guard's `bytes` prohibition is unaffected. Still needs a federation
  §8 decision.
- **A16** — the `DecisionRecord.chosen` conflation. Noted as a sequencing interaction above, not
  fixed here.
- **Whether the emitted `params { }` block should shrink.** Entry params (`input`, `gtf`,
  `fasta`) stay as they are; they are lab-supplied data, not settings, and invariant 15 is why
  they default to `null`.
- **Plan 3's review screens.** They will read `pipeline.yml`, which is most of why it is YAML
  with a `why:` on every decision, but the API surface is Plan 3's.

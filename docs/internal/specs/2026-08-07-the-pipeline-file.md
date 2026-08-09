# The pipeline file — one artifact, every setting, every provenance

**Spec, 2026-08-09.** Closes [#10](https://github.com/comeni-project/Comeni-Labs/issues/10).
Supersedes the four-route settings surface described in `ARCHITECTURE.md`.

Verified against the code at `e9cab07`, then **re-verified against `ae92002`** (Plan 1.9 complete,
441 fast tests green) on 2026-08-09. Five citations were stale and are corrected inline, each marked
*"1.9 changed this"*; every design decision survived. What changed and what held is in
[the journal](../journal/).

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
  displaced: []                # 1.9 changed this: was `shadowed`
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
  - kind: param              # 1.9 changed this: param | producer | source
    key: star_align.seq_platform
    subject: seq_platform
    tier: 4
    candidates: [null]         # what was on the table
    chosen: null               # what the resolver took
    confidence: 0.0
    resolved_by: flag-only
    reason: "no rule covered 'seq_platform'"
    human_override: illumina   # replayed by `upgrade`

emitted:                       # 1.9 added this: what was written, recorded not reconstructed
  from_digest: sha256:c41a…    # of everything above, so staleness is detectable
  files:
    - {name: main.nf,         digest: sha256:7b31…}
    - {name: nextflow.config, digest: sha256:0ac9…}

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

**`inputs:` replaces the flat edge list**, keyed under the consuming step, and its `from:` values are
already a declared kind: 1.9 added `EdgeRef` (`<node>.<port>`, both Groovy identifiers) for exactly this
string, because bare values were indistinguishable from filenames — A16. Lossless, since an
`IREdge` has exactly one consuming port, and it makes "where does this step's GTF come from"
answerable without scanning a separate list. Root D's finding that `diff_ir` ignored `ir.edges`
is the reason edges must be prominent rather than tucked away.

**`emitted.from_digest` closes a gap consolidation opens.** Decided 2026-08-09. `Emitted` records the
digests of the generated files, so a hand-edited `main.nf` is caught. It cannot catch the opposite and
more likely mistake: **Nextflow runs `main.nf`, not `pipeline.yml`.** Edit the file you were told to edit,
forget `mendel emit`, and the pipeline that runs is not the pipeline that is documented — with every
digest matching, because the bytes on disk are exactly the bytes that were written. The artifact and the
run diverge silently, which is the one failure this whole design exists to prevent, arriving through the
door the design itself installs.

So `emitted:` carries `from_digest`: the digest of the pipeline content those files were generated from,
computed over the model **with `emitted:` excluded** — otherwise it would have to contain its own digest.
That is the same exclusion `ResolvedValue._drop_computed` makes for `review_level`, and for the same
reason: a derived field inside the thing it describes does not round-trip.

Two failure modes, told apart:

| what happened | detected by | code |
|---|---|---|
| `pipeline.yml` edited, not re-emitted | `from_digest` ≠ the file's current content | `MD0213` |
| `main.nf` or `nextflow.config` hand-edited | `files[].digest` ≠ the bytes on disk | `MD0214` |

Both are `any load`, so every verb that opens the directory reports them. And `MD0214`'s `fix:` must say
**edit `pipeline.yml` and re-emit** rather than "revert your change" — a person who hand-edited `main.nf`
was trying to change the pipeline, and the file that does that is the other one. A diagnostic that only
forbids is half a diagnostic.

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
| `DecisionRecord.kind` | **1.9 added it.** A record is now `ParamDecision`/`ProducerDecision`/`SourceDecision` discriminated on `kind`, whose docstring notes `kind` reaches the artifact |
| `PublishBundle.emitted` | **1.9 added it.** Digests of what was written — see the root-D note |
| `Displacement.*` | **1.9 replaced `shadowed`** with something wider: an overlay measurement or vocabulary previously reached the artifact as nothing at all |

Losing `container` is the serious one: a consolidation meant to *strengthen* reproducibility would
have quietly dropped the field the clinical protection profile depends on.

So the requirement is not a longer example. **A test asserts that every field of `PipelineIR`,
`IRNode`, `ResolvedValue`, `ParamDecision`, `ProducerDecision`, `SourceDecision`, `Lockfile`,
`LockedContract`, `LockedLayer`, `Displacement`, `Emitted`, `EmittedFile`, `Goal` and `DataProfile`
has a declared home in `Pipeline`** — mechanically, over `model_fields`, with an
explicit allowlist for anything deliberately not carried. This is root D's finding applied to
consolidation rather than to diffing: `diff_ir` enumerated the fields it knew about, so every field
added to the IR became a silent blind spot, and Plan 1.8 added four. A hand-written mapping between
three types and one has exactly that shape, and reviewing it by eye already failed five times.

**And the converse rule: every embedded field must be productive.** Self-containment widens door 4 —
`pipeline.yml` embeds contract-derived strings (`process`, `include`, `template`, `expression`) that
`PublishBundle` only ever pinned by digest. That widening was accepted on 2026-08-09 **on the
condition that nothing rides along**. So a field is embedded only if it is either:

1. **read by `emit`** — without it the Nextflow cannot be regenerated; or
2. **provenance that cannot be reconstructed** — `why.reason`, `displaced_layer`, `gate`: facts about
   *this* build that no later registry lookup recovers.

Anything that fails both tests is pinned by digest, not embedded. No whole contracts, no
`provenance:` blocks, no `meta.yml` prose, no container tag *and* digest where one will do. Totality
(above) says nothing is silently lost; this says nothing is silently added. A payload that grows
because embedding is convenient is how a door with no undo gets wide, and the test that holds the
egress lists literally is the wrong place to notice it.

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
mendel upgrade build/pipeline.yml --registry registry/ --dry-run   # = verify; writes nothing
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

**`verify` is `upgrade --dry-run`, not a separate verb** — decided 2026-08-09. A digest-only compare
was the alternative, and it answers a strictly weaker question: it can say a contract moved, but not
whether the pipeline would resolve differently. A dry run reports all five categories — drift,
changes, replayed, stale, orphaned — and writes nothing.

That collapses two code paths into one, which matters more than the saved verb: a `verify` that
compared digests while `upgrade` compared resolutions would be two answers to "is this pipeline still
what it says it is", and root D's whole finding is what happens when a comparison is not the one that
governs. One path, one answer, `--dry-run` deciding only whether bytes are written.

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
    ARGS   = "args"          # evidence: 10 of 10 vendored modules
    ARGS2  = "args2"         # nf-core CONVENTION only — see below
    ARGS3  = "args3"         # nf-core CONVENTION only — see below
    PREFIX = "prefix"        # evidence: 8 of 10 vendored modules
```

**`args2` and `args3` are in this enum on convention, not on evidence.** `grep -rn "ext.args2\|ext.args3"
over `vendor/` and `registry/` finds nothing: no vendored module reads them. They are standard nf-core
for modules that pipe one tool into another, and they are included because adding an `ExtKey` value
later costs a `version:` bump for every archived file whereas an unused value costs nothing. That is a
deliberate asymmetry, and it is the one judgement in this enum that rests on knowledge of nf-core
rather than on this repository. **If a reviewer thinks it is wrong, this is the line to strike** —
`MD0108`'s check (does the module actually read this key?) will refuse a contract that names an unused
key anyway, so a wrong inclusion here fails loudly at build rather than silently at run time.

Three emission sites, because those are the three places the compiler writes into — the `ext`
scope, the channel's meta map, and the directive scope. That is verifiable against the emitter
rather than being a prediction about Nextflow, which is why it is the claim worth making.

`via: ext` requires `key:`. A `directive` requires a name from the compiler's directive list, which
is code rather than registry data for reasons §9 sets out under `MD0209`.

**A setting without `via:` fails to load.** That makes a dead setting structurally impossible
rather than merely detectable, and it closes #10 by removing the possibility rather than by
adding a warning.

Composition is deterministic per key: for `ext.args`, the contract's static `ext_args` first, then
each `via: ext` / `key: args` setting in **name-sorted** order. `prefix`, `meta` and `directive`
take a single value and refuse a second writer (`MD0208`).

**`ext.when` is deliberately absent, and refused.** It is a boolean that skips a process
entirely, so a setting could switch off a step while `steps:` and `inputs:` still describe it
running. That is a second routing mechanism competing with resolution, and it would make the
file's DAG a claim rather than a description. Whether a step exists is decided by resolving the
goal. A `pipeline.yml` naming `key: when` is refused by `MD0205`.

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

#### The assumption behind the character class, and how to revisit it

**Decided 2026-08-09: start strict, on the stated assumption that almost no tool setting needs a
space or a slash in its value.** Written down because it is an assumption and not a fact.

The asymmetry is what makes strict the safe direction: **loosening later is backward-compatible** —
every file that validated still validates — while tightening later invalidates files already sitting
on labs' disks. So the cost of being wrong in this direction is one release; the cost of being wrong
in the other is unreadable archives.

But the three excluded character classes are not equally cheap to admit later, and treating them as
one thing would make a future fix look smaller than it is:

| | why it is excluded | cost to allow later |
|---|---|---|
| `/` | nothing — it is inert in this position | **trivial.** Widen the class. |
| space | `ext.args` is space-joined into one command line, so `--flag a b` becomes a flag plus a stray argument *unless the template quotes* — and whether a template quotes is not reliably checkable | **moderate.** Needs the substituted value shell-quoted at emit time, which moves every `ext.args` string and every golden file. |
| `'` `"` `$` `` ` `` `;` newline | shell injection. `'PL:{value}'` is escapable in one character | **should stay excluded.** This is root C's subject, and the reason the mechanism is refuse-not-escape. |

So the honest future path is: allow `/` by widening the class; allow spaces by shell-quoting the
value at substitution time, in its own commit, with the golden-file churn that implies. Not the same
size of change, and the plan should not record them as one.

**Where this is documented is the point.** A note in a spec is not read by the person who hits the
wall. The message goes in **three places**, and the third is public:

1. **`Diagnostic.fix`** for `MD0201` — what to do, at the moment of refusal.
2. **`EXPLANATIONS["MD0201"]`** — the long form behind `mendel explain MD0201`.
3. **`docs/reference/cli.md`** — the diagnostics table, which is where `MD0100`–`MD0107` already live
   and is **public documentation**, not a working note. Written for a stranger, therefore: state that
   the limit is deliberate, that a value needing a space or a slash may be a legitimate case nobody
   has hit yet, and where to report one.

All three say the same thing because the reader arrives at whichever one they arrive at. And the
first genuine counterexample is a finding rather than a bug report: it means a boundary drawn on
reasoning was drawn in the wrong place, and §5's table already says what allowing each class costs.

**`template:` is legal only where the destination is an argument string** — `key: args`, `args2`,
`args3`. `prefix`, `meta` and `directive` each take one typed value and emit it directly; a
template there has nothing to compose into, and `cpus = "--cpus 12"` is not a thing. `MD0204`
therefore covers both halves of the same mistake: a template that never mentions `{value}`, and a
template on a route that takes none.

**Corrected 2026-08-09 by experiment.** Two earlier drafts said `ext.args` must be emitted as a
**double-quoted** Groovy string so `${meta.id}` interpolates. That is false, and Nextflow says so
loudly:

```
$ # process { withName: FOO { ext.args = "--rg ID:${meta.id}" } }
ERROR ~ Unknown config attribute `process.withName:FOO.meta.id`
```

A double-quoted string in a config file is a GString evaluated **when the config is parsed**, where
no task exists and `meta` is not a name. The form that works is a **closure**, evaluated per task:

```
$ # process { withName: FOO { ext.args = { "--rg ID:${meta.id}" } } }
echo "ARGS=[--rg ID:SAMPLE1]"          # from the resolved .command.sh
```

So the emission rule is not about quote characters, it is about **whether the template needs the
task**:

| template | emitted as |
|---|---|
| no `${…}` — e.g. `--readFilesCommand zcat` | single-quoted string, **exactly as today** |
| any `${…}` | `ext.<key> = { "…" }`, a closure |

Two consequences the drafts got wrong. **The golden files move far less than predicted** — a static
`ext_args` keeps its single quotes, so only a step carrying a dynamic template moves at all. And
`_render_literal` stays correct for the static case rather than being replaced.

An earlier draft said *"every golden file moves, as a reviewable diff"*, and then that
`nextflow.config` had *"no golden, no assertion, no coverage of any kind"*. **1.9 falsified the second
half and the first is still true.** Precisely:

- There is still exactly **one golden file**, `tests/golden/spine/main.nf`, and it is not the file this
  change writes into.
- `nextflow.config` now **does** have coverage, of two kinds. A27 added
  `test_a27_a_config_process_block_cannot_be_broken_out_of` — the injection guard, on the surface root C
  called "the second surface" because it was assembled by f-strings. And A28's `emitted:` digests mean
  `mendel upgrade` reports *"the generated pipeline differs: nextflow.config"*.

**A golden `nextflow.config` is still a prerequisite, for a narrower and better reason than the draft
gave.** A recorded digest and a golden file answer different questions. The digest catches *it changed*
— against what this build itself produced, after the fact. A golden catches *it changed to something
wrong*, in review, before merge, as a diff a person reads. `ext.args` composition is where a wrong flag
would appear, and a wrong flag reaches the tool while every digest check stays perfectly happy: the bytes
match what was emitted, and what was emitted was wrong. That is the same gap `-stub-run` has against a
hollow input.

**`template:` is legal only where the destination is an argument string** — `key: args`, `args2`,
`args3`. `prefix`, `meta` and `directive` each take one typed value and emit it directly; a
template there has nothing to compose into, and `cpus = "--cpus 12"` is not a thing. `MD0204`
therefore covers both halves of the same mistake: a template that never mentions `{value}`, and a
template on a route that takes none.

**Corrected 2026-08-09 by experiment.** Two earlier drafts said `ext.args` must be emitted as a
**double-quoted** Groovy string so `${meta.id}` interpolates. That is false, and Nextflow says so
loudly:

```
$ # process { withName: FOO { ext.args = "--rg ID:${meta.id}" } }
ERROR ~ Unknown config attribute `process.withName:FOO.meta.id`
```

A double-quoted string in a config file is a GString evaluated **when the config is parsed**, where
no task exists and `meta` is not a name. The form that works is a **closure**, evaluated per task:

```
$ # process { withName: FOO { ext.args = { "--rg ID:${meta.id}" } } }
echo "ARGS=[--rg ID:SAMPLE1]"          # from the resolved .command.sh
```

So the emission rule is not about quote characters, it is about **whether the template needs the
task**:

| template | emitted as |
|---|---|
| no `${…}` — e.g. `--readFilesCommand zcat` | single-quoted string, **exactly as today** |
| any `${…}` | `ext.<key> = { "…" }`, a closure |

Two consequences the drafts got wrong. **The golden files move far less than predicted** — a static
`ext_args` keeps its single quotes, so only a step carrying a dynamic template moves at all. And
`_render_literal` stays correct for the static case rather than being replaced.

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

**`_still_applies` and `MD0203` are two different cases, and the draft merged them.**

- **Stale** — the candidate set moved, so the record answers a question nobody is asking.
  `_still_applies` returns `False` and the existing code falls back to `FlagOnlyResolver`, which its
  docstring defends: *"replaying would assert a decision between options that no longer exist —
  worse than asking again, because it would look decided."* **That is right and stays.** What is
  wrong is that it currently vanishes into a `fresh` count with no statement that an override was
  discarded. It becomes its own reported category.
- **Orphaned** — the step or setting is gone entirely. `ReplayingResolver.resolve()` is *never
  called* for it, because there is no ambiguity to resolve, so no resolver hook can see it. It needs
  a post-resolution sweep comparing every recorded `source: human` value against the fresh
  `Pipeline`. **This is the genuinely new check**, and `MD0203` is only about this case.

So `upgrade` reports **five** categories, not four:

```
drift      2  digest changed, resolved value unchanged
changes    1  the resolver now decides differently
replayed   1  your edits, reapplied verbatim
STALE      1  your edit no longer answers the question that is being asked
              star_align.seq_platform — candidates moved; re-asked, flagged tier 4
ORPHANED   1  your edit no longer applies to anything
              hisat2_align.seq_platform — that step is gone
              → refused, MD0203
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

**`channels[].params` is stored *and* derived, deliberately, and `MD0211` is the price.** It is
extractable from `expression` — that is what `entry_params` does today, with `re.findall(r"params\.
(\w+)")` over Groovy. Storing it duplicates a fact, which root G is right to be suspicious of. It is
stored anyway, because taking a regex over arbitrary Groovy *out* of the emitter is a large part of
what materialisation buys, and `expression` is the one field this spec leaves unbounded. So the
duplication is accepted and then checked: `Pipeline.of()` validates the list against the extraction,
and `MD0211` refuses a hand-edited file where the two have diverged. It is plural because
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

| codes | what they cover |
|---|---|
| `MD0100`–`MD0108` | conformance — a contract disagrees with its module (`MD0100`–`MD0107` **exist**) |
| `MD0200`–`MD0214` | the pipeline file — a setting, an override, or the format |

`MD` is Mendel's deterministic core — the three pure packages. The forge, the API and `mendel-ai` take
`MF`, `MA` and `MI`; bands of one hundred group concerns inside each prefix, and a full band overflows
rather than renumbering. §10 has the scheme and the reasoning, including the two drafts it replaced.

An earlier draft's column said *"refuses: build"* on almost every row. That is wrong now that four
verbs read `pipeline.yml`: **a load-time check must fire wherever the file is loaded**, or `mendel
emit` on a hand-edited file succeeds where `mendel build` would have refused. So the column is which
verbs a code fires on, and *any load* means all four.

| code | fires on | catches |
|---|---|---|
| `MD0108` | build | `via: ext` / `key: args` on a module whose source never reads `task.ext.args` |
| `MD0200` | any load | a setting with no `via:` |
| `MD0201` | any load | `{value}` outside the closed character class — **its message must say the limit is an assumption and invite the counterexample** |
| `MD0202` | `upgrade` (incl. `--dry-run`) — **reports, does not refuse** | a frozen value disagrees with the contract's current digest |
| `MD0203` | `upgrade` | an orphaned override. Only re-resolution can know, so no other verb can raise it |
| `MD0204` | any load | a `template:` with no `{value}`, **or** a template on a route that takes none |
| `MD0205` | any load | `via:` is not one of the three, or `key:` is not a legal `ExtKey` — including `when` |
| `MD0206` | build | the file `build` wrote does not parse back to the same object |
| `MD0207` | any load | `version:` is newer than this Mendel understands |
| `MD0208` | any load | two writers for one destination — a `meta` key, a `prefix`, or a directive |
| `MD0209` | any load | `via: directive` names something Nextflow will silently ignore |
| `MD0210` | `emit` | `modules/` is absent, so the emitted `include` paths would point at nothing |
| `MD0211` | any load | `channels[].params` disagrees with what `expression` actually references |
| `MD0212` | any load | two settings on one step share a name, or two steps share an `id` |
| `MD0213` | any load | `pipeline.yml` has changed since the Nextflow was generated from it |
| `MD0214` | any load | `main.nf` or `nextflow.config` was hand-edited since it was generated |

`MD0108` is build-only because it needs module source, which `emit` does not read. `MD0210` is
emit-only because that is the verb that would otherwise write an unrunnable `main.nf`.

`MD0108` costs nothing: `modulespec.py` already parses `reads_ext_args` as
`"task.ext.args" in source`. A setting claiming that route for a module that ignores it is a
checkable lie, and it lands in the reserved conformance band on day one. The same parse extends to
`key: prefix` — `task.ext.prefix` is present in 8 of the 10 shipped modules and absent from
`star/genomegenerate` and `samtools/index`, so the check has real negatives to find.

Four deserve their reasoning recorded:

**`MD0204`** is the subtle one. `key: args` with a template that forgets `{value}` produces a
setting that looks wired, renders real flags, and discards the value. Deadness wearing a bridge
is *harder* to spot than today's honest no-op.

**`MD0206`** is what makes the round trip load-bearing rather than decorative.

**`MD0212`** is A11 arriving in a new type. `ModuleContract` already rejects a duplicate `Param`
name, because `IRNode.set_param` appends and a duplicate there *"died here with an uncaught
TypeError"* when the emitter's sort fell through to comparing two `ResolvedValue`s. The mapping form
of `settings:` makes this easier to hit, not harder: `yaml.safe_load` keeps the last of two
duplicate keys silently, which is root G's finding, so a duplicate would be *collapsed* rather than
caught. Written as a list it must be rejected explicitly.

**`MD0208`** exists because `via: meta` and a `Measurement.meta_key` write to the same map. The
collision is a **Python** one before it is a Groovy one: `meta_for()` returns `dict[str,
ParamValue]` and `_render_meta` renders its sorted keys, so a setting and a measurement both
claiming `single_end` collide in that dict and one is gone before any Groovy is written. `prefix`
and each directive have the same property for the same reason. Two writers for one destination is
a refusal, not a precedence rule nobody remembers.

**`MD0209`** is the one that costs something, and the premise was tested rather than assumed. A
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

MD0203  build/pipeline.yml → steps[hisat2_align].settings[seq_platform]
  Your override no longer applies to anything.
  This file records `source: human` for hisat2_align.seq_platform, but
  re-resolving the goal no longer produces a step called hisat2_align.
  fix: remove the override, or pin the module under `steps[].module` so the
       step survives re-resolution.
       `mendel explain MD0203` for the long form.

1 diagnostic. Nothing emitted.
```

`where:` is a path into the document — `steps[<id>].settings[<name>]`, `channels[<type_id>]`,
`decisions[<key>]` — because a diagnostic about a file that does not say *where in the file* makes
the reader grep for it. `Diagnostic.render()` already lays out summary/detail/fix in that order and
needs no change beyond the field.

**The codes are also public documentation, and an earlier draft had forgotten it.**
`docs/reference/cli.md` carries the `MD0100`–`MD0107` table, a rendered example and the `mendel
explain` usage — it is the document a stranger reads, public since 2026-08-04. All sixteen new codes
belong there, and one existing row goes stale: `MD0100`'s entry says the contract is *"recorded in
`pipeline.ir.json` as `unverified`"*, and that file retires here — the fact moves to
`registry.unverified`.

That draft proposed a test asserting every code appears in `cli.md`. **§10 supersedes it**: the table
is generated from `diagnostics.yml`, so it cannot drift, and `--check` is both the test and the fix.

Codes are declared in `diagnostics.yml` and validated at construction (§10), so a code with no
explanation is unrepresentable rather than merely tested for.

### 10. The codes are data, and the document is generated

Decided 2026-08-09. Everything above describes the codes as prose in three places kept in step by a
test. **That is the wrong shape** — it is the same hand-maintained-list defect as root D's `diff_ir`
and §2's field mapping, wearing documentation's clothes. One source, two derived artifacts.

```yaml
# packages/comeni-core/src/comeni_core/diagnostics.yml   — see "why comeni-core" below
MD0201:
  band: pipeline-file
  says: "`{value}` outside the closed character class"     # one line — it is a table row
  fires_on: [build, emit, upgrade]
  refuses: true
  fix: |
    Use letters, digits, and `_ . : + - ` only, or a number, or true/false.
    If your value legitimately needs a space or a slash, that is a case we assumed
    did not exist — please report it at github.com/comeni-project/Comeni-Labs/issues.
  explanation: |
    A template substitutes {value} into a string that becomes part of a shell command
    line. Rather than escape dangerous characters, Mendel refuses them …
```

**Why `comeni-core` and not `mendel-compiler`.** The forge, the API and `mendel-ai` will all emit
diagnostics, and codes are globally unique across the M-namespace. Putting the registry in
`mendel-compiler` forces one of two bad outcomes: `mendel-forge` depends on the compiler — a
dependency that exists for a data file and points the wrong way for an impure package — or the forge
gets a *second* registry, and `mendel explain M0201` cannot answer because the compiler has never
heard of it. `comeni-core` is the one package everything already depends on, so one registry stays one
registry and every `explain` in the system reads it.

**A two-letter prefix per subsystem, with 100-wide bands inside it.** Decided 2026-08-09, after two
wrong drafts worth recording because both looked reasonable.

The first put 100-wide numeric bands under a single `M`. The second gave each subsystem its own letter
— `F` forge, `A` api — which fixed the band ceiling but split one product across three namespaces and
forced a rule reserving `A` away from Nightingale's future API. Two letters keep both properties: `M`
still means Mendel, and the second letter says which part.

| prefix | subsystem | purity |
|---|---|---|
| `MD` | the **deterministic core** — `comeni-core`, `mendel-resolver`, `mendel-compiler` | pure |
| `MF` | the forge | impure |
| `MA` | `mendel-api` | impure |
| `MI` | `mendel-ai` | impure |
| `N…` | Nightingale | — |
| `W…` | Wiener | — |

The prefix follows **the purity split `ARCHITECTURE.md` already uses**, rather than inventing a
taxonomy: `MD` is exactly the set of packages that may not reach the network. And a future
Nightingale API is `NA`, so the collision the one-letter scheme needed a rule for cannot arise.

Inside `MD`, bands of one hundred group by concern:

| band | concern | used |
|---|---|---|
| `MD0000`–`MD0099` | loading registry data — contracts, vocabularies, rules, measurements | none yet; today these are Pydantic errors |
| `MD0100`–`MD0199` | **conformance** — a contract disagrees with its module | `MD0100`–`MD0108` |
| `MD0200`–`MD0299` | **the pipeline file** — a setting, an override, or the format | `MD0200`–`MD0212` |
| `MD0300`–`MD0399` | routing and resolution | none yet; `UnroutablePinError` if it joins |
| `MD0400`–`MD0499` | gates and emission | none yet |

**A band may overflow into a new band. A code may never be renumbered.** That is the rule that makes
banding safe, and it is the answer to the objection that killed the twenty-wide version: if
conformance ever exceeds a hundred codes, its hundred-and-first is `MD0900`, not a renumbering of
`MD0100`. An ugly discontinuity in a table is a cosmetic cost paid once; a renamed code breaks every
laboratory runbook, support thread and pinned URL that cites it. **Published codes are immutable.**

**One rename happens now, and now is the last cheap moment.** `M0100`–`M0107` become
`MD0100`–`MD0107`: one mechanical substitution across roughly 107 places in live code, tests and
public documentation. The repository went public on 2026-08-04 and there is no released version, so
nothing external cites these yet. That will not be true for long, and the rule above means it can
never be done again.

**History is not rewritten.** Roughly 120 further occurrences live in `docs/internal/journal/`,
`docs/internal/audits/` and the 2026-08-05 conformance plan. Those are append-only and were correct on
their date — the same convention that leaves journal entries saying "Plan 2.5" for what is now Plan
1.7. A reader meeting `M0104` in a journal entry needs one line in `docs/reference/cli.md` saying the
`MD` prefix arrived on 2026-08-09 and old entries predate it.

**The thirteen pipeline-file codes move into their own band while they are still free.** They were
drafted as `M0110`–`M0122`, wedged against conformance because that is where there was room. Nothing
implements them, so they become `MD0200`–`MD0212` at no cost, and conformance keeps `MD01xx` whole —
including `MD0108`, the `task.ext.args` check, which is conformance and belongs there rather than in
the pipeline band.

**Grouping still lives in the data as well as the number.** `diagnostics.yml` carries `emitted_by:` and
`concern:`, and the generated `cli.md` renders sections from them. The band makes a code *readable*;
the field makes the document *correct*. Neither alone is enough — a band tells you nothing if you have
not memorised the table, and a field tells you nothing until you look it up.

**Open question for the plan:** whether the resolver's typed exceptions join the scheme as `M`-codes.
`UnroutablePinError` is user-facing — a genuine contradiction between a pin and its inputs — and reads
like a diagnostic; the others are closer to programming errors. Not decided here.

**What stays in code, and why the boundary is there.** `summary` and `detail` interpolate the actual
mismatch — *this* contract, *this* declared value versus *that* module's. They stay at the check
site. What moves to data is the code's **identity**: its one-line description, its standing advice,
its long form, which verbs raise it, whether it refuses. That split is exactly the line between
per-occurrence and per-code, and it is also the line that keeps root C's interpolation problem out of
the data file: nothing in `diagnostics.yml` is a template.

**Three things the compiler pulls, and one of them replaces a test with a type.**

1. **`Diagnostic` validates `code` against the registry**, so an undeclared code **cannot be
   constructed**. The test "every emittable code has an explanation" stops being a test and becomes
   unrepresentable — which is invariant 7's shape (a closed vocabulary; a contract using an
   undeclared state fails to load) applied to diagnostics. This is strictly better than the test it
   replaces, because a test can only find codes on paths it executes.
2. **`explain()` reads `explanation` from the registry.** The `EXPLANATIONS` dict retires, and with it
   the possibility of a code that exists in one and not the other.
3. **`Diagnostic.fix` defaults to the registry's `fix`**, so a check site restates nothing. It stays
   overridable per occurrence, because some fixes must name real values — `fix` being required
   (*"a diagnostic without this is half a diagnostic"*) is unchanged.

**`tools/generate_diagnostics_doc.py`, mirroring `tools/generate_types.py` exactly** — render between
markers in `docs/reference/cli.md`, `--check` compares and exits 1 with *"run: uv run python
tools/generate_diagnostics_doc.py"*, and `make check` gains it beside `make types`. The same pattern,
because a second convention for the same job is how one of them rots. The generated table therefore
**cannot** drift, so §9's proposed "every code appears in `cli.md`" test is deleted rather than
written: `--check` is that test, and it is the one that also fixes the file.

Three things easy to get wrong here, all with precedent in this repository:

- **Root G applies to this file.** `yaml.safe_load` silently keeps the last of two duplicate keys, so
  a `diagnostics.yml` with `MD0201` twice would load one and lose one. It takes the same loader
  discipline as a contract.
- **`says` must be a single line.** It is rendered into a markdown table row; a newline breaks the
  table silently rather than loudly. Root C's `Line`/`Text` split, in a new place — `says` is `Line`,
  `fix` and `explanation` are `Text`.
- **It must ship inside the wheel.** `mendel explain MD0201` has to work from an installed package
  with no repository checked out, so `diagnostics.yml` is package data and needs the packaging entry
  to match. This repo has been bitten twice by a file that existed locally and not where it was
  needed — `/build/` in `.gitignore` swallowing a vendored module, and `uv sync` installing nothing
  the root project does not depend on.

**It belongs in Plan 1.10 rather than after it**, for two reasons. Fourteen codes are being added, and
adding them to a hand-maintained table then extracting it means writing the content twice. And the
band reservation has to precede Plan 2, or the forge picks numbers in whatever range is free and the
namespace acquires its layout by accident.

**No GitHub Action commits the generated doc**, and that is a decision rather than an omission — see
*What this spec does not cover*.

### 11. What measurements do, so nobody "fixes" it

A `Measurement` has two jobs and only one of them is a route. `strandedness` and `paired` declare
`describes` + `meta_key` and reach the tool through the meta map. `read_length` and `n_samples`
declare neither, and correctly reach no tool — they are inputs to **rules**, which route
decisions rather than carrying values. A measurement with no `meta_key` is not a dead setting,
and `MD0200` must not be extended to cover it.

---

## How this composes with the other roots

- **Root A (egress allowlist).** **1.9 made this stricter than the spec described.** The guard is now a
  positive allowlist — `test_every_payload_field_is_a_declared_shape` walks every payload field
  recursively and requires a *declared shape*, closing A19 (`object`), A20 (`Any`) and A30 (`Path`)
  together, "with everything round three would otherwise find". So it is no longer four prohibitions to
  satisfy but one rule: **every leaf of `Pipeline`, `Step`, `Setting`, `Channel`, `CallArg` and
  `RegistryProvenance` must be a declared shape.**

  That is a gift rather than a cost: it *enforces* the productive rule in §2 mechanically. A field
  embedded because it was convenient has to be given a declared type first, and giving it one is where
  someone asks whether it belongs. `Displacement` already passes — its docstring says every field is a
  `StrEnum` or a marked string so it "may cross a door" — which is the pattern the new types follow.

  The free-text count must not change: the two permitted fields stay `PromptRequest.prompt` and
  `GateFailure.tool_message`. `tests/test_egress.py` holds its lists literally on purpose, so editing it
  is the intended friction.

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
- **Root C (nothing is interpolated).** **Landed in 1.9, and richer than this spec assumed.** `Mark` is
  an eighteen-entry enum and four of this schema's fields already have their kind waiting:
  `channels[].expression` is `GroovyExpression`, `include:` is `NfPath`, `process:` is `NfIdentifier`,
  and `inputs[].from` is `EdgeRef`. `Line`/`Text` exist, so `why.reason` is `Line` and `fix`/`explanation`
  are `Text`. `PARAM_LITERAL` exists for values.

  What is still missing is the template kind. `template` is a **new string kind**, and it renders into
  Groovy — so it takes `entry_channel`'s discipline, not `reason`'s. Root C's table gains a sixth
  row. In exchange, `channels[].expression` becomes the *only* unbounded-Groovy field in the only
  emitted-from file, which is a better position than root C's current five kinds across two
  surfaces. If root C lands first, this spec's new markers must be added to its `Mark` enum, not
  invented beside it.
- **Root D (the verdict comes from the artifact).** **1.9 changed this, and solved it differently than
  this spec predicted.** `diff_ir`'s signature is unchanged; instead `PublishBundle` gained
  `emitted: Emitted | None` — `Emitted.of(directory, names)` digests the generated files, sorted, and
  `mendel upgrade` now prints *"the generated pipeline differs: nextflow.config"*. So the verdict comes
  from bytes rather than from a field list, which is the right mechanism and not the one predicted.

  Its docstring makes an argument that **this spec's premise removes**:

  > Comparing bytes is the right mechanism, but **do not reconstruct the past — record it.**
  > Re-emitting the bundle's own IR needs the registry as it was, and a contract removed from the
  > registry is one of the two cases upgrade exists to report.

  That limitation is exactly what a self-contained `pipeline.yml` lifts: emission no longer needs the
  registry, so re-emitting a removed contract's pipeline does not die on a `KeyError` — the frozen
  values are in the file. **Both mechanisms then hold and neither is redundant.** `emitted:` proves
  *these bytes are what was published*; self-containment proves *and you can regenerate them*. A
  recipient gets verification and reproduction; today they get only the first, which `Emitted`'s
  docstring rightly calls a property that "did not exist at all".

  `emitted:` therefore becomes a section of `pipeline.yml` rather than a sibling artifact, and it
  covers the generated files only — never the copied `modules/` tree, which is vendored rather than
  emitted, per `Emitted`'s own rule.

  Root D's edge comparison (`_edge_changes`) stays as it is. Re-targeting `diff_ir` to `Pipeline` is
  still the eventual shape, and root D's tests remain the acceptance criterion for that swap.

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
- **A16 — closed by 1.9, and the sequencing advice paid off.** This spec said it did not depend on A16
  being fixed but that the plan should sequence after it, "since replay is the code that would have to
  change twice". It was fixed: `chosen` is no longer one loosely-typed field but three — `ParamValue`,
  `ContractId`, `EdgeRef` — on three variants discriminated by `kind`. Replay's `_chosen()` and
  `_still_applies()` survive unchanged, so §7 holds as written. The consequence for this spec is
  schema-shaped rather than behavioural: `decisions[]` carries `kind`, and the totality test names three
  types where it named one.
## Verification

Root I applies. Each probe added, watched failing, reverted.

| probe | expected |
|---|---|
| a setting with `via:` removed | refused at load, `MD0200`, naming the setting |
| `seq_platform: "illumina'; println 'X'; //"` | refused at load, `MD0201`. **Root C's own attack, on the new surface** |
| `template: "--flag fixed"` with no `{value}` | refused, `MD0204` |
| an override for a step that re-resolution does not produce | refused, `MD0203` — **not warned, not dropped** |
| an override whose candidate set moved | re-asked and reported `STALE`; **not** refused, and **not** silent as it is today |
| a setting answered by an override | absent from `needs_review()`, present in `overrides()`, still tier 4 |
| `upgrade` replaying an override | the recorded `reason` emitted **verbatim** — byte-identical `main.nf`, federation §4.1 |
| `mendel upgrade --out` pointed at the input's own directory | refused — the existing never-overwrite test, with a second subject |
| `via: meta` on `single_end` while `paired` is also measured | refused, `MD0208` |
| a `Pipeline` hand-built with `process: ""` | refused by `tests/test_construction.py` |
| a `Pipeline` field added with no `field_serializer` on a `frozenset` | refused at build, `MD0206` |
| `via: directive` naming `cpuz` | refused, `MD0209` |
| `version: 2` in a `pipeline.yml` | refused, `MD0207` |
| **a step carrying two `key: args` settings, with the name-sort reverted** | **byte-identity must fail** |
| `key: when` on any setting | refused, `MD0205` — a step's existence is resolution's call |
| `key: prefix` on `star/genomegenerate`, whose source has no `task.ext.prefix` | refused, `MD0108` |
| the shipped registry, built then re-emitted from its own `pipeline.yml` | **byte-identical `main.nf` and `nextflow.config`** |
| `mendel emit` with no `--registry` and no network, `modules/` present | **succeeds** |
| `mendel emit` on a `pipeline.yml` with `modules/` deleted | refused, `MD0210` — never a `main.nf` that cannot run |
| `pipeline.yml` edited, then run without re-emitting | refused, `MD0213` — **the run and the artifact must not diverge silently** |
| one byte changed in `main.nf` by hand | refused, `MD0214`, and the fix names `pipeline.yml` rather than forbidding the edit |
| `emitted.from_digest` computed with `emitted:` included | fails to round-trip — the exclusion is load-bearing, as `review_level`'s is |
| the emitted `nextflow.config`, against a golden file | **byte-identical** — digests catch *changed*, only a golden catches *changed to something wrong* |
| a measurement with no `meta_key` (`read_length`) | **still routes nothing, and is not flagged** |
| a field added to `PipelineIR` or `DecisionRecord` with no home in `Pipeline` | the totality test fails, naming the field |
| a `Registry` or `ModuleContract` field added to `Pipeline` | refused — `registry.py`'s mapping premise must hold |
| any `frozenset`-typed field on `Pipeline` | refused — `digest_of` is not stable over one |
| a hand-edited `pipeline.yml` with a bad setting, run through `mendel emit` | refused — a load check fires on **every** verb, not only `build` |
| `upgrade --dry-run` on a `pipeline.yml` built before `Param` gained `via` | reports drift on `star/align` and `hisat2/align` only — **expected, not a bug** |
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

And `MD0204` catches a template that ignores `{value}`; *nothing* catches a template whose flag is
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
- `comeni_core/egress.py` — door 4's payload becomes `Pipeline`, carrying 1.9's `Emitted`/`EmittedFile`
  plus the new `from_digest`; `Displacement` and the three decision variants get homes; `PublishBundle` retires, and the
  eight docstrings that cite it by name are rewritten rather than orphaned.
- `comeni_core/marks.py` — the `NfTemplate` kind and its validator.
- `mendel_resolver/resolve.py` — an override keeps the displaced tier and sets `source: human`.
- `mendel_resolver/replay.py` — **extended, not written.** `ReplayingResolver` already prefers
  `human_override` and tracks `replayed`/`fresh`; it gains a reported `stale` list where
  `_still_applies` returns `False`, and the post-resolution orphan sweep that no resolver hook can
  perform. `_chosen()` and the verbatim-`reason` rule stay exactly as they are.
- `mendel_compiler/emit.py` — `emit(pipeline)`; `ext.args` composition and double-quoting;
  `via: directive` and `via: meta` emission.
- `mendel_compiler/conformance.py` — `where` replaces `contract_id`; `MD0108`, `MD0200`–`MD0214`;
  and `M0100`–`M0107` renamed to `MD0100`–`MD0107`, which also touches `tests/test_conformance.py`
  (34 occurrences), `tests/test_spine_contracts.py`, `tests/test_conformance_cli.py`,
  `tests/test_modulespec.py`, `mendel_compiler/cli.py`, `CLAUDE.md`, `CHANGELOG.md` and
  `docs/design/conformance.md`. **`docs/internal/journal/`, `docs/internal/audits/` and the
  2026-08-05 plan are not rewritten** — append-only, correct on their date.
  `EXPLANATIONS` retires into `diagnostics.yml`; `Diagnostic` validates `code` against it.
- **New:** `comeni_core/diagnostics.yml` — the code registry, in `comeni-core` because the forge and
  the API will emit codes too. Shipped as package data so `mendel explain` works from an installed
  wheel; packaging entry required.
- **New:** `tools/generate_diagnostics_doc.py` — renders the `cli.md` table; `--check` in **both**
  `make check` (PRs) and `.github/workflows/nightly.yml` (`main`), mirroring `tools/generate_types.py`.
  No Action commits anything.
- `mendel_compiler/cli.py` — `emit`, `verify`, `upgrade` reworked; `build` round-trips. **And
  `mendel profile`, which the first draft of this radius missed**: it shares `build`'s emitter path,
  so it moves with the signature. It writes `pipeline.yml` *and* `profile.yml` — two files, correctly,
  because `profile.yml` is an instruction sheet for the laboratory rather than a description of the
  pipeline. "One artifact" is a claim about what describes the pipeline, not a cap on output files.
- `mendel_compiler/` — the legal Nextflow directive names, as code, carrying the Nextflow version
  they were read against. Not registry data; see `MD0209`. **Open question for the plan:** whether
  these belong in `diagnostics.yml`'s neighbourhood as compiler data rather than in a Python
  literal, now that §10 establishes the pattern.
- `registry/` — `via:`, `key:` and `template:` on both `seq_platform` params; one real `key: args`
  setting on the spine for the counts assertion.
- **Public documentation, which the first draft of this radius omitted entirely.**
  `docs/reference/cli.md` — sixteen new codes into the diagnostics table, the `M0100`→`MD0100`
  rename across the existing eight, a line noting the prefix arrived 2026-08-07, and `MD0100`'s row
  corrected: it cites `pipeline.ir.json`, which retires. `docs/reference/goal-schema.md` keeps its
  meaning (`Goal` is unchanged) but gains a line on `goal:` being inert to `emit`. A new
  `docs/reference/pipeline-schema.md` alongside the other five schema references, because
  `pipeline.yml` is now the file a stranger is most likely to open. `docs/README.md`'s index and
  `ARCHITECTURE.md`'s five stages both describe the four-route settings surface this supersedes.
- **Tests, and one of them comes first.** A golden `tests/golden/spine/nextflow.config` is a
  **prerequisite commit.** 1.9 gave that file an injection guard (A27) and digest comparison (A28), but
  still no golden — and it is where this mechanism emits. Then: `tests/golden/spine/main.nf` moves; `tests/test_egress.py` is edited for the new
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
pinning those two, and `upgrade --dry-run` will correctly report drift on a file built before this
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

## Before the plan is written

**This spec merges after Plan 1.9, and Plan 1.10 is written after that** — decided 2026-08-09. Not a
formality: `CLAUDE.md` records that every plan written ahead of its types has needed correction during
execution, and names the damage. Plans 2 and 3 *"predate the types they reference"*. The measurements
plan predicted a YAML row syntax that does not parse, a producer pin that makes the spine unbuildable,
a `mendel profile` whose `want` cannot route, and a `.pyi` that would have hidden three types from
every type checker — four things, all written in good faith, none of which existed. **Writing Plan 1.10
before 1.9 lands would repeat that exactly**, because 1.9 is rewriting the code this spec cites.

So, in order, once 1.9 is on `main`:

1. **Rebase this branch.** It is based on `e9cab07` and touches three files. `CLAUDE.md` and
   `docs/internal/README.md` will conflict — 1.9 marks roots closed and moves statuses in both — and
   the conflicts are table rows. The spec file itself should not conflict at all.
2. **Re-verify every citation and move the header's commit.** The header says *verified against
   `e9cab07`*, and the precedence section says citations will drift. Both stay honest only if someone
   re-reads them. The ones most likely to have moved:
   - `diff_ir` — root D rewrites it, and §2 and the root-D note both depend on its shape.
   - `Diagnostic` — root F is *"a guard calls its subject"*, which may already have renamed
     `contract_id`. If it has, §9's `where:` is a smaller change than described, or already done.
   - `marks.py` — root C adds the `Mark` enum entries this spec extends. `NfTemplate` must join
     what root C built, not sit beside it.
   - `replay.py`, `resolve.py`, `emit.py`, `conformance.py` — cited throughout.
   - The `frozenset` and `Line`/`Text` rules — root C may already enforce what §5 and §10 ask for.
3. **Re-run the two experiments.** The `cpuz` directive check (`MD0209`) was run on Nextflow 25.10.4;
   confirm the toolchain has not moved. And re-count `params` across contracts — §"The problem" claims
   the whole declared-param surface is two dead entries, and 1.9 touches contracts.
4. **Then write the plan**, against what is there.

**What must not happen** is the spec being treated as verified because it says so. The date and commit
in the header are a claim about a moment, and that moment will have passed.

## What this spec does not cover

- **Where in `mendel-compiler` the directive-name list lives, and how it records the Nextflow
  version it was read against.** That it is code rather than registry data is decided (`MD0209`); the
  module and shape are a plan question.
- **An Action that regenerates `cli.md` on push to `main` was considered and rejected.** It was
  proposed on 2026-08-09 and the reasoning against is worth keeping, because the idea will recur.

  `--check` on a pull request and auto-commit on `main` solve the same problem at different times, and
  the earlier time is strictly better: **main cannot drift if drift cannot merge.** The `--check`
  pattern already exists (`make types` inside `make check`, which CI runs on every PR), so the
  protection is in place before any Action would fire.

  What auto-committing adds is cost. It needs push rights to `main`, which is a protected branch, so
  the bot needs a bypass — and a bypass exists forever, for everything, not just for this. It puts
  bot commits in the history of a public repository. It can race with a concurrent push. And the real
  objection: **it makes `main` self-healing, so nobody ever sees the drift.** Someone edits the
  generated table by hand, the bot silently reverts them, and they learn nothing about why the file is
  generated. A failing check teaches; a silent fix does not.

  The genuine gap it would close is drift arriving by a route that skips PR CI — a direct push, or a
  merge that bypassed checks. **Decided 2026-08-09: cover it with a check, not a commit.** Two places,
  both read-only:

  - `make check` → `--check` on every pull request, so drift cannot merge. This is the existing
    `make types` pattern and needs no new machinery.
  - `.github/workflows/nightly.yml` → the same `--check` on `main`, so drift that arrived by another
    route is reported within a day. That workflow already exists and already runs the stub gate.

  Neither needs write permission, and a failure names the file and the command that fixes it.
- ~~Whether `ExtKey` should carry `args2` and `args3`.~~ **Settled 2026-08-07: keep them.** An unused
  enum value costs nothing and a missing one costs a `version:` bump for every archived file, while
  `MD0108` refuses a contract naming a key its module does not read — so a wrong inclusion fails loudly
  at build and a wrong omission is a migration. Still the one judgement in this spec resting on
  knowledge of nf-core rather than on code here, and §4 says so at the enum.
- **Whether the resolver's and loaders' errors become `MD03xx` diagnostics** — [#18](https://github.com/comeni-project/Comeni-Labs/issues/18).
  **Deferred to the next audit round on 2026-08-09**, not dropped: 41 raise sites, of which 32 are bare `ValueError`, and
  deciding which are user-facing is judgement per site. Band `MD0300`–`MD0399` is reserved and the item
  is carried in
  [`../audits/2026-08-07-round-two-brief.md`](../audits/2026-08-07-round-two-brief.md) under *Carried
  forward*, because a deferral recorded only in a commit message is a deferral lost.
- **Whether any real tool setting needs a space or a slash.** Assumed not, deliberately, and the
  assumption is stated in §5 with the cost of each class of counterexample. `MD0201` is instrumented to
  surface one if it exists. **The first genuine counterexample is a finding, not a bug report** — it
  tells us a boundary drawn on reasoning rather than evidence was drawn in the wrong place.
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

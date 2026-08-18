# Architecture

How Mendel turns a goal into a Nextflow pipeline, and why each part is shaped the way it is.

Written against the code as it stands, not against a plan. Every type name here exists; if
one has drifted, the code is right and this document is wrong.

For the product claim and the invariants those parts serve, read `CLAUDE.md` first. This
document is the *how*; that one is the *why it may not change*.

---

## 1. The five stages

```
   Goal ──route──▶ RoutePlan ──resolve──▶ PipelineIR ──materialise──▶ pipeline.yml
                                                                          │
                                                                        emit
                                                                          │
                                                                          ▼
                                                              main.nf + nextflow.config
                                                                          │
                                                                    run_gate ──▶ GateResult
```

| Stage | Input | Output | Lives in |
|---|---|---|---|
| load | layer directories | `Layers` | `mendel_resolver/layers.py` |
| route | `Goal`, `Registry`, `RuleTable` | `RoutePlan` | `mendel_resolver/router.py` |
| resolve | `RoutePlan` | `PipelineIR` | `mendel_resolver/resolve.py` |
| materialise | `PipelineIR`, `Registry`, `Vocabulary`, measurements | `Pipeline` | `comeni_core/artifact/pipeline.py` |
| emit | `Pipeline` | `str` | `mendel_compiler/emit.py` |
| gate | a pipeline directory | `GateResult` | `mendel_compiler/gates.py` |

**The stages and the packages are the same five things.** `comeni-core` is grouped by
lifecycle stage rather than by type kind, so a reader who has followed the table above already
knows which directory to open:

| | holds |
|---|---|
| `comeni_core/declared/` | what a registry layer holds — contracts, measurements, vocabularies, roles, and the stacking every kind shares |
| `comeni_core/goal/` | what was asked for, and what the data measurably looks like |
| `comeni_core/plan/` | what was decided — the IR, each ambiguity's record, the tier ladder |
| `comeni_core/artifact/` | what is shipped — `pipeline.yml`, its digests, and the doors it crosses |
| `comeni_core/spell/` | how a value is written down — marked strings, routes, directives |

`yaml_strict.py` and `diagnostics.py` sit above those five because every one of them uses both.

`tests/test_architecture.py` asserts every path this document names exists — prose that names
a path is prose that goes stale, which is what `CLAUDE.md`'s two stale counts were (A71, A72)
and what `registry.yml:kinds` was until Plan 1.15.

**Materialisation is why `emit` takes one argument.** Everything the emitter used to look up —
process names, include paths, entry-channel expressions, the measured facts that ride in `meta`
— is copied onto the `Pipeline`. So `mendel emit build/pipeline.yml` regenerates the Nextflow
with no registry and no network, which is what lets a laboratory archive a validated pipeline
and rebuild it years later: `modules/` is inert vendored source, while the registry is the part
that resolves differently as it changes.

`build` writes `pipeline.yml`, parses it back, and emits from **the copy it read**. One extra
parse; in exchange the round trip is load-bearing on every build rather than asserted once, and
a field that does not survive YAML is a refused build (`MD0206`). That bug class is not
hypothetical — `ResolvedValue._drop_computed` exists because the IR did not round-trip at all,
and in its own words *"nothing noticed, because nothing read an IR back until now."*

**`cli.py` is the only thing that touches disk.** Everything else takes objects and returns
objects, which is what makes the golden-file tests possible at all: a stage you can only
exercise through the filesystem is a stage whose output you compare by hand.

`mendel build` reads a goal file; `mendel profile` constructs the same `Goal` in memory and
runs the identical remaining path. A test asserts their `main.nf` are byte-identical, because
"sugar" is a claim that decays into a second implementation unless something checks.

---

## 2. Declared data

Every kind in `DeclaredKind` is files under a **layer directory**, all of them stacked by
repeating `--registry`. Later layers win.

**A file says what it is; the directory says nothing** (comeni-registry#1). Each carries a
`declares:` line, and a vocabulary or measurement carries an `id:` beside it, so the loader
globs the layer and buckets by content rather than by path. `MD0010`, `MD0011` and `MD0012`
are the refusals that replace position.

**So the layout is a convention, free to serve a reader.** The public registry groups a tool's
files together, which is the whole point — working on STAR used to mean opening three trees:

```
<layer>/
├─ registry.yml                          the layer's account of itself
├─ roles.yml                             the roles a contract may fill
├─ types/<type_id>.yml                   states a type may carry, and how it enters a pipeline
├─ measurements/<id>.yml                 kind, allowed values, bounds, unit, citation
├─ rules/<name>.rule.yml                 decision tables: measured data → a value or a module
└─ tools/nf-core/star/                   one tool, its contracts and the types it produces
   ├─ align.contract.yml                 what a module consumes, produces and is called with
   ├─ genomegenerate.contract.yml
   └─ genome.index.star.type.yml
```

Nothing in the loader requires that shape. A layer that put every file at its root would load
identically; a layer digest pins which bytes were at which path, so moving a file moves the
digest, and that is the only thing the arrangement decides.

They are not independent, and the dependency runs one way:

```
measurements ──▶ vocabulary ──▶ registry ──▶ rules
```

A measurement derives a `measurement.<id>` type; contracts validate against the vocabulary
that includes those; rules validate against all three. Loading them out of order does not
fail where the mistake is — it fails inside whichever contract happened to mention a
`measurement.*` type. `mendel_resolver.layers.load()` exists so the order is a fact rather
than something each caller remembers.

### Stacking is one mechanism

`comeni_core.layered.stack(layers, kind)` loads one kind across a stack. A `Kind` declares
only what genuinely differs — how a file parses, what keys an entry, whether a higher layer
replaces (`Policy.REPLACE`), extends (`MERGE`, opt-in and spelled in the file as `add_states`
or `add_values`) or deletes a whole group (`DELETE_GROUP`, which is contract shadowing by
module key). Everything else — recursion, `*.yml` **and** `*.yaml`, a missing subdirectory,
stack order, and recording what displaced what — belongs to `stack()` and is therefore
identical for every kind.

It was four hand-written loaders before Plan 1.9, disagreeing on six axes: two of them
recorded nothing at all, three globbed one level, all four ignored `.yaml`, and displacement
was keyed on a layer *name*. Every finding in audit root B is a cell in that table.

A `Layer` is a value: `path`, `name` (from `registry.yml`, for rendering) and `index`
(**identity** — names collide). Every displacement, of any kind, is one `Displacement`
record: it reaches `PipelineIR.displaced`, the published `pipeline.yml` (`registry.displaced`),
and the `OVERLAY` block of `mendel build`.

### Vocabularies are closed

`Vocabulary.validate(type_id, states)` raises `UnknownStateError` for any state the type does
not declare. A contract naming an undeclared state fails to load. This is what makes routing
provable rather than plausible: `alignment.bam[coordinate_sorted]` means one thing across the
whole registry, and a typo is an error at load rather than a module that silently never
matches.

`entry_channel` lives here too, so `mendel-compiler` has no built-in idea what a FASTQ is —
required if the same compiler is to emit calls for a pegi3s image or an in-house process.

### Measurements are declarations, and also types

`Measurement` declares `kind` (`integer`, `number`, `boolean`, `enum`), allowed `values`,
`minimum`/`maximum`, `unit`, `cite`, `edam`, and `deprecated`/`replaced_by`.

**There is deliberately no `string` kind.** A free-text measurement is exactly the hole
`tests/test_egress.py` exists to close: `organism: "patient 4471023's tumour"` is a perfectly
valid string. A categorical declares its values instead, which also lets a rule over it be
checked for exhaustiveness.

`Vocabulary.with_measurements()` derives a stateless `measurement.<id>` type per declaration.
That one line is what makes profiling free — see §6.

### Contracts

`ModuleContract` declares `consumes: list[InputPort]`, `produces: list[OutputPort]`,
`params`, `priority`, `container`, `nf_inputs`, and `provenance`. `nf-core`'s `meta.yml` is a
scaffold, not a contract: it types both `samtools/sort`'s output and `star/align`'s
`bam_unsorted` as `type: file, *.bam`, so "sorted" exists only in the English description.
The semantic `state` overlay is the missing ~40%, and it is what routing depends on.

### Rule tables

Two layers, both in `rules/`. The **premise layer** builds the facts a rule may read; the
**decision layer** maps those facts to effects on a role.

```yaml
derives:                                        # the premise layer
  - fact: strandedness                          # a fallback: fills a gap, never overwrites
    kind: enum
    rows:
      - {when: {strandedness: absent}, then: reverse, cite: "Wang et al. 2012"}
  - fact: sjdb_overhang                         # arithmetic, without an expression language
    kind: integer
    source: read_length
    transform: [{op: subtract, by: 1}]
    cite: "STAR manual 2.2.2"

decisions:                                      # the decision layer
  - decides: {effect: implementation, of: alignment}
    cite: "Dobin et al. 2013, doi:10.1093/bioinformatics/bts635"
    rows:
      - {when: {read_length: ">= 70"}, then: nf-core/star/align@1.11.0, cite: "Dobin 2013"}
      - {when: {read_length: "< 70"},  then: nf-core/hisat2/align@2.2.2, cite: "Kim 2019"}
```

Grouped rather than flat so a reviewer reads the justification once and then reads the
branches — and so a *missing* branch is visible, which flat rules actively hide.

A derivation does one of three things and says which: fill a gap from `rows`, reduce a cohort
with an `aggregate`, or compute a fact with a `transform` — a chain of **named unary operations
with a literal operand**, left to right. No parser, no precedence, and no way to name a second
fact, which is what keeps arithmetic from becoming a solver (issue #39).

**A decision names a role, never a type and never a bare parameter name.** Three effects:
`presence` (whether the step exists), `implementation` (which contract fills it), and `param`
(a named setting on it). The old target admitted `{param: X}` and `{producer_of: T}`, so a rule
about duplicate handling and a rule about which aligner to use both had to key on
`alignment.bam` — and `Policy.REPLACE` settled that collision by deleting one of them, silently,
at exit 0. Keying on `(effect, role[, name])` is what makes them different keys. One decision
may carry several targets, because "where the annotation is used" is one choice with two flags.

A row's **tier is read off its own text**: it earns tier 3 only by testing a premise
positively, so `when: {}` and `when: {x: absent}` exit at tier 2 and need a citation rather than
a sentence.

**Every table is validated at load**, against the registry, the vocabulary, the roles and the
measurements — twelve diagnostics, `MD0300`–`MD0313`. A role nothing fills, a param some filler
of the role does not declare, two decisions sharing a key, a `when` naming a premise nothing
supplies, a `then` outside its parameter's declared domain, rows that do not cover their
premise's domain: each refuses to load, and the error says what the author *can* write.

This is the load-bearing part. `subject` used to be an unvalidated free string, and two of
the five rules shipped in the example layer had never once executed. Nothing said so, and a
constant named `KNOWN_DEAD_RULES` recorded them instead. Validation replaced both.

A layer replaces a decision **block**, not a row — a reviewer should read one block and see
the entire effective decision. `derives:` and `decisions:` share one key space, namespaced
(`derive:<fact>`, `presence:<role>`, `param:<role>:<name>`), so an overlay replacing a
derivation leaves the decision beside it untouched.

---

## 3. Routing

Backward chaining from wanted types to held ones, inserting producers. Three rules make it
terminate and stay honest.

**A contract cannot satisfy its own input.** `SAMTOOLS_SORT` consumes `alignment.bam` and
produces `alignment.bam`, so without the `visiting` exclusion it selects itself forever.

**Smallest surplus wins.** `Registry.producers_of` matches on superset, which is right for a
requirement — asking for `coordinate_sorted` should accept a producer that also indexes — but
when nothing is required *every* producer of the type matches and the aligner and the sorter
become indistinguishable. Preferring the fewest states beyond those asked for keeps "get me a
BAM" from silently meaning "get me a sorted BAM".

**A tie is ambiguity.** Contracts equal on surplus and priority produce an `Ambiguity`, a
`DecisionRecord`, and a tier-4 selection. Never a coin flip.

### A port may accept alternatives

`InputPort` declares either `type_id` + `state_required`, or an ordered `accepts` list of
`Alternative`s — one level of disjunctive normal form, so "a coordinate-sorted BAM, or failing
that a CRAM" is expressible. Declaring both, or neither, is a load error.

Order is first-match-wins in the router and again when wiring edges, because alternative order
is the author saying which kind of input they would rather have. Full boolean logic would
express more and cost the thing the product sells: today "why is `SAMTOOLS_SORT` here?"
answers in a sentence, and under a general constraint language it becomes a solver trace.

`prefer` ranks sources *within* the alternative that matched. It never promotes a later
alternative over an earlier one and never causes an insertion.

---

## 4. The four tiers, for parameters and for modules

| Tier | Fires when | Review |
|---|---|---|
| 1 structural | no choice exists — inputs force it | `none` |
| 2 convention | a documented default exists | `none` |
| 3 data-profiled | a declared rule matched measured data | `advisory` |
| 4 ambiguous | no rule matched | `required` |

Parameters exit through `_resolve_param`: a goal override is tier 1, a matching rule row is
tier 3, a contract default is tier 2, and anything left asks the `AmbiguityResolver`, records
a `DecisionRecord`, and exits at tier 4.

**Module choices carry a tier too**, in `IRNode.selection`. Until that field existed, spec
§6.1's claim that every module choice exits at exactly one tier was not true of the code: a
module selected because it was the sole producer was indistinguishable from one selected by
priority. `router._choose` assigns it:

- **structural** — one candidate, or one with strictly smaller surplus than the rest
- **data-profiled** — a rule pinned it, and `selection.reason` carries the citation
- **convention** — equal on surplus, `priority` broke it
- **ambiguous** — nothing distinguished them

A pin binds only where the pinned contract is genuinely a candidate for the requested
*states*. featureCounts asks for `alignment.bam[coordinate_sorted]`, whose only producer is
the sorter; the aligner rule is about the sorter's own BAM input, one level down, where the
aligners actually compete. Treating a pin as binding everywhere makes the spine unbuildable.
`UnroutablePinError` is for the case that *is* a contradiction: the pin was selected and its
own inputs cannot be reached.

`PipelineIR.needs_review()` returns both flagged parameters and flagged module selections. A
record nobody is shown is not a flag — for a while that method scanned only node params, so
the CLI reported "0 requiring review" while an aligner had been chosen alphabetically.

---

## 4a. One question, two behaviours

The forge and the build path both ask a reviewer questions, and until 2026-08-18 each had its
own vocabulary for doing so. `comeni_core/review/` is the shared one.

```
Question                    base — subject, what, why_open, candidates, closed, evidence
  ├── Hole                  forge. Held by Scaffold, answered by HoleFiller
  └── Ambiguity             build. Held by the resolver, answered by AmbiguityResolver
        ├── ParamAsked
        ├── ProducerAsked
        └── SourceAsked

Answer                      base — value, by, how, why
  ├── FilledValue           forge
  └── Resolution            build  (adds `confidence`)
```

`ValueSource` is the one provenance vocabulary — `RESOLVER / GOAL / HUMAN / MODEL / MEASURED /
DERIVED`. The forge's `Filler` is gone: `HAND` was `HUMAN` under a second name.

**The base classes are inert, and that is the load-bearing part.** A hole *blocks* — 
`Scaffold.is_complete()` gates `contract_from`, so the forge structurally cannot emit an invalid
declared file. An ambiguity *ships flagged* — the pipeline is built and runnable, marked tier 4.
That difference is **not** a field and **not** an overridden method. It lives in the container
and in the port, and the cleanest statement of it is the two signatures:

```python
class HoleFiller(Protocol):
    def fill(self, hole: Hole, observation: Observation) -> FilledValue | None: ...

class AmbiguityResolver(Protocol):
    def resolve(self, ambiguity: Ambiguity) -> Resolution: ...
```

**One may return `None`. The other may not.** A filler that always answers is a filler that
invents; `FlagOnlyResolver` must always answer, because that is what keeps a pipeline runnable
with no model and makes the flagged count an honest measure of rule coverage.

Putting `blocks: bool` — or a `blocks()` method — on `Question` would trade a structural
guarantee for a runtime check on a value, which is the mistake this repository records about
invariant 1. `notes/specs/2026-08-18-the-shared-question.md` §3.1 is the argument; a test asserts
the base carries no behaviour beyond `legal()`.

**Two shapes of candidate, deliberately.** The forge offers `Candidate(value, note)` so a
reviewer sees where an option is declared; the build path narrows `candidates` to bare declared
ids, because door 2 types them as `CandidateRef` and A129 records that payload accepting only one
of three `*Asked` types until *values* were checked rather than names. `Question.legal()` reads
both.

**What the door gained.** `AmbiguityRequest` carries `what`, `why_open`, `closed` and `evidence`
now. Not padding: the forge measured a local model at 69% without them and 88% with, and two of
the three fixes behind that were *the question never said what it was about* and *the evidence
was not readable*.

---

## 5. Ports versus channels

A contract port is *semantic*: a typed thing the module consumes. A process input is
*plumbing*: one channel in the call signature. They do not correspond, and assuming they did
made the first generated spine uncallable.

| Process | Contract ports | Process channels |
|---|---|---|
| `FASTQC` | 1 | 1 |
| `TRIMGALORE` | 1 | 1 |
| `MULTIQC` | 1 | 1 |
| `SAMTOOLS_INDEX` | 1 | 1 |
| `STAR_GENOMEGENERATE` | 1 | **2** |
| `HISAT2_BUILD` | 1 | **3** |
| `SAMTOOLS_SORT` | 1 | **3** |
| `STAR_ALIGN` | 2 | **4** |
| `HISAT2_ALIGN` | 2 | **4** |
| `SUBREAD_FEATURECOUNTS` | **2** | **1** |

Five of ten match. `ModuleContract.nf_inputs` declares the real signature, and `NfInput.empty`
carries the **tuple width** — Nextflow matches arity, and a 2-tuple handed to a slot declared
`tuple val(meta), path(fasta), path(fai)` dies with "Path value cannot be null".

Declared rather than parsed out of `main.nf`, for the same reason `entry_channel` lives in the
vocabulary: it has to work for a module the compiler has never seen.

---

## 5a. Where a resolved value goes

A resolved value has to reach the tool, and for a plan and a half one did not: it became a
`params.<node>_<name>` line in the emitted workflow that no module reads. The resolver ran,
flagged tier 4, printed `REVIEW`, and the pipeline behaved identically whatever anyone
answered. That was issue #10.

Every `Param` now declares the **route** that carries it, and a setting without one cannot
load (`MD0200`). Three destinations, because there are three places a Nextflow module takes
configuration from:

| `via:` | emitted as | `key:` |
|---|---|---|
| `ext` | `process { withName: X { ext.<key> = … } }` | `args`, `args2`, `args3`, `prefix` |
| `meta` | `.map { meta, files -> [ meta + [k: v], files ] }` on the entry channel | — |
| `directive` | `process { withName: X { cpus = 4 } }` | — |

`ext` is a *keyspace* rather than one destination: `task.ext.prefix` appears in 8 of the 10
vendored modules and `task.ext.when` in all 10. `when` is deliberately not a legal key — it
switches a process off entirely, which would be a second routing mechanism competing with
resolution, and whether a step exists is decided by resolving the goal.

Three properties are checked rather than assumed:

- A `template` on an `args` key must mention `{value}` (`MD0204`). One that forgets renders
  real flags and discards the resolved value, which is *harder* to spot than an honest no-op.
- A `via: directive` name must be one Nextflow accepts (`MD0209`). Measured, not assumed: a
  config carrying `withName: FOO { cpuz = 4 }` runs to exit 0 with no warning on Nextflow
  25.10.4, so an unchecked directive name reinstalls the exact defect `via:` removed.
- A route must exist in the module (`MD0108`). `via: ext, key: prefix` on a module whose
  script never mentions `task.ext.prefix` is a checkable lie — three of the ten vendored
  modules ignore it, so the check has real negatives.

**A value is validated, not escaped.** `{value}` substitution accepts letters, digits and
`_ . : + -`, numbers and booleans, and nothing else (`MD0201`). Escaping-for-context is where
injection bugs live, and a value that cannot contain a quote cannot close one. The class is
narrow on a stated assumption — that almost no tool setting needs a space or a slash — and
`MD0201`'s message asks for the counterexample, because loosening it later is
backward-compatible and tightening it is not.

**Measured facts do not go through `via:` at all.** `strandedness: reverse` rides in `meta`,
and featureCounts contains its own translation to `-s 2`. A tier-3 rule producing `-s 2`
directly was deleted in Plan 1.5: that is the module's encoding of a fact, not a decision, and
duplicating it put the same claim in two places that could disagree.

---

## 6. Profiling is a build

A measurement is a type, so `mendel profile --have fastq.reads` is
`mendel build --want measurement.*`. The router needs no profiling code; the emitter needs
none; the decision records are the same records.

Two rules keep it honest.

**The profile it resolves against is empty.** A build resolves tier-3 parameters against a
profile, and a profiling build is a build — resolving one against a profile would need a
profile to profile with. Profiling contracts therefore exit at tiers 1, 2 and 4 only, and the
regress stops here rather than one recursion later.

**`want` is what the registry can actually reach.** Declaring a measurement is how a
laboratory *starts*, before any tool for it exists, so wanting every declared measurement
would make the verb unroutable for exactly the people adopting it. What cannot be measured is
named on stderr. A registry that can measure nothing at all is an error, not an empty pipeline
that looks like success.

`profile.yml` records, per measurement, `{value, source, by}` — `source: measured` and the
contract that will produce it. **`value` is `null`**: the pipeline has been emitted, not run.
The laboratory runs it and fills the values in, and the file is the same shape a goal accepts
back, so the round trip is one test rather than a hope. Reporting a number Mendel has never
looked at is precisely what invariant 15 exists to prevent.

A hand-written profile records no tool, and that absence *is* the provenance:
`ValueSource.GOAL` means a person asserted it. `ValueSource.MEASURED` is what a `sealed`
policy will check a tier-3 decision against, once Plan 2 builds `ProfilePolicy` — issue #2.

---

## 7. The guards

Three AST-and-reflection tests, each of which exists because the property it asserts was
broken by someone who meant well.

| Guard | Asserts | Broken by |
|---|---|---|
| `tests/test_purity.py` | the pure packages import no web framework, HTTP client or LLM library — closed allowlist for `comeni-core` and `mendel-resolver`, banlist including stdlib transports and dynamic imports for `mendel-compiler` | four lines: `import urllib.request`, `importlib.import_module("httpx")`, `__import__("openai")` |
| `tests/test_egress.py` | four doors, one payload type each, no `Any`, no mapping, no bare `str`, `extra="forbid"`, free text only in the seven named fields | a `user_note: str`, which carried no marker to catch and no `Any` to forbid; and roots taken from `vars(egress)` rather than `DOORS`, which walked three doors out of four |
| `tests/test_construction.py` | a `DataProfile` is built in exactly one place, and that place validates it | — new; watched failing by adding `DataProfile()` to `router.py` |

The third exists because validation *moved*. `DataProfile` used to hold four hardcoded fields,
so `extra="forbid"` alone refused `sample_name`. Measurements are declared data now, so the
model cannot know what is declared, and the mapping shorthand is no longer a validation
boundary. `MeasurementRegistry.profile()` is the only validating constructor,
`test_construction.py` enforces that nothing else builds one, and `mendel build` re-routes
every goal's profile through it. Without that last step a goal file carrying
`profile: {sample_name: SILVA_biopsy_01}` validates, resolves and reaches
`pipeline.yml` — the 2026-08-03 audit's `constraints` hole, re-opened one field over.

**A guard that has not been watched failing has proven one thing, not the general property.**
Three of three earlier guards had holes, all found that way.

`tests/test_generated_types.py` is a fourth of a different kind: `profile.pyi` is generated
from the measurement declarations, and `--check` in CI is what stops it rotting. A stale stub
costs autocomplete and never correctness — which is exactly why nobody would notice.

---

## 8. Determinism

Same `Goal` → byte-identical `.nf`. Tested three ways, because the obvious test does not bite:

- two builds in one process produce identical output;
- two builds under different `PYTHONHASHSEED` values produce identical output;
- a `frozenset` of four states serialises identically under three seeds.

The third is the one that catches things. Every state set the current spine produces has one
element, and a one-element set has no order to vary — so the CLI-level seed test stayed green
with the `IREdge.states` serialiser deleted. Anything new that serialises a set needs the same
`field_serializer` treatment.

---

## 9. Where Plan 2 plugs in

`mendel_resolver/ports.py` declares `AmbiguityResolver` as a `Protocol`; `FlagOnlyResolver` is
the shipped implementation, which picks the first candidate, flags it, and never guesses
cleverly. `mendel-ai` will implement the same protocol over LiteLLM. The dependency arrow
points `mendel-ai → mendel-resolver`, never the reverse, and `tests/test_purity.py` is what
holds it.

This plan changed none of that seam. Runtime AI stays confined to three declared points —
goal extraction, tier-4 resolution, compiler repair — and tier 3 remains a pure lookup whose
miss demotes to tier 4 rather than reaching for a model.

---

## 10. The forge — where declared data comes from

Everything above reads the registry. **`mendel-forge` is how a registry gets written**, and it
is the first impure package: it is not scanned by `tests/test_purity.py`, it is listed in
`IMPURE_PACKAGES`, and `test_no_pure_package_imports_an_impure_one` holds the arrow pointing
`mendel-forge → the pure packages` and never back.

```
mendel-forge/
  observe.py     Excerpt, Fact, Observation — what a source proved, and where from
  scaffold.py    Filler, FilledValue, Candidate, Hole, Scaffold
  sources/       the Source protocol, and the nf-core adapter
  candidates.py  what a hole will accept, read off the layer stack
  assemble.py    Observation -> Scaffold, and Scaffold -> ModuleContract
  modulegen.py   a skeleton main.nf for a source that ships none
  verify.py      the five-rung ladder
  workspace.py   drafts on disk, outside every layer
  land.py        the one thing that writes to a registry
  ops.py         one typed function per verb — the only layer with logic
  ports.py       HoleFiller — the seam, NoFiller, and since Phase 2 ModelFiller
  filler.py      ModelFiller — a model behind that seam
  cli/  http/    two transports over ops.py, neither holding logic
```

### Phase 2 — a model behind the seam

`mendel_forge.filler.ModelFiller` implements `HoleFiller` over `mendel-ai`. It attempts
**candidate-bearing holes only**: those are the holes whose legal answers come off the layer
stack, so an answer is checkable, and `Hole.legal` refuses one that is not. A hole with no
candidates is free text and is **declined without being sent** — stronger than asking and
discarding, because no prose about it ever leaves. Issue #70 gates the other direction, and
`priority_because` is the one such value that would reach a registry.

Every answer is validated twice: `mendel_ai.choose_*` refuses a value the model was not
offered, and `hole.legal` refuses it again on the way in. The second is not redundancy — it is
the check a person's fill already goes through, so a model's answer meets one rule rather than
a second that can drift from it.

A model fill lands as an **answer**, not a proposal, carrying `Filler.MODEL` and the model id;
`assemble._drafted_by` writes that into `Provenance.drafted_by`, so a model-filled contract
lands with the model named in the file and **no artifact schema changed**. `forge show` prints
`(filler, by)` beside every value, so a reviewer sees which a model settled without opening
anything.

**The forge is not an egress door.** Invariant 14's doors track the prompt taint path — prompt,
goal, build, pipeline, publish — and the forge is offline authoring outside it, reading vendored
modules and registry files. `DOORS` and `tests/test_egress.py` did not change when Phase 2 wired
a model in. `notes/specs/2026-08-17-forge-phase-2.md` §1 is the argument.

### `mendel-ai` — model access

One primitive: `generate(instruction, shape, evidence)` validates a model's answer against a
declared Pydantic shape before any caller sees it, and returns `None` when it declines or will
not validate. `choose_one` and `choose_many` are helpers for the closed-choice case; two of them
because `roles` and `produces[].state` take several members from one closed set.

The boundary is not *the model may not speak* but **nothing it says is taken on trust** — the
same rule closed vocabularies and contract-versus-module checking already enforce. A drafted rule
has the rule validator; a `Goal` is a Pydantic model. A module's script body has no shape, which
is why `MF0005` refuses it.

The package holds **no Mendel domain types** — it speaks in strings and shapes its caller
declares, which is what lets the tier-4 ambiguity resolver reuse it unchanged in Plan 3. It is
impure and classified as such. `MA0001`–`MA0007` are its diagnostics.

### A scaffold is not a half-built contract

This is the decision everything else follows from. `ModuleContract` validates and forbids
extras, so a *partially valid* contract is unrepresentable — and it must stay that way, because
the moment one is constructible somebody persists one. So the forge never builds a contract it
cannot finish. It holds an `Observation` plus a list of `Hole`s, and calls `contract_from` only
when the last hole is filled; while any remains, that call raises `MF0004`.

The consequence is the property worth stating plainly: **the forge cannot emit an invalid
declared file.** It emits a valid one, or something that is honestly not one yet and says which
fields it is missing and why.

A `Hole` carries `what`, `why_open`, the `Candidate`s that are legal there, and the `Excerpt`s
bearing on it. The candidates are **invariant 7 moved earlier** — vocabularies are closed, so a
contract naming an undeclared state fails to load; a hole carrying its legal values turns that
load-time refusal into a fill-time one, and turns Phase 2's open prompt into a closed choice.

**What is a hole and what is derived was measured, not assumed** —
`notes/audits/2026-08-16-forge-derivability.md`, run against all twelve shipped contracts. Two
rows moved when measured: a contract's input port name is *not* the module's channel name (four
of twelve rename), and an output port name is one of up to nineteen emits.

### The five-rung ladder

`verify()` asks five questions, cheapest first, and stops at the first refusal so a reviewer
sees the cause rather than a wall of consequences.

| rung | asks | on failure |
|---|---|---|
| `COMPLETE` | are all the holes filled? | `MF0004`, refuses |
| `CONSTRUCTS` | does `ModuleContract` accept it? | `MF0007`, refuses |
| `LOADS` | does the layer stack declare every type, state and role? | the loader's own code, refuses |
| `CONFORMS` | does it agree with the module? | `MD0101`–`MD0106`, reused not twinned |
| `ROUTES` | can anything consume what it produces? | `MF0006`, **warns** |

**Four of the five are existing machinery pointed at a draft instead of a build.** A second
implementation of *"is this contract sound"* would disagree with the first one inside a plan.
Rung 4 calls `conformance.against`, which is `check`'s per-contract half made public for this.

Two weaknesses, stated rather than left to be found. **Rung 4 is a transcription check when the
module was forge-generated** — contract and module descend from one `Observation`, so agreement
proves the two code paths match, not that either is right; it is a real check only against a
vendored module, where the module is foreign ground truth. And **rung 5 warns**, because a
laboratory adding a tool before the goal that needs it is being reasonable.

### One operations layer, two transports

`ops.py` holds one typed function per verb, pydantic in and pydantic out. `cli/` renders those
results and `http/` serialises them; neither decides anything, and
`test_no_route_contains_a_branch` refuses an `if` in a route. `test_http.py` compares
`forge --json <verb>` against the HTTP body **directly**, so a transport that grows logic fails
rather than drifts. Plan 3's GUI calls the HTTP app rather than reimplementing a verb to display
it.

### Landing is the invariant-2 boundary

`land.py` is the only thing in the package that writes under a registry root, and
`tests/test_forge_write_boundary.py` is a static scan holding that over every other module. It
creates a branch, writes the files, and commits — refusing the default branch (`MF0100`), a
dirty tree (`MF0101`) and an incomplete draft (`MF0004`).

**It does not open a pull request.** Invariant 13 says self-hosted is not a degraded tier, so a
laboratory landing into a private local overlay must get the identical path to the one the
public registry gets; making GitHub the approval mechanism would break that for every lab that
never pushes anywhere. The branch *is* the approval queue.

### No model, by construction

`ports.py` declares `HoleFiller` and ships `NoFiller`, which declines every hole. **`--no-ai` is
not a flag in the forge — it is the only mode**, so there is nothing to leave accidentally on.
A filler returns the same `FilledValue` a human's `forge fill` produces, differing only in
`filler` and `by`, and `by` is copied verbatim into `Provenance.drafted_by` — a field every
contract has carried since the first one.

**Phase 2's first question is not an implementation question.** A forge model call sends tool
documentation to a provider, and invariant 14 says data leaves through *four* declared doors.
Read §10.3 of `notes/specs/2026-08-16-the-forge.md` before writing an adapter.

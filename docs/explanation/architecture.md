# Architecture

Comeni separates pipeline construction from execution. Mendel builds a saved pipeline
and emits Nextflow; Wiener launches it and projects execution events into run state.
The browser carries the pipeline bundle between the APIs and combines their views.

This page explains component ownership and the construction path. Use the
[contributing guide](../how-to/development/contribute.md) for setup and checks,
[the invariants](invariants.md) for design constraints, and
[the authoring protocol](authoring-protocol.md) for the conversation engine.

## Component ownership

| Component | Responsibility | Boundary |
|---|---|---|
| `comeni-core` | Shared declarations, schemas, intermediate representation and saved artifacts | Pure |
| `mendel-resolver` | Routing, decision tiers, rules and adapter ports | Pure |
| `mendel-compiler` | Nextflow emission, conformance and gates | Pure construction; CLI and gate adapters perform I/O |
| `mendel-authoring` | Protocol, interpreter, commands and draft projections | Pure |
| `wiener-core` | Run-state transitions and decisions from supplied events | Pure |
| `dag-core` | Graph layout shared by the canvases | Pure |
| `comeni-ai` | Provider transport and reusable model integration | I/O adapters |
| `mendel-ai` | Deprecated re-exports of `comeni-ai` | Compatibility only |
| `comeni-vendor` | Fetching module source and checking its pins | I/O adapters |
| `comeni-inspect` | Sample-inspection subprocesses | I/O adapters |
| `mendel-api` | Build sessions, drafts, jobs, settings and HTTP routes | Service and persistence |
| `wiener-api` | Artifact upload, run submission, workers and execution queries | Service and persistence |
| `frontend/` | Browser application and API integration | React, TypeScript and Vite |

Pure components keep calculation separate from network access. Guards provide partial
static and runtime coverage; they do not constitute a security sandbox. API clients in
`frontend/src/api/` are generated with `make client`.

See [package responsibilities](package-boundaries.md) for source groups, dependencies, consumers
and runtime owners, and [Mendel AI ownership](mendel-ai-ownership.md) for model call paths.

## Construction topics

The sections below cover declared data and layers, routing, decision tiers and
corrections, review questions, Nextflow wiring, profiling, guards, determinism, model
integration and registry authoring. Detailed sections are being reviewed against current
code; a source-path check establishes that a path exists, not that every behavior claim
is current.

## 1. Construction stages

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

`comeni-core` groups shared models by their role in the lifecycle:

| | holds |
|---|---|
| `comeni_core/declared/` | what a registry layer holds — contracts, measurements, vocabularies, roles, and the stacking every kind shares |
| `comeni_core/goal/` | what was asked for, and what the data measurably looks like |
| `comeni_core/plan/` | what was decided — the IR, each ambiguity's record, the tier ladder |
| `comeni_core/artifact/` | saved pipeline models, dependency fingerprints, and generated-file evidence |
| `comeni_core/egress/` | outbound payload schemas and their declared boundaries |
| `comeni_core/spell/` | how a value is written down — marked strings, routes, directives |

`yaml_strict.py` and `diagnostics.py` provide shared YAML loading and diagnostic helpers.

`comeni_core/settings/` sits beside them: what an installation may change, the layers a value
comes from, and why a setting is greyed out. It holds declarations and logic only; the store and
the cipher are adapters in `mendel-api`.

`tests/repo/test_architecture.py` checks the core, resolver and compiler source paths
named here. Other references and behavior claims require review against the implementation.

**Materialisation is why `emit` takes one argument.** Everything the emitter used to look up —
process names, include paths, entry-channel expressions, the measured facts that ride in `meta`
— is copied onto the `Pipeline`. So `mendel emit build/pipeline.yml` regenerates the Nextflow
with no registry and no network, which is what lets a laboratory archive a validated pipeline
and rebuild it years later: `modules/` is inert vendored source, while the registry is the part
that resolves differently as it changes.

`build` writes `pipeline.yml`, parses it back, and emits from the saved copy.
This checks the serialization round trip on every build. A field that does not survive
YAML causes the build to be refused (`MD0206`).

The compiler separates emission from its adapters. CLI commands read inputs and compose
operations; artifact-file, staging, conformance and gate modules also perform filesystem or
subprocess work. The emission calculation can be tested from supplied models.

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

**So the layout is free to serve a reader**, and a layer that wants one writes it into its
manifest's `layout:`, which `mendel lint` enforces. The public registry reads as five things, one
folder per tool, and **the path is the id** (#216):

```
<layer>/
├─ registry.yml                          the layer's account of itself, and its layout:
├─ tools/nf-core/star/                   one tool, everything about it
│  ├─ tool.yml                           what STAR is, in words an explanation may quote
│  ├─ README.md                          its page, generated (`mendel docs --in-place`)
│  ├─ types/genome.index.star.yml        a type only this tool touches
│  ├─ align/contract.yml  module.yml  module/
│  └─ genomegenerate/…                   one folder per subtool; the folder is the id
├─ profilers/comeni/profile/fastqc/      a use of a tool to measure the data
├─ inspectors/                           code that measures an uploaded sample (14.7.6.2)
├─ vocabulary/
│  ├─ types/<type_id>.yml                states a type may carry, and how it enters a pipeline
│  ├─ measurements/<id>.yml              kind, allowed values, bounds, unit, citation
│  └─ roles/  families/                  the jobs a contract can do; the kinds of data
└─ rules/<name>.yml                      decision tables: measured data → a value or a module
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
provable rather than plausible: `alignment.bam::coordinate_sorted` means one thing across the
whole registry, and a typo is an error at load rather than a module that silently never
matches.

`entry_channel` lives here too, so `mendel-compiler` has no built-in idea what a FASTQ is —
required if the same compiler is to emit calls for a pegi3s image or an in-house process.

### Measurements are declarations, and also types

`Measurement` declares `kind` (`integer`, `number`, `boolean`, `enum`), allowed `values`,
`minimum`/`maximum`, `unit`, `cite`, `edam`, and `deprecated`/`replaced_by`.

**There is deliberately no `string` kind.** A free-text measurement is exactly the hole
`tests/guards/test_egress.py` exists to close: `organism: "patient 4471023's tumour"` is a perfectly
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
      - {when: {read_length: ">= 70"}, then: nf-core/star/align@2.7.11b, cite: "Dobin 2013"}
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
priority. `router._choose` assigns it through a chain of small deciders (`_CHAIN`), each
returning a `Choice` or an open question (`Asked`) and none writing to the plan:

- **structural** — one candidate, or one with strictly smaller surplus than the rest
- **data-profiled** — a rule pinned it, and `selection.reason` carries the citation
- **convention** — equal on surplus, `priority` broke it
- **ambiguous** — nothing distinguished them, or a rule could not apply

**A person's tool wraps the chain.** `goal.constraints.producers` holds `ProducerPin(site,
contract)`, where a `Site` is the type and states a step was chosen to produce. Where the pinned
tool is a candidate and differs from the engine's pick, it is chosen at tier 4 with source
`human`, the engine's pick and reason kept beside it, and one `ProducerDecision`; the resolver is
not asked. A pin that agrees changes nothing; one that applies nowhere is named (`inert_pins`,
`MD0230`). Authoring (`mendel_authoring`: `amend`, `alternatives`, `draft`, `diff`) writes every
decision in the walk as such an amendment to the goal, and projects the draft from the resolved
blueprint.

A pin binds only where the pinned contract is genuinely a candidate for the requested
*states*. featureCounts asks for `alignment.bam::coordinate_sorted`, whose only producer is
the sorter; the aligner rule is about the sorter's own BAM input, one level down, where the
aligners actually compete. Treating a pin as binding everywhere makes the spine unbuildable.
`UnroutablePinError` is for the case that *is* a contradiction: the pin was selected and its
own inputs cannot be reached.

`PipelineIR.needs_review()` returns both flagged parameters and flagged module selections. A
record nobody is shown is not a flag — for a while that method scanned only node params, so
the CLI reported "0 requiring review" while an aligner had been chosen alphabetically.

---

### Authoring decisions and corrections

The draft owns typed input, wanted-output, measurement, producer, parameter and review
subjects. Each subject selects one retained revision. The goal is composed from those
selections; neither the session nor draft stores another live goal. The authored graph is
a versioned projection, and materialisation refuses an outdated projection.

Observations retain evidence origin separately from the actor selecting an answer. Conflicting
samples ask keep, use, correct or unknown. A correction persists truthful input, recomputes the
goal and invalidates reviews whose semantic fingerprint changed. A hand edit is not a
separate kind of work: it is read as intent in the same goal (one builder, #395), so a
correction after it lands in the same pipeline. Read-only history is available; undo is deferred in
[issue 302](https://github.com/comeni-project/Comeni-Labs/issues/302).

**Every change goes through one writer** (`mendel_api/services/changes.py`): a person's click
or edit, the chat model's reply, and a stage's handler all arrive as a
`mendel_authoring.payloads.DecisionChange` — a want, an input, a measurement, a required state, a
tool pinned, a parameter, something asked for that is not offered, or the retraction of one —
and `c.Change` takes the correction section's edges, so the consequence is the diagram's. A
model's change is **heard** when it quotes the person and the quote is in one of their turns
(`mendel_authoring.heard`); heard changes are recorded before the goal is confirmed, everything
else waits in `pipeline_authoring_suggestion` for one click. The quote is kept on the revision
(`heard`, `heard_seq`), never in a payload. Confirmation is recorded (`confirmed_revision`), not
inferred. Every conversational prompt is given what is known, rendered from these rows by
`mendel_authoring.memory` through `services/known.py`.

Legacy conversion uses a frozen snapshot converter before removing the old live columns.
Its archive is historical presentation, never a fallback authority. Recovery after new writes
requires restoring the verified database backup rather than a lossy schema downgrade.

## 4a. One question vocabulary

`comeni_core/review/` is the shared vocabulary for asking a reviewer something. The build path
is its consumer today; the old forge was the other until it was removed
([#361](https://github.com/comeni-project/Comeni-Labs/issues/361)).

```
Question                    base — subject, what, why_open, candidates, closed, evidence
  └── Ambiguity             build. Held by the resolver, answered by AmbiguityResolver
        ├── ParamAsked
        ├── ProducerAsked
        └── SourceAsked

Answer                      base — value, by, how, why
  └── Resolution            build  (adds `confidence`)
```

`ValueSource` is the one provenance vocabulary — `RESOLVER / GOAL / HUMAN / MODEL / MEASURED /
DERIVED`.

**The base classes are inert.** What a question does when nobody answers it lives in its container
and its port, not in a field or an overridden method. An ambiguity *ships flagged*: the pipeline
is built and runnable, marked tier 4.

```python
class AmbiguityResolver(Protocol):
    def resolve(self, ambiguity: Ambiguity) -> Resolution: ...
```

`FlagOnlyResolver` must always answer, because that is what keeps a pipeline runnable with no
model and makes the flagged count an honest measure of rule coverage. Putting `blocks: bool` — or
a `blocks()` method — on `Question` would trade that structural guarantee for a runtime check on
a value. `notes/specs/2026-08-18-the-shared-question.md` §3.1 is the argument; a test asserts the
base carries no behaviour beyond `legal()`.

**Two shapes of candidate, deliberately.** The base offers `Candidate(value, note)` so a
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

**Inspectors are the other measurer.** An inspector measures an uploaded sample's head on this
server, during the conversation, before anything is built; a profiler measures all the data on
the lab's machine when the pipeline runs. Both produce the same measurement ids, and a fact
records which one measured it: `Measured.by` names a profiler's contract, `Measured.pieces` an
inspector's format and measure. Where each runs, and what crosses, is
[the protocol page's table](authoring-protocol.md#where-each-measurer-runs).

A hand-written profile records no tool, and that absence *is* the provenance:
`ValueSource.GOAL` means a person asserted it. `ValueSource.MEASURED` is what a `sealed`
policy will check a tier-3 decision against, once Plan 2 builds `ProfilePolicy` — issue #2.

---

## 7. The guards

Three AST-and-reflection tests, each of which exists because the property it asserts was
broken by someone who meant well.

| Guard | Asserts | Broken by |
|---|---|---|
| `tests/guards/test_purity.py` | the pure packages import no web framework, HTTP client or LLM library — closed allowlist for `comeni-core`, `mendel-resolver`, `wiener-core`, `dag-core` and `mendel-authoring`, banlist including stdlib transports and dynamic imports for `mendel-compiler` | four lines: `import urllib.request`, `importlib.import_module("httpx")`, `__import__("openai")` |
| `tests/guards/test_egress.py` | registered boundaries and their flows; payloads across every egress module; no `Any`, mappings, or unmarked strings; rejection of unknown fields; explicit free-text fields | an undeclared text field or a payload omitted from schema traversal |
| `tests/guards/test_construction.py` | a `DataProfile` is built in exactly one place, and that place validates it | — new; watched failing by adding `DataProfile()` to `router.py` |

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

### Why the egress guard is here, and it is not primarily privacy

Stated in this order because the first reason holds whether or not anybody is talking about
clinical data, and a rule whose purpose has gone quiet is a rule the next reader deletes as
ceremony.

**It is what makes a model call reproducible.** Every crossing carries a declared type, which is
what lets a response be recorded and replayed in CI, a rendered prompt be held to a golden file,
and an answer be checked against the question that was asked. The alternative is passing a dict,
and nothing about a dict can be frozen, diffed or replayed. §9's seam only works because the
payload on each side of it has a shape.

**It is where "which parts did a model touch" becomes answerable.** That is the product claim,
not a compliance feature: *the rest is reproducible without a model* is only checkable if there
is a boundary to point at and a list of what crossed it.

**Clinical non-receipt is a consequence of those two, not the reason for them.** It is a real
claim and `docs/design/clinical-data-protection.md` is the long form — but the doors were not
built to satisfy it, and it is the part of this that would not survive on its own. The expensive
half of that story is deliberately unbuilt: **no `EgressRecord` exists for any door**, and the
three protection profiles are issue #71, which nothing has started.

**What the guard costs, measured.** Declaring door 5 on 2026-09-05 took under an hour, most of
it prose; the mechanical part was a Pydantic type that would have existed anyway, one entry in
`DECLARED`, and two lines in a list. It found two defects on the way in, neither privacy-shaped:
a response model carrying a `file` field that the path allowlist never walked, and a global
free-text count asserted in a test about channel scope, which would have broken on any unrelated
change.

`tests/repo/test_generated_types.py` is a fourth of a different kind: `profile.pyi` is generated
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

## 9. The seam a model plugs into

`mendel_resolver/ports.py` declares `AmbiguityResolver` as a protocol. `FlagOnlyResolver`
is the current blueprint path's implementation: it flags unresolved choices for the person.
`mendel_api/authoring/resolver.py` implements `ModelResolver`, but
`mendel_api/services/blueprint.py` leaves that adapter unwired.

The application adapter imports both the resolver port and `comeni-ai`; shared provider
transport does not depend on Mendel's resolver, and the resolver does not import transport.
Builder calls outside blueprint resolution include understanding, follow-up, phrasing,
read-back and sample characterisation. Their current owners and admission/storage boundaries
are described in [Mendel AI ownership](mendel-ai-ownership.md).

Tier 3 remains a lookup over declared rules. An unresolved choice does not make that lookup
reach a model. Egress shapes are declared in `comeni_core/egress/boundaries.py`; callers own
protection checks and transport.

---

## 10. Where declared data comes from

Everything above reads the registry. Today a registry is written by hand, as reviewed changes
to its own repository ([Writing a contract](../how-to/registry/add-tool.md)). The forge, which
drafts registry data for a person to approve, is being rebuilt from scratch
(`docs/superpowers/specs/2026-10-19-forge-mvp-design.md`); the old `mendel-forge` package was
removed in [#361](https://github.com/comeni-project/Comeni-Labs/issues/361). Invariant 2 holds
either way: nothing writes to a registry without a person's approval.

### `comeni-ai` — model access

One primitive: `generate(instruction, shape, evidence)` validates a model's answer against a
declared Pydantic shape before any caller sees it, and returns `None` when it declines or will
not validate. `choose_one` and `choose_many` are helpers for the closed-choice case; two of them
because `roles` and `produces[].state` take several members from one closed set.

The boundary is not *the model may not speak* but **nothing it says is taken on trust** — the
same rule closed vocabularies and contract-versus-module checking already enforce. A drafted rule
has the rule validator; a `Goal` is a Pydantic model.

The package holds **no domain types** — it speaks in strings and shapes its caller declares,
which is what lets the tier-4 ambiguity resolver reuse it unchanged in Plan 3. It is impure and
classified as such. `MA0001`–`MA0009` are its diagnostics.

`converse` is the same validation over a multi-turn exchange, and `PromptTemplate` loads,
renders and versions a *caller's* committed prompt files — it owns no prompt text, because
shared infrastructure that accumulates every agent's prompts has become a shared pile rather
than a boundary.

**It was `mendel-ai` until 2026-09-04.** The rename is not cosmetic: an engine-specific name on
the shared transport is what would have produced three clients, one each for the forge, the
builder and Wiener's agents, and `MENDEL_MODEL` configuring a Wiener agent is a lie in a `.env`
file. The configuration is `COMENI_AI_*` and the `MENDEL_*` spellings are read as a fallback.
`mendel-ai` survives as a deprecation shim that re-exports this package and holds no code;
`packages/mendel-ai/tests/test_shim.py` refuses a new in-repo import of it.

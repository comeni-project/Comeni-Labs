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
| materialise | `PipelineIR`, `Registry`, `Vocabulary`, measurements | `Pipeline` | `comeni_core/pipeline.py` |
| emit | `Pipeline` | `str` | `mendel_compiler/emit.py` |
| gate | a pipeline directory | `GateResult` | `mendel_compiler/gates.py` |

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

Four kinds, all of them files under a **layer directory**, all of them stacked by repeating
`--registry`. Later layers win.

```
<layer>/
├─ vocabularies/<type_id>.yml      states a type may carry, and how it enters a pipeline
├─ measurements/<id>.yml           kind, allowed values, bounds, unit, citation
├─ contracts/**/*.yml              what a module consumes, produces and is called with
└─ rules/*.yml                     decision tables: measured data → a value or a module
```

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
identical for all four.

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

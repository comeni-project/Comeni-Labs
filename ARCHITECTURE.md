# Architecture

How Mendel turns a goal into a Nextflow pipeline, and why each part is shaped the way it is.

Written against the code as it stands, not against a plan. Every type name here exists; if
one has drifted, the code is right and this document is wrong.

For the product claim and the invariants those parts serve, read `CLAUDE.md` first. This
document is the *how*; that one is the *why it may not change*.

---

## 1. The five stages

```
   Goal ──route──▶ RoutePlan ──resolve──▶ PipelineIR ──emit──▶ main.nf
                                                             nextflow.config
                                              │                     │
                                              └──────run_gate───────┴──▶ GateResult
```

| Stage | Input | Output | Lives in |
|---|---|---|---|
| load | layer directories | `Layers` | `mendel_resolver/layers.py` |
| route | `Goal`, `Registry`, `RuleTable` | `RoutePlan` | `mendel_resolver/router.py` |
| resolve | `RoutePlan` | `PipelineIR` | `mendel_resolver/resolve.py` |
| emit | `PipelineIR`, `Registry`, `Vocabulary` | `str` | `mendel_compiler/emit.py` |
| gate | a pipeline directory | `GateResult` | `mendel_compiler/gates.py` |

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

One block per decision, rows underneath:

```yaml
decisions:
  - decides: {producer_of: alignment.bam}
    cite: "Dobin et al. 2013, doi:10.1093/bioinformatics/bts635"
    rows:
      - {when: {read_length: ">= 70"}, then: nf-core/star/align@1.11.0}
      - {when: {read_length: "< 70"},  then: nf-core/hisat2/align@2.2.2}
```

Grouped rather than flat so a reviewer reads the justification once and then reads the
branches — and so a *missing* branch is visible, which flat rules actively hide.

**Every table is validated at load**, against the registry, the vocabulary and the
measurements. A `decides.param` no contract declares, a `producer_of` type nothing produces,
a pinned contract not in the registry, a comparison against an enum, or a `when` naming an
undeclared measurement: each refuses to load, and the error says what the author *can* write.

This is the load-bearing part. `subject` used to be an unvalidated free string, and two of
the five rules shipped in the example layer had never once executed. Nothing said so, and a
constant named `KNOWN_DEAD_RULES` recorded them instead. Validation replaced both.

A layer replaces a decision **block**, not a row — a reviewer should read one block and see
the entire effective decision.

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
| `tests/test_egress.py` | four doors, one payload type each, no `Any`, no mapping, no bare `str`, `extra="forbid"`, free text only in the four named fields | a `user_note: str`, which carried no marker to catch and no `Any` to forbid |
| `tests/test_construction.py` | a `DataProfile` is built in exactly one place, and that place validates it | — new; watched failing by adding `DataProfile()` to `router.py` |

The third exists because validation *moved*. `DataProfile` used to hold four hardcoded fields,
so `extra="forbid"` alone refused `sample_name`. Measurements are declared data now, so the
model cannot know what is declared, and the mapping shorthand is no longer a validation
boundary. `MeasurementRegistry.profile()` is the only validating constructor,
`test_construction.py` enforces that nothing else builds one, and `mendel build` re-routes
every goal's profile through it. Without that last step a goal file carrying
`profile: {sample_name: SILVA_biopsy_01}` validates, resolves and reaches
`pipeline.ir.json` — the 2026-08-03 audit's `constraints` hole, re-opened one field over.

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

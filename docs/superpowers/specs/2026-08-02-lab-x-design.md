# Lab X — Deterministic Pipeline Builder

**Date:** 2026-08-02
**Status:** Design approved, ready for implementation planning
**Scope:** Lab X only. Lab Y, Lab Z and Comeni Code are separate specs.

---

## 1. Context and philosophy

Researchers increasingly build analysis pipelines with AI assistance without the
methodological background to judge what the AI produced. A biologist can get a
working-looking `nf-core` pipeline out of a chat window in minutes and have no basis
for knowing whether the tool choices, parameters, or data assumptions are defensible.
The output is plausible, unattributed, and unreproducible.

Comeni Labs exists to make pipeline construction **explainable and reproducible**
rather than merely fast. The name comes from John Amos Comenius, generally credited
with the idea of universal public education: in an age where AI leads, humans must
still be able to follow.

Lab X is the pipeline builder — the first and load-bearing component.

### The product claim

> Given the same goal, Lab X produces the same pipeline, and every decision in it
> can be traced to a constraint, a convention, a measurement, or an explicitly
> flagged judgement call.

That claim is the entire differentiator against a chat window. Every design decision
below serves it.

---

## 2. Product decomposition

| Component | Role | Depends on | Status |
|---|---|---|---|
| **Lab X** | prompt → resolved module graph → Nextflow | nothing | **this spec** |
| Lab Y | run pipelines on Azure/AWS, monitor, auto-diagnose failures | Lab X output format | later spec |
| Lab Z | data analysis / QC agent | Lab X contracts | **parked** |
| Comeni Code | node-based learning platform; modules become lessons | Lab X registry | separate repo |

Lab X is first because it has no upstream dependency and both Lab Y and Comeni Code
consume its artifacts. Lab Z is parked deliberately: a data-checking agent cannot be
designed before the pipeline contract exists.

**Repository:** Lab X, Y and Z live in `Comeni-Labs`. `Comeni-Code` remains the
learning platform, developed independently so release cycles stay decoupled.

---

## 3. v1 success criterion

Falsifiable, in CI:

> From a plain-language prompt plus a test dataset, Lab X emits Nextflow that runs
> green on the `nf-core` test profile and produces a counts matrix.

Target pipeline is the **RNA-seq spine** — roughly 15–20 modules on the canonical
path, not the full `nf-core/rnaseq` decision tree:

```
FASTQC → TRIMGALORE → STAR_ALIGN → SAMTOOLS_SORT/INDEX → FEATURECOUNTS → MULTIQC
```

Full `nf-core/rnaseq` (multiple aligners, pseudo-aligners, UMI handling, optional QC
branches) is explicitly v2. The spine proves routing, all four tiers, compilation and
repair end to end at a scope that can be finished.

---

## 4. Architecture

### 4.1 Three workflows

```
WORKFLOW 1   forge      sources ──▶ contracts          offline, human-gated
WORKFLOW 2   builder    prompt ──▶ GOAL ──▶ IR         tiers 1-4, decision records
WORKFLOW 3   compiler   IR ──▶ .nf ──▶ validate ──┐    cycles until green or gives up
                          ▲                       │
                          └──── repair ◀──────────┘
```

### 4.2 The governing principle

**AI never evaluates contracts or rules at runtime. It authors artifacts offline that
humans approve, and runtime is pure lookup.**

This applies uniformly:

- the forge drafts module contracts; humans approve them
- AI proposes tier-3 rules; humans approve them into versioned rule tables
- AI proposes new vocabulary states; humans approve them

Runtime AI is confined to exactly three declared, bounded points:

1. **prompt → goal extraction** — output is shown to the user, who can correct it
   before anything runs
2. **tier-4 resolution** — always flagged, always recorded as a decision record
3. **compiler repair** — bounded to 3 attempts, proposes IR patches only, and every
   attempt is recorded

Nothing else in the runtime path calls a model.

### 4.3 Ports and adapters

The pure core declares interfaces; AI plugs in as implementations. No package in the
pure core imports anything AI-shaped. This makes the determinism claim testable and
makes the model provider a configuration detail.

```
                     ┌────────── comeni-forge ──────────┐
  nf-core meta.yml ─▶│  ingest → AI draft → human OK    │
                     └──────────────┬───────────────────┘
                                    ▼
                            module contracts
                                    │
  ┌─────────────────────────────────┼──────────────────────────────────┐
  │                    WORKFLOW 2 — builder                            │
  │                                 ▼                                  │
  │ prompt ─▶[AI port]─▶ GOAL ─▶ comeni-resolver ─▶ IR                 │
  │           extract   (user      tier 1 structural                   │
  │                     edits)     tier 2 convention                   │
  │                                tier 3 rule table                   │
  │                                tier 4 ─▶[AI port] ─▶ decision rec  │
  └────────────────────────────────────────────────────────────────────┘
                                    │
  ┌─────────────────────────────────▼──────────────────────────────────┐
  │                    WORKFLOW 3 — compiler                           │
  │  IR ─▶ Nextflow DSL2 ─▶ gates ─▶ green?  ─yes─▶ done               │
  │   ▲                                │no                             │
  │   └──── IR patch ◀──[AI port]──────┘  bounded, max 3 attempts      │
  └────────────────────────────────────────────────────────────────────┘
```

### 4.4 Packages

| Package | Contains | Pure |
|---|---|---|
| `comeni-core` | data types, contract schema, pipeline IR, registry | yes — no I/O, no model |
| `comeni-resolver` | four-tier ladder, rule tables, decision records | yes — AI only via injected port |
| `comeni-compiler` | IR → Nextflow DSL2, validation gates, repair cycle | yes — AI only via injected port |
| `comeni-ai` | port implementations via LiteLLM | no — the only package that calls models |
| `comeni-forge` | ingestion adapters, contract drafting, approval queue | no |
| `comeni-api` | FastAPI surface, OpenAPI schema, job dispatch | no |

Named `comeni-compiler` rather than `codegen` deliberately: "compiler" carries the
determinism claim.

---

## 5. Data model

Three artifacts. Everything else derives from them.

### 5.1 Module contract

Produced by the forge, consumed by the resolver.

```yaml
id: nf-core/star/align@1.11.0
consumes:
  reads:  { type: fastq.reads, state_required: [], state_preferred: [trimmed], cardinality: 1..2 }
  index:  { type: genome.index.star, ref: required }
produces:
  bam_sorted:   { type: alignment.bam, state: [coordinate_sorted] }
  bam_unsorted: { type: alignment.bam, state: [] }
params:
  - { name: seq_platform, tier_hint: 4, default: null }
provenance:
  source: nf-core-meta-yml
  drafted_by: <model-id>
  approved_by: <human>
  approved_at: <date>
```

`state_required` states the router must satisfy — an unmet one triggers gap insertion
(§6.3) or fails the build. `state_preferred` states influence tie-breaking only and
never cause insertion or failure.

**Why the overlay exists.** `nf-core` `meta.yml` declares outputs as `type: file` with
a filename pattern. `samtools/sort` and `star/align`'s `bam_unsorted` are both
`type: file, *.bam`; "sorted" appears only in the English description. A router working
from `meta.yml` alone would wire an unsorted BAM into `featureCounts`, emit valid
Nextflow, and fail at runtime. `meta.yml` is a **scaffold, roughly 60% of the work** —
filename patterns, parameter lists, tool identity, EDAM references. The missing 40% is
semantic state, and routing depends entirely on it.

### 5.2 Type vocabularies

Each data type declares the exact states it may carry. Closed for validation, open for
extension.

```yaml
# vocabularies/alignment.bam.yml
states: [coordinate_sorted, name_sorted, deduplicated, filtered]
```

A contract using a state outside its type's vocabulary is rejected at approval time.
When the forge proposes a genuinely new state, it enters the **same approval queue** as
contracts — one click, no code change, no release. Vocabularies are versioned data
files.

This is what lets the router *prove* a connection is valid rather than hope it is.

### 5.3 Pipeline IR

Resolver output, compiler input, and the thing tests assert on. A typed DAG:

- nodes reference contract IDs
- edges carry the resolved type **and state**
- every parameter carries `value` + `tier` + `reason` + `review_level`

The IR earns its place even with a single compiler backend: the resolver must emit
something assertable in a unit test. Testing by string-matching generated Nextflow
would be miserable.

### 5.4 Decision record

Emitted whenever tier 3 misses or tier 4 fires:

```
what was ambiguous · options considered · what was chosen · which model ·
confidence · human override (if any)
```

Persisted, and **replayed on rerun** rather than re-asking the model. Determinism
becomes "deterministic given a decision record", and the record is auditable,
diffable, and human-correctable. This is the artifact that makes the system get *more*
deterministic the more it is used — the first user pays for the model call, everyone
after replays the decision.

This is the concrete thing a vector store (Mem0/Qdrant) would hold. Not vague
"pipeline memory" — resolved ambiguities, retrieved by goal similarity.

---

## 6. The resolver

### 6.1 Four tiers

Every module choice and every parameter exits the ladder at exactly one tier and
carries it forever.

| Tier | Fires when | Produces | Review level | UI |
|---|---|---|---|---|
| **1 structural** | no choice exists — goal or data forces it | value + the forcing constraint | `none` | silent |
| **2 convention** | a documented default exists for this context | value + citation | `none` | green |
| **3 data-profiled** | a rule matches measured data properties | value + rule + measurement | `advisory` | **yellow** |
| **4 ambiguous** | no rule matched | AI proposal + reasoning + alternatives | `required` | **red** |

`review_level` is a field on the resolution, not a UI convention, so the API exposes it
and Lab Y and Comeni Code can both consume it.

**Tier 3 is yellow, not green, deliberately.** A tier-3 match is only as good as the
rule *and* the measurement. If the profiler misreads strandedness, the rule fires
correctly on wrong input and produces a confidently wrong pipeline. Yellow means "the
machinery worked, check the premise" — exactly the failure a biologist can catch and
the system cannot.

**Tier 4 is always flagged, even at high model confidence.** That is the honesty
mechanism and the difference from a chat window.

Triage story for the dashboard: **red must be resolved before running; yellow can be
batch-acknowledged; green collapses by default.**

### 6.2 Tier 3 is a rule table, never a model

Measuring the data (read length, strandedness, encoding, sample count) is pure
computation. What maps measurements to a choice is a **declared rule table**:

```
read_len >= 70          → STAR
strandedness = reverse  → featureCounts -s 2
```

A miss is **not** an escalation to an LLM inside tier 3 — it is a demotion to tier 4,
where AI already lives and everything is flagged. This keeps tier boundaries meaningful
and keeps the common case free, instant and reproducible. Rules are versioned data,
reviewable, and citable to a paper.

### 6.3 Routing and gap insertion

When a module needs `alignment.bam[coordinate_sorted]` and the graph holds
`alignment.bam[]`, the resolver searches the registry for a contract producing that
state from what is available, and inserts it.

- bounded search depth
- deterministic tie-breaking: tier, then explicit contract priority, then lexical
- **if several routes tie, that is ambiguity** — demote to tier 4 rather than pick
  arbitrarily

### 6.4 The dashboard falls out for free

Every node and parameter already carries tier, reason and review level. The UI is a
rendering of the IR. There is no separate explanation system to build — the
explanation *is* the data structure.

---

## 7. The compiler

### 7.1 Repair edits the IR, never the generated file

If AI patches `.nf` text directly, the IR stops describing the pipeline: dashboard
explanations go stale, decision records lie, reruns are not reproducible.

A repair proposes an **IR-level change** — insert `SAMTOOLS_SORT`, flip a parameter,
swap a module — and the compiler re-emits from scratch. Text patching is a last resort
and is flagged loudly as *"this pipeline diverged from its plan."*

### 7.2 Bounded loop

Maximum 3 attempts, then stop and hand to a human with everything that was tried. An
unbounded AI repair loop burns money and converges on nonsense.

### 7.3 Validation gates, cheapest first

| Gate | Cost | Catches |
|---|---|---|
| parse / lint | instant | syntax, malformed DSL2 |
| `-preview` | seconds | DAG construction, channel wiring |
| `-stub-run` | seconds | whole graph executed with dummy outputs |
| `-profile test` | minutes | the real thing — the v1 pass/fail |

`-stub-run` is the important one: `nf-core` modules all define stub blocks, so the
entire DAG can be exercised without downloading a genome or burning CPU. The repair
loop iterates in seconds and only the final candidate pays for a real run.

---

## 8. The forge

One approval queue serves three proposal kinds — **new module contract**, **new
vocabulary state**, **new tier-3 rule** — with the same review UI, versioning and
provenance stamp. That uniformity is worth real effort saved.

**v1 ingestion:** `nf-core` `meta.yml`.
**Later:** `pegi3s` Docker images. Their 190 tool directories carry `Dockerfile` +
prose `README.md` only — no structured metadata — so ingesting them means parsing
English, which is strictly harder and is a capability the tool should grow into rather
than start with.

---

## 9. Stack

| Layer | Choice | Rationale |
|---|---|---|
| Core packages | Python | Nextflow tooling, bioinformatics libraries, data profiling all live there |
| API | **FastAPI** | async-native for streaming; OpenAPI from the same Pydantic models `comeni-core` defines, no duplicate serializers |
| Persistence | SQLAlchemy 2.0 + Alembic | standard, framework-independent |
| Workers | **ARQ** | async-native, Redis-backed, pairs naturally with FastAPI |
| Models | **LiteLLM** | one interface across Anthropic/OpenAI/Gemini/local; satisfies the any-model requirement |
| Frontend | **React + TS + Vite + Tailwind**, TanStack Query | matches the established pattern in `Cladewright` and `website_nubiup` |
| Client | generated from `openapi.json` | contract and IR types stay in sync automatically |
| Deploy | Docker Compose dev/prod + nginx + Makefile | matches existing repos |

**Django was considered and rejected.** The main argument for it was that its admin
could serve as the forge approval queue — but the queue needs side-by-side
source-vs-draft diffs and a YAML editor, which the admin does poorly, and the React SPA
provides a `ReviewQueue` screen anyway. Django-Ninja was additionally rejected on
maintenance grounds: ~9.1k stars, 66% of commits from a single maintainer, roughly
monthly cadence. Comeni Labs is not a CRUD app — the value is a pure Python library and
the API is a thin skin over a compute engine with long jobs and streaming, which is
FastAPI's shape.

**This decision is low-stakes by construction.** `comeni-core`, `comeni-resolver` and
`comeni-compiler` import no web framework. Replacing FastAPI later means rewriting
`comeni-api` and nothing else.

---

## 10. Repository layout

```
comeni-labs/
├─ packages/
│  ├─ comeni-core/          types, contract schema, IR, registry
│  ├─ comeni-resolver/      four-tier ladder, rules, decision records
│  ├─ comeni-compiler/      IR → Nextflow, validation gates, repair cycle
│  ├─ comeni-ai/            model ports via LiteLLM
│  ├─ comeni-forge/         ingestion, drafting, approval queue
│  └─ comeni-api/           FastAPI surface
├─ vocabularies/            data types and their closed state lists
├─ rules/                   tier-3 rule tables, versioned, citable
├─ contracts/               approved module contracts
├─ frontend/                React + TS + Vite + Tailwind SPA
└─ docs/superpowers/specs/  this spec
```

---

## 11. Testing

Mirrors the purity split. This is what makes the determinism claim auditable rather
than rhetorical.

- **`core` / `resolver` / `compiler` — golden-file tests.** Goal in → exact IR out →
  exact `.nf` out. No network, no model, milliseconds. A change in generated Nextflow
  becomes a reviewable diff in CI.
- **`ai` — contract tests against recorded fixtures.** The suite never calls a live
  model.
- **End-to-end** — `-stub-run` on every commit; full `-profile test` nightly.

---

## 12. Explicitly out of scope for v1

- Lab Y (cloud execution and monitoring) and Lab Z (data analysis)
- Comeni Code integration — modules becoming lessons
- `pegi3s` ingestion
- Full `nf-core/rnaseq` branching: alternative aligners, pseudo-aligners, UMI handling
- Agent-authored *new* modules (as opposed to contracts for existing ones)
- Vector-store retrieval of decision records — records are persisted in v1, similarity
  retrieval comes once there is a corpus
- Gamification, auth beyond a single-tenant deployment, billing

---

## 13. Prior art consulted

- **braidworks** (`../braidworks`) — the typed-routing model here is directly informed
  by its Strand/Weaver/Braider design: declared consumes-produces contracts, a registry
  graph, plan-then-execute separation, confidence and review flags carried as data
  rather than raised as exceptions.
- **nf-core/modules** — `meta.yml` as ingestion scaffold; stub blocks as a validation
  tier.
- **auto-phylo / auto-phylo-pipeliner** (pegi3s) — an existing Docker-based pipeline
  maker with a GUI from the host lab. Noted as prior art and as the comparison Lab X
  will be measured against. Its implementation is not a model to follow.

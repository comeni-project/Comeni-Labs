# The builder is a builder — 2026-08-23

Plan 3E, on `plan-3e-builder`. Twelve tasks, `make verify` green, 1495 tests.

## What it is

`/build` was a **visualiser**: a goal went in, the resolver searched, the canvas drew what it
found, and nothing on it could be changed. It is a **builder** now — you assemble, it checks you,
and it shows what the resolver would have built instead.

The insight the spec rested on held up: **it is the same knowledge from a different route.**
`resolve()` searches for edges; a builder is handed edges and asked whether they hold, and every
fact that check needs was already declared. Nothing new was declared.

**Six new things, all of them small:**

| | |
|---|---|
| `mendel_resolver/validate.py` | `validate(graph, layers) -> Verdict`. Pure, golden-tested, nine `MD0500` codes |
| `mendel_resolver/compatibility.py` | what can feed what, precomputed, so a browser colours a wire with no round trip |
| `mendel_resolver/materialise.py` | a drawn graph becomes a `PipelineIR` **and a `Goal`** |
| `comeni_core/plan/draft.py` | `DraftGraph` — four names per edge, nothing derived |
| `comeni_core/review/verdict.py` | `Verdict`, three levels, reports and never refuses |
| `services/{validate,compare,drafts}.py` | the API half, plus `POST /pipeline/draw` |

## The thing worth carrying

**A hand-drawn graph emits real Nextflow.** Four nodes drawn by hand → validated → kept →
`pipeline.yml` → `mendel emit` → a workflow with entry channels wired, params resolved and
processes in order.

Against `mendel build` on the same registry, the process sets differ by **exactly one include**:
`TRIMGALORE`, which the resolver adds because `star/align.reads` declares
`state_required_conventional: [trimmed]` and the four-node drawing omitted it. **That is the
correct answer**, and it is what `compare` reports as `mendel-only`. The two halves of the screen
disagree only where the drawing actually differs.

## What the plan got wrong, and how

The plan was audited before execution — twelve findings, A146–A157, two critical, all fixed in
the text before a line was written. **Execution still found nine more.** Every one was a guard
refusing something, which is the machinery working rather than failing.

| found by | what was wrong |
|---|---|
| import | `review/verdict.py` importing `plan/draft.py` — `plan/` already imports `review/`, so it was a **cycle**. `Finding` carries two `EdgeRef`s instead (A146, A157) |
| `EmittedBy.CORE` docstring | `emitted_by: core` for a verb living in `mendel-resolver`. That docstring warns about this exact drift — 23 entries once named the wrong package |
| `test_diagnostics_ownership` | `_f(code, …)` passed the code **positionally**, and the guard scans for `coded("X"` or `code="X"`. All nine codes would have read as dead while being emitted |
| `ContractId` validator | contract ids carry `@version`; the plan's `nf-core/star/align` is not one |
| the doc generator | a new `concern` needs a heading in `HEADINGS` or it refuses by name |
| `test_a_schema_change_bumps_the_version` | `SERIALISED_SHAPE` moves *with* `SCHEMA_VERSION`. Its own message says updating either alone is the defect Plan 1.14 Task 0 fixed |
| `test_openapi` | every operation id is pinned by hand. Six new ones added |
| `test_every_configured_root_is_absolute_in_the_compose_file` | a new `MENDEL_*_ROOT` that compose does not set. Its docstring predicted this by name |
| `MD0210`, `MD0224` | a kept draft with no `modules/` and no settings — `mendel emit` refused the file `keep` had just written |

**The pattern in the audit's own findings was fixtures and entry points invented rather than
read** — `tests.helpers.REGISTRY_ROOT` does not exist, there is no shared `client` fixture, and
it is `create_app()` not `app`. Backend *types* were verified carefully; test scaffolding was
not, and that is where the errors were.

## Three decisions the operator took mid-execution

1. **`comeni-core` 0.2.0, not 1.0.0.** `SCHEMA_VERSION` bumps are `x.0.0` by the release guide,
   but the pre-1.0 paragraph permits a `0.x.0` break if it is said out loud. 1.0.0 would claim
   the artifact format is stable, and it has moved twice in three weeks. The changelog says it.
2. **The goal is derived from the graph.** `Pipeline.of` requires a `Goal` and a drawn graph has
   none. Entry-channel inputs are what you have; terminal outputs are what you want. For the
   hand-drawn spine that reconstructs `examples/rnaseq-goal.yml` exactly, from the other end.
3. **Drawn settings run the resolver's own ladder.** `_resolve_param`, the function
   `mendel build` calls — not a cheaper defaults-only pass. Otherwise a drawn pipeline and a
   resolved one disagree on the same node and `compare` reports differences that are artifacts
   of the route rather than of the drawing.

## One thing that could not be done as designed

**A156 — telling "a param a model set to null" from "a param a model never touched" — cannot be
closed with `model_fields_set`.** Measured: after a `model_dump()` round-trip **every** field is
in that set, so presence-by-fields-set would refuse every `pipeline.yml` ever written.

The checkable direction is enforced (an author naming no act is refused); the un-checkable one is
written on the field. That is the shape A130 settled on. `test_a_decision_round_trips_through_model_dump`
guards against reaching for `model_fields_set` again.

## Measurements

| | | budget |
|---|---|---|
| `POST /validate` | **5.4 ms** | 500 ms |
| `GET /compatibility` | **9.8 ms** | |
| `GET /compatibility` (304) | **5.1 ms** | |
| `POST /compare` | **10.1 ms** | |
| the compatibility index | **2,247 bytes** | |
| index/verb agreement | **216 pairs**, 8 of 11 signatures legal | |
| input ports with `cardinality != "1"` | **0 of 18** | |

**The 304 costing 5.1ms rather than ~0 is the number worth keeping.** That is
`digest_of_directory`, which the performance audit measured at 4.6ms and named as the real
per-request floor — so **the ETag buys bandwidth, not latency**, and that floor rises with the
registry.

**`MD0505` ships with one legal value exercised.** Every input port in the registry declares
`cardinality: "1"`; the field genuinely had no reader before this, so no contract's value for it
has ever been checked against reality.

## Traps

- **A helper that takes a diagnostic code positionally is invisible to the ownership guard.** It
  scans for `coded("MD0001"` and `code="MD0001"` and knows no third shape. Keyword-only, always.
- **`node_modules` are absent in a fresh worktree.** `npm install` in `frontend/` before vitest,
  or the vite config fails to load and every test errors at startup.
- **`Wires.d()` reads `points[0]`.** A fixture wire with `points: []` throws inside the render
  rather than drawing nothing, and surfaces as an unrelated missing element.
- **The client prepends `/api`.** `get("/api/pipeline/…")` fetches `/api/api/…`.
- **A guard's own repair needs auditing.** A157 was introduced *by* the pre-execution audit while
  fixing A146, and found only because the fix's own claim was checked against `_edge_ref` rather
  than believed. One pass is not obviously enough.

## What is next

1. **The forge.** The operator is rethinking its design. Nothing here touched it, and the 3C
   journal's note stands: it needs testing and general rework.
2. **Keeping-yours records nothing yet.** `Compare`'s *keep mine* holds its reason in component
   state; writing it to `ProducerDecision.human_override` needs an override endpoint that is not
   built. Held rather than silently dropped, which is the A77 failure it would otherwise repeat.
3. **The picker still lists every contract.** [#77](https://github.com/comeni-project/Comeni-Labs/issues/77)
   puts the real number at ~1,600 once nf-core and pegi3s are ingested; at that point it needs
   server-side search and the index needs to ship incrementally.
4. **A14 is still open**, and one more revert is recorded in the ledger.

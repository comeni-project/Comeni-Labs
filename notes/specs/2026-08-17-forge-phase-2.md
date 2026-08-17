# The forge, Phase 2 — a model fills the holes

**Status:** design spec, written 2026-08-17 with the operator, before any plan. Phase 1 is
merged (`cfda572`); this is the phase that puts a model behind `HoleFiller` and creates
`mendel-ai`.

**Precedence:** where this spec and the code disagree, the code is right and this file has
drifted — it is written against types that exist and is dated so it can be checked.

**Read first:** [`2026-08-16-the-forge.md`](2026-08-16-the-forge.md) for what the forge is, and
[`journal/2026-08-17-the-forge.md`](../journal/2026-08-17-the-forge.md) §Phase 2 for the handoff
this spec answers.

---

## 1. The fifth-door question, resolved

**There is no door 5.** Phase 1's handoff named this as the thing to settle before writing a line,
and it is settled in the direction the design documents already implied.

Invariant 14 reads as absolute — *"data leaves through four declared doors and no others"* — but
`docs/design/clinical-data-protection.md` §4.2 states what the doors are actually tracking:

> **Free text enters at exactly one door. Anything derived only from typed inputs is publishable;
> anything downstream of the prompt is not.**

The egress boundary is a **taint-tracking system with one taint source: the researcher's typed
prompt.** Read that way the four doors are one path — prompt → goal → build → pipeline → publish.
`PromptRequest.prompt` is the taint source; `AmbiguityRequest` is closed vocabulary because it is
downstream of it; `ErrorCategory` exists because Nextflow's stderr carries work directories and
input filenames; door 4 is the artifact that path produces.

**The forge is not on that path.** It has no prompt, takes no `Goal`, and writes no
`pipeline.yml`. It reads vendored modules and registry files — public data — and produces registry
files that a build later consumes. It is the offline authoring half of invariant 2, and a clinical
laboratory can deploy Mendel and never run it.

This is corroborated by a list nobody had to change: `AiPoint` declares exactly three runtime AI
points — `prompt`, `tier-4`, `repair`. Invariant 3 says there are exactly these, and
`tests/test_ai_provenance.py` asserts the list. **The forge is not one of them and must not
become one.**

**What this costs, stated rather than waved past.** The two options in Phase 1's handoff were
*make it door 5* or *write the argument that it is not*. This is the second, and the handoff's
warning against it is fair: an invariant's strength comes from being absolute, and a carve-out is
what future carve-outs cite. The answer is that this is not a carve-out but a **scope correction**
— §4.2 has said since it was written that the boundary tracks prompt-derived data, and the
one-line summary in `CLAUDE.md` lost that qualifier. `DOORS` and `tests/test_egress.py` do not
change. What changes is three sentences of prose that were wrong about what they were describing.

### 1.1 The two consequences for the plan

- **A documentation task, not an architecture task.** `CLAUDE.md` invariant 14, `ARCHITECTURE.md`,
  and `docs/design/clinical-data-protection.md` §4.1 each gain the qualifier §4.2 already has.
  `notes/specs/2026-08-16-the-forge.md` §10.3 records this section as its resolution.
- **`--no-ai` does not arrive here either.** `CLAUDE.md` says the flag arrives with Plan 2. With
  `--model` an opt-in on `forge fill`, the forge's default *is* the no-AI lane — the same argument
  that made `NoFiller` not-a-flag — and `mendel build` still has no AI path to switch off until
  the ambiguity resolver exists. That sentence is corrected in the same change.

---

## 2. What Phase 2 builds

**`mendel-ai`, and its first consumer.** Plan 3 adds its second.

The distinction matters because "transport only" undersold it in conversation and would invite a
fifty-line wrapper. The package is built properly here — three access lanes, coded failures, a
fixture harness every later AI subsystem inherits. What is deferred is one *adapter class*,
`LLMResolver(AmbiguityResolver)`, whose hard parts are not `mendel-ai` concerns at all: replay
(invariant 9), always-flagged (invariant 6), `sealed` blocking the build, and
[#69](https://github.com/comeni-project/Comeni-Labs/issues/69).

### 2.1 Out of scope, with the reason

| Not built | Why |
|---|---|
| `LLMResolver(AmbiguityResolver)` | Plan 3, beside the review screens. Invariant 6 flags tier 4 even at high confidence, so a model answer still needs a human — the screen is what makes tier 4 tractable, not the model |
| `AiProvenance.available` threading | [#69](https://github.com/comeni-project/Comeni-Labs/issues/69). A `comeni-core` artifact design question, and Plan 3's first task |
| Model fills for prose holes | [#70](https://github.com/comeni-project/Comeni-Labs/issues/70). `priority_because` is the one free-prose value that lands in the registry, and it is the one nothing can check |
| Goal extraction (door 1) | A different subsystem, a different egress door, and genuinely a free-text problem — see §4.3 |
| A `--no-ai` flag | §1.1 |

---

## 3. The six decisions, and the arguments behind them

Taken 2026-08-17 with the operator, before any code was read for implementation.

### 3.1 Candidate-bearing holes only

A hole with candidates is **mechanically checkable**: `candidates.for_field` reads the layer
stack, `Hole.legal` refuses anything outside it, and invariant 7 is enforced when the value is
*written* rather than when the file is read. A model asked *which of these declared types* cannot
invent one that is not on the list.

A hole without candidates is free text and nothing can check it. Deferred to
[#70](https://github.com/comeni-project/Comeni-Labs/issues/70).

**An asymmetry that makes this narrower than it first appears.** `contract_from` reads only
`filled.value`; **`FilledValue.why` is discarded at land time.** So a model's prose *justification*
for a checkable value never reaches the registry — it is reviewer-facing and lives in the draft.
The only model prose that could become registry data is `priority_because`, which is exactly what
#70 gates.

### 3.2 A model fill lands as an answer, marked model-filled

Not as a proposal needing acceptance. Three reasons:

- **No schema change at all.** `Filler.MODEL` exists, `FilledValue.by` carries the model id, and
  `assemble._drafted_by` already writes it into `Provenance.drafted_by` — a field every contract
  has carried since the first one.
- **The approval gate already exists downstream.** `land` opens a branch in a registry checkout
  and refuses the default branch; a human approves there. That is invariant 2's approval step,
  and it is a diff review either way.
- **A proposal state is a state machine `Hole` does not have**, threading through `scaffold`,
  `ops`, both transports and the golden tests.

The honesty cost is paid by display rather than by state: `forge show` marks which fills a model
made, and `Provenance.drafted_by` names the model in the landed file.

### 3.3 `ModuleSpec` gains line numbers, before the filler

`sources/nfcore.py` builds **one identical excerpt for every fact**:

```python
def fact(value: object) -> Fact:
    return Fact(value=value, evidence=Excerpt(locator=at, text=f"{spec.process} in main.nf"))
```

Every fact carries `locator="modules/nf-core/fastqc/main.nf"` and
`text="FASTQC in main.nf"`. `Excerpt`'s own docstring already calls this out: a human clicks
through, and **a model given that string learns nothing.**

`ModuleSpec.parse` is regex-based and discards positions. It gains them, and `nfcore.py` builds a
distinct excerpt per fact quoting the line it came from — eight facts always, plus `container`
and `documented_inputs` where the module has them. This is a change to a **pure** package
(`mendel-compiler`), so it runs under `make verify` rather than `make check`.

**Scope: positions and per-fact excerpts only.** `conformance.py` is untouched and gains nothing
in this phase — wiring line numbers into the `MD01xx` diagnostics moves message text, golden
output and `docs/reference/diagnostics.md`, and is worth its own change. The positions sit there
for it.

**Why before rather than after.** Prompt work tuned against evidence that carries no information
is work aimed at the wrong target, and the evidence is the input a filler is *most* sensitive to.

### 3.4 `mendel-ai` holds the client, not the resolver

See §2. The seam it exposes is §4.

### 3.5 `forge fill <target> --model`

Extends the existing verb rather than adding one, because §3.2 decided a model fill **is** a fill.
`forge fill fastqc roles --model` does one hole; `forge fill fastqc --model` attempts every
candidate-bearing hole. The documented loop stays six steps.

`draft` stays deterministic and takes no model flag — the golden scaffold test pins its output on
the `NoFiller` path and the two modes must stay cleanly separable.

### 3.6 `sealed` makes no forge model call

The profile table's logic applied straight. Under `sealed` the prompt door is closed and tier 4
blocks the build; a forge that reached a provider anyway would be the one inconsistency.

---

## 4. `mendel-ai`

### 4.1 Dependencies and the arrow

LiteLLM, Pydantic, and `comeni-core` **for `coded()` only** — no Mendel domain types. The package
speaks in strings, which is what lets the ambiguity resolver reuse it unchanged.

`IMPURE_PACKAGES` in `tests/test_purity.py` gains it. This is self-forcing:
`test_every_package_is_classified` fails the moment the directory exists and is unlisted, and the
list's docstring already records that `mendel-ai` is *deliberately* absent until then (A67, #31 —
a name matching no directory is a guard nobody runs).

### 4.2 The surface

**Closed choice, and nothing else.** There is no free-text generation call in the package.

```python
def choose_one(question: str, options: list[Option], evidence: list[str]) -> Choice | None
def choose_many(question: str, options: list[Option], evidence: list[str]) -> Choices | None
```

`Option` is a value plus a note saying where it is declared. `Choice` carries the picked value and
a free-text `why`; `Choices` carries several values and one `why`. **`None` stays legal** — a
filler that always answers is a filler that invents, and `ports.py` already says so.

**Two methods rather than one, because some holes are list-valued.** `roles` and
`produces[].state` take several members from one closed set — which is why `Hole.legal` checks
member by member, and why a single-value return cannot fill them. The future `AmbiguityResolver`
uses `choose_one` only; `Resolution.chosen` is singular.

**The narrowness is doing work.** A package that cannot generate prose cannot quietly start
writing `priority_because`. Adding free-text generation is then a reviewable change to a package
whose whole surface is two functions, which is the gate #70 describes.

### 4.3 The known future cost

Goal extraction (door 1) **is** a free-text problem and will need a second primitive. That is a
real future change, and it is the right shape for one: door 1 is the taint source with its own
protection-profile rules, and it deserves a reviewed addition rather than riding in on a generic
API that existed for convenience.

### 4.4 The three lanes

Invariant 13: self-hosted is not a degraded tier, so the lanes are **one code path with different
config**, never three branches. A `ModelAccess` config carries a model id, an optional `base_url`
and a key — BYO key, a local OpenAI-compatible endpoint (Ollama and vLLM both qualify), or hosted.

**Invariant 12 is enforced by shape.** The config has no OAuth field, so there is nowhere to put a
Claude Pro/Max subscription token. A ban enforced by having nowhere to write the value is worth
more than one enforced by a check.

---

## 5. The forge side

`mendel_forge/filler.py` — `ModelFiller`, implementing `HoleFiller`:

- A hole with no candidates is **declined**, not attempted (§3.1, #70).
- Otherwise the hole becomes a question, its candidates become options, and its evidence plus the
  observation's prose become the evidence list.
- **Validated twice**: the client refuses a value outside the options it handed over, and
  `hole.legal()` refuses it again on the way in. The second is not redundant — it is the check
  that already exists for human fills, and routing model fills through it means one rule.
- Returns `FilledValue(filler=Filler.MODEL, by=<model id>, why=<the model's rationale>)`, which
  reaches `Provenance.drafted_by` through the existing `_drafted_by`.

### 5.1 Data flow

```
forge fill fastqc --model
  → ops.fill(FillRequest(..., model=...))
  → workspace loads the scaffold
  → for each candidate-bearing hole: ModelFiller.fill
  → scaffold persisted after each fill
  → FillResult reports filled / declined / refused, per hole
```

**Persistence per fill, not per batch.** If the provider dies after eight of fifteen holes, the
eight are kept. All-or-nothing would make a flaky network cost the whole draft, and the draft is
the thing the forge exists to accumulate.

---

## 6. Error handling

New `MA00xx` diagnostics through `coded()`, with `emitted_by: ai`. At minimum: no model
configured (naming the config it wanted), authentication failure, timeout, and **a model returning
a value outside its options**.

The ownership guard accepts any `[A-Z]{2}\d{4}` prefix since Phase 1's first correction, so no
guard changes. But both directions of `tests/test_diagnostics_ownership.py` apply: a code must be
**emitted** in the same change that declares it, or `test_every_declared_code_is_emitted` goes
red. No reserving an `MA` band ahead of use.

---

## 7. Testing

- **A record/replay fixture harness in `mendel-ai`**, fixtures committed to the repo — the
  approach `CLAUDE.md` already specifies for this package. Every later AI subsystem inherits it,
  which is most of why it is worth building carefully here.
- **A guard that no test reaches a live model.** `CLAUDE.md` states the rule; nothing currently
  enforces it, because until now there was no model to reach.
- **The golden scaffold test stays pinned to `NoFiller`.** A model-filled draft is not
  golden-testable and should not be.
- **Determinism is not claimed for model fills**, and the spec says so where a reader will meet
  it. "Same goal in → same pipeline out" is the resolver and compiler; the forge has never been
  in that claim.

---

## 8. Two weaknesses this phase does not close

Recorded because Phase 1's handoff recorded them and neither is fixed here.

**`MF0005` is load-bearing and gets more so.** Rung 4 is a transcription check when the module was
forge-generated — contract and module descend from one `Observation`, so their agreement proves
the two code paths match, not that either is right. Today `MF0005` marks a script body unfilled
and refuses. **A model that writes a plausible command line produces a module that launches and
does the wrong thing, and `-stub-run` cannot see it.** The script body is a prose hole, so #70
gates it — but if #70 is ever picked up, the script body needs a rung the ladder does not have,
decided separately from `priority_because`.

**Rung 5 warns rather than refuses**, because a laboratory adding a tool before the goal that
needs it is being reasonable. Unchanged.

---

## 9. Task shape

Roughly fourteen, in dependency order: `ModuleSpec` positions → per-fact excerpts → `mendel-ai`
skeleton and classification → `ModelAccess` and the lanes → the client and the two choose calls →
`MA` diagnostics → the fixture harness and the live-model guard → `ModelFiller` → `ops.fill`'s
model mode → CLI flag → HTTP surface → `forge show` marking → docs (§1.1, `ARCHITECTURE.md` §10,
the guide) → journal.

**The two expected to run long** are the fixture harness and `ModuleSpec` positions — regex
parsing that currently discards positions has to start keeping them without changing what it
parses. Per `CLAUDE.md`, an estimate wrong by more than about double is a decision point: say the
new number, say what changed, offer the choice.

**Expect to correct this spec while executing it.** Phase 1's plan needed five corrections and two
were found only by running the loop by hand rather than by reading it. Run the thing you built
before believing the tests.

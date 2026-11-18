# The invariants, and why each one exists

`CLAUDE.md` states each invariant in one line. **This page holds the argument**: why the rule
exists, what it protects, and where it was once defeated. Violating any of these breaks the
product claim, not just a test.

Moved here from `CLAUDE.md` on 2026-09-28 (#118), word for word where still true. A citation to a
design document deleted on 2026-09-02 is given as `git show 83c873d^:<path>`, which prints the
file as it was.

## The invariants

Violating any of these breaks the product claim, not just a test.

### 1. The pure packages do not reach the network

Two partial guards, and the claim is their union — say *do not*, never *cannot*. A
static AST scan (`tests/guards/test_purity.py`) rejects the imports, the dynamic import forms, bare
`exec`/`eval`/`compile`, and a module reached as an attribute of an allowed one; a runtime
assertion (`tests/guards/test_purity_runtime.py`) installs an audit hook over a real build and fails
if any socket or process event comes from a frame in those packages. Neither is complete: the
scan cannot see a two-link attribute chain or a `getattr`, and the hook only covers code a
build reaches. **Audit A1 defeated the scan alone** — a file importing only `pathlib` and
`typing` reached `os.system` via `pathlib.os` and delivered a serialised `Goal` over TCP while
the guard reported green. **Audit A17 then defeated both**, with a libc socket obtained
through `ctypes`: FFI raises `ctypes.dlopen`/`dlsym` rather than any `socket.*` event, so it
was outside the union rather than a gap in either half. `ctypes` is now banned statically and
watched at runtime — a pure package has no legitimate FFI need, which is what makes that entry
costless in a way `subprocess` never could be. If a change to those packages seems to need
such an import, the design is wrong.
**`wiener-core` joined on 2026-08-24** (`git show 83c873d^:docs/design/wiener.md` §3.1), and it is the first
time this list has grown. A fold over events has no legitimate need to open a socket, which
is the same argument that made `ctypes` costless — and it is load-bearing in a place nobody
planned: **the OpenTelemetry SDK is a network client**, so this guard is what keeps the span
*mapping* pure and the *export* on the other side of the line, without anybody having to
remember. What it does **not** yet cover is a clock: `datetime` is on that package's
allowlist for the class and must never be `datetime.now`, because §6.1's claim — same events
in, same decisions out — dies the first week one is read inside the fold. The allowlist
cannot express *this name but not that attribute*, so a separate scan holds it.

**`mendel-authoring` joined on 2026-10-04** (14.7.8, the consultant build). It holds the
conversation's protocol, the diagram the builder runs, and the interpreter that runs it; the
shell (`mendel-api`) binds handlers to it and stores where each session rests. Its allowlist adds
no name another pure package does not already have: a protocol that knew a database, a queue or a
model would be the shell under the core's name, and the guard is where that is refused.

### 2. AI authors artifacts offline; humans approve; runtime is pure lookup

Contracts, rules and vocabulary states are drafted outside the build — by hand today, and by
the forge once it is rebuilt (`docs/superpowers/specs/2026-10-19-forge-mvp-design.md`) — and a
person approves them into the registry layer. Nothing writes there automatically.

### 3. Runtime AI is confined to declared points

They are the builder agent (since #463 it is both the conversation that becomes a goal and
tier-4 resolution) and compiler repair (bounded to 3 attempts). Nothing else calls a model.
The agent reads the person's words and chooses through tools; every choice it makes is recorded
as the AI's, at tier 4 with the model as its source, with its reason, and flagged for review. A
pipeline it built records both points (`AiPoint.PROMPT`, `AiPoint.TIER_4`). How it works is
[the builder agent page](builder-agent.md). A new point is declared like these: an `AiPoint`, a
door, a prompt file and an `ai_invocation` row.

### 4. A tier-3 rule miss demotes to tier 4. It never calls a model inside tier 3

That keeps
the tier labels meaningful and the common case free and reproducible.

### 5. Repair patches the IR and re-emits. It never edits generated `.nf` text

Text patching
is a last resort that sets `PipelineIR.diverged = True` and is surfaced loudly.

### 6. Tier 4 is always flagged, even at high model confidence

This is the honesty mechanism
and the difference from a chat window.

### 7. Vocabularies are closed

A contract using an undeclared state fails to load. New states
arrive by review as data changes, never code changes.

### 8. Routing ties are ambiguity, not a coin flip

If several contracts tie after
`(-priority, id)` ordering, demote to tier 4 rather than picking arbitrarily.

### 9. Every ambiguity emits a `DecisionRecord`

That includes one resolved by `FlagOnlyResolver`.
Records are replayed on rerun rather than re-asking the model — that is how determinism
survives having a model in the loop.

### 10. Determinism is a test, not an aspiration

Same `Goal` → byte-identical `.nf`.

### 11. The registry is a stack

A public curated base, then private overlays. A layer is a
**directory of declared files, each of which says what it is** — a `declares:` line
naming one of `DeclaredKind`, and for a vocabulary or a measurement an `id:` beside it.
**The layout is free**, and the convention the public registry uses is to group a tool's
files together: `registry/tools/nf-core/star/align/contract.yml` beside the type it produces.
Every kind stacks **through one mechanism** — `comeni_core.layered.stack()`,
parameterised by a `Kind` that declares only how its files parse, key and merge.
Hand-written loaders disagreeing on six axes is what audit root B was.
**The count lives in `DeclaredKind` and not in this sentence.** It said "four" from Plan
1.9 to Plan 1.15 and would have been wrong the day a fifth kind arrived, which is A33's
lesson and A71/A72's: a number repeated in prose is a number that goes stale while
everything around it stays true. `len(DeclaredKind)` is the honest count.
**What weakened, recorded rather than discovered** (comeni-registry#1): the directory used
to make a misfiled document impossible — a *contracts* directory held contracts, and a
misspelled *contract* directory was caught by `MD0003` because nothing read it. That was prevention *by
construction*, and a misspelled `declares:` can only be *detected*, which is `MD0011`.
Same class of error, one guarantee fewer, and `MD0003` is retired rather than emptied.
Load a stack through `mendel_resolver.layers.load()`, never by hand: the kinds are not
independent, and the wrong order fails inside a contract rather than at the caller. Every
loader takes **layer roots**, never a directory of one kind: a loader handed a slice of a
layer cannot know which layer it is reading, which is why displacement went unrecorded.
A higher layer sharing a **module key** (the contract ID minus `@version`) displaces every
lower-layer contract for that module. A different module key is an ordinary candidate and
obeys invariant 8. Keying on the module key rather than the full ID is what lets a lab pin
`@1.22.0` over `@1.21.0` without the two tying — a version bump is not ambiguity.
**Identity is `Layer.index`, never `Layer.name`**: two layers may share a name and the
lockfile's own docstring says `registry/` over `registry/` is a day-one collision.
Replacement is legal and **`Displacement` is the record that it happened** — one shape for
every kind, carried on `PipelineIR.displaced` and printed in the `OVERLAY` block, so a
measurement or a vocabulary type finally has somewhere to be reported. `states:` replaces a
type's states, `add_states:` extends them; `values:` and `add_values:` say the same pair for
a measurement. Never let an installed overlay reroute a pipeline silently.

### 12. Retired: subscription sign-in is allowed

This was "no subscription OAuth". The operator dropped it on 2026-11-05 (#457) so that a paid
ChatGPT subscription can answer forge calls through LiteLLM's ChatGPT provider. The number
stays so that references to later invariants keep their meaning. Anthropic's consumer terms
still forbid Claude Pro/Max tokens in third-party tools; that is the provider's rule, not this
repository's.

### 13. Self-hosted is not a degraded tier

Same registry, same resolver, byte-identical
output. The hosted instance sells convenience, never capability. Anything that would only
work on our infrastructure is a design error.

### 14. Data reaches a model through declared doors only

Each door carries one declared payload type, listed in `comeni_core.egress.boundaries.BOUNDARIES`,
on one of two paths (`BoundaryFlow`): the **pipeline** path (the builder agent, compiler repair,
publication) and the **forge** path. `tests/guards/test_egress.py` holds the list literally, so
widening the boundary means editing a test that says *these are all the ways data leaves*.

**Why:** a declared input type is what makes a model call reproducible and auditable. It lets a
response be recorded and replayed, a prompt be held to a golden file, and `admit()` check an
answer against the question that was asked. *A reader can see exactly which parts a model
touched* is only true if there is a boundary to point at.

**The rules a payload follows:** no field is `Any`, `object` or a plain `str`. Every string is a
declared id alias, or carries a mark: `Mark.FREE_TEXT` for what a person typed or a tool printed,
`Mark.SAMPLE` for something of a person's data. The guard is an allowlist
(`test_every_payload_field_is_a_declared_shape`), and `FREE_TEXT_FIELDS` and `SAMPLE_FIELDS` in
`tests/support/egress.py` are the counts. Only the builder agent's door may reach a sample, and
only by name. A prompt composed only from public sources (registry files, vendored modules) is not
a door. Publication carries the `Pipeline` itself, so what a person reads before publishing and
what crosses cannot disagree; it is the door with no undo. Transport metadata is not a door
either: the builder agent tells an OpenAI-shaped provider which conversation a call continues,
for its prompt cache, with a digest of the session id (`agent.loop.cache_key`, #555), never the
id itself or anything a person wrote.

### 15. A pipeline never holds a person's data

No goal, `pipeline.yml`, emitted workflow or log holds a path, a sample's name or anything a
file contains. A pipeline holds **shapes**: type ids, states and declared measurements; its
inputs are typed sockets the run fills. `MeasurementRegistry.profile()` is the only validating
constructor of a `DataProfile`, and `tests/guards/test_construction.py` holds that nothing else
builds one: delete that call and `profile: {sample_name: ...}` builds cleanly, which is how it was
watched failing.

**A person's files are read where they are, never copied** (#511). Comeni reads only under the
installation's data roots, mounted read-only, and every path is resolved and checked (`MI0221`).
To measure a sample it reads at most the first 4 MB of each file. An analysis's data
(`analysis_data`) keeps the folders ticked, the files by path, the samples by name and what was
measured on each, and is deleted with the analysis. **Facts about the data are derived from it at
every read, never logged as decisions**: change the data and the facts change. A run's params are
built from it when the run is sent, and Wiener keeps them in the run's own directory, never in a
table (#273). The builder agent's model may read sample names, so it can talk about them; never a
path or a file's contents.

## The four tiers

Every module choice and parameter exits at exactly one tier and carries it forever.

| Tier | Fires when | Review level | UI |
|---|---|---|---|
| 1 structural | no choice exists — inputs force it | `none` | silent |
| 2 convention | a documented default exists | `none` | green |
| 3 data-profiled | a declared rule matched measured data | `advisory` | yellow |
| 4 ambiguous | no rule matched | `required` | red |

Tier 3 is yellow rather than silent on purpose: a rule match is only as good as the
measurement behind it. Yellow means "the machinery worked, check the premise."

**Tiers are the engine's; the interface speaks sources** (#511). Every value on screen carries
where it came from: MEASURED, RULE, DEFAULT, YOU, AI or NOT SET. A tier-4 choice is AI until a
person keeps it, and NOT SET while open; the tier stays in `pipeline.yml` for review and replay.

Module choices carry a tier too, in `IRNode.selection`, and `needs_review()` lists a tier-4 one
by node rather than only as a `DecisionRecord` a reviewer would have to join by hand.

## Public claims

**Say "a pipeline never holds a person's data", never "anonymised".** Genetic data are not
reliably anonymisable, and pseudonymised data stays personal data under GDPR Art. 9.

**We are a tool; the lab is the manufacturer.** Never claim IVDR/CLIA/CAP/ISO 15189 compliance —
those attach to a laboratory's processes. Mendel supplies the documentation substrate. Curated
means reference material a lab validates, never a validated test, because distributing across
legal entities forfeits the IVDR Art. 5(5) in-house exemption.

A privacy posture for a laboratory (which data a model may see) is not built; it is #71, and it
is built as one setting when a laboratory asks for one.

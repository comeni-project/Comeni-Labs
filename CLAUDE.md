# Comeni Labs

Deterministic bioinformatics pipeline construction. A researcher describes an analysis in
plain language; **Mendel** resolves it to a Nextflow pipeline where every decision traces to
a constraint, a convention, a measurement, or an explicitly flagged judgement call.

The product claim, which every design decision serves:

> Same goal in → same pipeline out, and nothing was guessed silently.

## Current state

**No code yet.** Documentation precedes implementation deliberately. Start from:

| Read this | For |
|---|---|
| `docs/superpowers/specs/2026-08-02-mendel-design.md` | the architecture. **Read before writing code.** |
| `docs/superpowers/specs/2026-08-02-comeni-federation-design.md` | provider access, registry stacking, pipeline publication, licensing |
| `docs/superpowers/specs/2026-08-03-clinical-data-protection-design.md` | clinical use, the egress boundary, protection profiles, lockfile scope |
| `docs/superpowers/plans/2026-08-02-mendel-deterministic-spine.md` | Plan 1 — 13 TDD tasks, zero AI. Start here. |
| `docs/superpowers/plans/2026-08-02-mendel-ai-and-forge.md` | Plan 2 — AI adapters + contract forge |
| `docs/superpowers/plans/2026-08-02-mendel-api-and-dashboard.md` | Plan 3 — FastAPI + React dashboard |
| `docs/design/*.md` + `.html` | visual design, with self-contained mockups |

## How to start implementing — decided 2026-08-02, read this first

> **Use `superpowers:executing-plans`. Subagents for review and design when needed.**

That is the operator's instruction, not a suggestion. Concretely:

- **Drive the plan yourself** with `superpowers:executing-plans`, sequentially, task by task.
  Do **not** use `subagent-driven-development` to farm out implementation tasks.
- **Subagents are for review and design only**, and only when the work calls for it — a
  second opinion on a design question, a review pass over something already written. Never
  as the default way to write code.
- **Work in the worktree**, not the main checkout:
  `.worktrees/plan-1-spine` on branch `plan-1-spine`. Fast-forward it onto `main` first.
- **Start with Plan 1**, task 1 (the AST purity guard), and go in order.

**Toolchain was verified on 2026-08-02** — do not re-audit it: `uv` 0.11.18, Python 3.12.12
(the plan's floor exactly), Nextflow 25.10.4, Java 21, Docker 29.6.2. `nf-core` CLI is not
installed and does not need to be; `uvx nf-core` works and github.com/nf-core/modules is
reachable.

**Task 11 ships a known defect on purpose.** `_calls` gives every node with no incoming edge
the same `ch_reads` channel — right for `FASTQC` and `TRIMGALORE`, wrong for
`STAR_GENOMEGENERATE`, which needs the GTF channel. Task 12's `-stub-run` gate is what
surfaces it. Fix it *then*, test-first, by keying entry channels on the port's `type_id`.
Do not pre-empt it; the failing gate is the point.

**Do not write Plan 2.5 yet.** It is designed (federation spec §8: lockfiles, `mendel
publish`, `mendel upgrade`, the pipeline catalogue, the pipeline review screens, and the
registry split out of `examples/`) but deliberately unwritten, and its absence is not an
oversight. Its code steps reference `PipelineIR.registry_layers`, `PipelineIR.shadowed`,
`DecisionRecord` fields and the lockfile shape — all of which exist only as text inside Plan 1
until Plan 1 builds them. Plans 2 and 3 were written ahead of Plan 1 in one sitting and the
cross-plan review found three defects, two of them plans referencing things that had drifted;
Task 5's own signature changed shape mid-implementation today. **Write Plan 2.5 after Plan 1
runs green, against real types rather than predicted ones.**

## The three Labs

Named for people who made a hard thing legible or dependable — after Comenius, following
Rosalind from Franklin.

- **Mendel** (Lab X) — the pipeline builder. Deterministic laws from observed data, which is
  what the tier-3 rule tables are. **The only one being built.**
- **Wiener** (Lab Y) — cloud execution and monitoring. Cybernetics: control through feedback.
- **Nightingale** (Lab Z) — data analysis. Parked until Mendel exists.

`Comeni-Code` is a separate repo: the learning platform. Do not build it here.

## Invariants

Violating any of these breaks the product claim, not just a test.

1. **`comeni-core`, `mendel-resolver` and `mendel-compiler` import no web framework, no HTTP
   client, and no LLM library.** Enforced by an AST test in `tests/test_purity.py`. If a
   change to those packages seems to need such an import, the design is wrong.
2. **AI authors artifacts offline; humans approve; runtime is pure lookup.** The forge drafts
   contracts, rules and vocabulary states — a person approves them into `contracts/`,
   `rules/`, `vocabularies/`. Nothing writes there automatically.
3. **Runtime AI is confined to three declared points**: prompt → goal extraction (user
   corrects the result before anything runs), tier-4 resolution (always flagged, always
   recorded), and compiler repair (bounded to 3 attempts). Nothing else calls a model.
4. **A tier-3 rule miss demotes to tier 4. It never calls a model inside tier 3.** That keeps
   the tier labels meaningful and the common case free and reproducible.
5. **Repair patches the IR and re-emits. It never edits generated `.nf` text.** Text patching
   is a last resort that sets `PipelineIR.diverged = True` and is surfaced loudly.
6. **Tier 4 is always flagged, even at high model confidence.** This is the honesty mechanism
   and the difference from a chat window.
7. **Vocabularies are closed.** A contract using an undeclared state fails to load. New states
   arrive through the forge's approval queue as reviewed data changes, never code changes.
8. **Routing ties are ambiguity, not a coin flip.** If several contracts tie after
   `(-priority, id)` ordering, demote to tier 4 rather than picking arbitrarily.
9. **Every ambiguity emits a `DecisionRecord`**, including when resolved by `FlagOnlyResolver`.
   Records are replayed on rerun rather than re-asking the model — that is how determinism
   survives having a model in the loop.
10. **Determinism is a test, not an aspiration.** Same `Goal` → byte-identical `.nf`.
11. **The registry is a stack**: public curated base, then private overlays. A higher layer
    sharing a **module key** (the contract ID minus `@version`) shadows every lower-layer
    contract for that module and writes a `ShadowRecord`. A different module key is an
    ordinary candidate and obeys invariant 8. Keying on the module key rather than the full ID
    is what lets a lab pin `@1.22.0` over `@1.21.0` without the two tying — a version bump is
    not ambiguity. Never let an installed overlay reroute a pipeline silently.
12. **No subscription OAuth.** Claude Pro/Max tokens in third-party tools violate Anthropic's
    Consumer ToS (documented 2026-02-19, enforced since 2026-01). API keys or local models only.
13. **Self-hosted is not a degraded tier.** Same registry, same resolver, byte-identical
    output. The hosted instance sells convenience, never capability. Anything that would only
    work on our infrastructure is a design error.
14. **Data leaves through four declared doors and no others** — goal extraction, tier-4
    resolution, compiler repair, publication. Each carries one declared payload type, and
    exactly two fields across the whole surface may hold free text: `PromptRequest.prompt` and
    `GateFailure.tool_message`. Everything else is closed vocabulary; no payload may carry an
    `Any`-typed field, and none may carry a plain `str` — every string is a declared ID alias or
    marked `FreeText`, because a bare `str` bypasses the marker in one line and a prompt fits in
    it perfectly. Enforced by `tests/test_egress.py`, which holds both lists literally,
    so widening the boundary means editing a test that says these are all the ways data leaves.
    Publication is the door with no undo.
15. **Mendel does not receive patient data.** No input accepts a sample identifier, filename or
    path. `Goal` holds type IDs, states and four measurements — a shape, not data. Profiling
    happens where the data is; the emitted pipeline references `params.input` as a placeholder
    the lab fills at run time. This is currently true by accident and is one plausible dashboard
    feature away from being false.

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

## The three protection profiles

Clinical labs are a target user, not a later market. Three ladders now exist and must never be
conflated: **four resolution tiers** (above), **three visibility tiers** (private / published /
curated, federation §4.2), and **three protection profiles** — below.

| | `open` | `guarded` (default) | `sealed` |
|---|---|---|---|
| prompt door | sends | shows the payload, waits for confirmation | closed — typed goals only |
| `GateFailure.tool_message` | included | `None` | `None` |
| repair | proposes and applies | proposes and applies | proposes only; a human applies |
| tier 4 | flags | flags | **blocks the build** |
| attribution | optional | when available | required |
| reference pinning | tags | tags | digests required |

Never configurable at any level: the four doors, typed payloads, an `EgressRecord` per crossing,
tier 4 always flagged, typed-only publish bundles, no patient data received. `guarded` is the
default because the unconfigured install is the one most likely to exist.

**Say "Mendel does not receive patient data" — never "anonymised".** Genetic data are not
reliably anonymisable and pseudonymised data stays personal data under GDPR Art. 9. The accurate
claim is also the stronger one: minimisation by non-receipt.

**Scrubbing was considered and rejected.** Safe Harbor needs all 18 identifier classes gone;
NLP de-identification leaves false negatives, and it fails silently. Pattern matching survives
only inverted, in `guarded`, where it halts the send and asks a human.

**We are a tool; the lab is the manufacturer.** Never claim IVDR/CLIA/CAP/ISO 15189 compliance —
those attach to a laboratory's processes. Mendel supplies the documentation substrate. Curated
means reference material a lab validates, never a validated test, because distributing across
legal entities forfeits the IVDR Art. 5(5) in-house exemption.

## Architecture

```
packages/
  comeni-core/       types, contract schema, pipeline IR, registry     PURE
  mendel-resolver/   four-tier ladder, rules, routing, ports           PURE
  mendel-compiler/   IR → Nextflow DSL2, validation gates, repair      PURE
  mendel-ai/         LiteLLM port implementations                      impure
  mendel-forge/      ingestion, contract drafting, approval queue      impure
  mendel-api/        FastAPI surface                                   impure
examples/      vocabularies/ rules/ contracts/ + rnaseq-goal.yml — TEST FIXTURES ONLY
modules/       vendored nf-core module code — root-level, does not move at Plan 2.5
frontend/      React + TS + Vite + Tailwind SPA
```

**The registry is a separate repository.** `comeni-registry` holds the real `contracts/`,
`rules/` and `vocabularies/` under CC-BY-4.0 with signed tags; this repo holds only enough
hand-written data under `examples/` for tests to run. The split happens at Plan 2.5 — until
then, do not treat `examples/` as a registry or add contracts there expecting them to ship.
`Registry.load()` takes paths, which is what keeps the move cheap. It globs `*.yml` recursively
under each layer, so `examples/contracts/` holds contracts and nothing else — the goal file sits
one level up for that reason.

Ports and adapters: the pure packages declare `Protocol`s in
`mendel_resolver/ports.py`; `mendel-ai` implements them. The dependency arrow points
`mendel-ai → mendel-resolver`, never the reverse.

`comeni-core` keeps the platform name rather than the product name because its IR is the
interface Wiener will consume.

## Distribution

Open source, self-hostable, public registry. Revenue is the hosted service only.

**Model access — three lanes.** `--no-ai` (none; what CI runs), self-hosted (BYO API key, or
a local model over an OpenAI-compatible endpoint — Ollama and vLLM both qualify), and
Comeni-hosted (our keys). `mendel-ai` reaches all of them through one LiteLLM adapter behind
the `mendel_resolver.ports` protocols. **The `--no-ai` flag itself arrives with Plan 2** —
through Plan 1 there is no AI path to switch off, so every build is already that lane.

**Registry.** Public curated base — the `comeni-registry` repo, data files with signed tags —
plus zero or more private overlays via repeated `--registry`. A lab that never publishes is
the normal case. Contributing upstream is a proposal into the forge queue.

**Pipelines are publishable artifacts**: `Goal` + `PipelineIR` + `DecisionRecord[]` + a
lockfile pinning contract digests and module versions. Three tiers — private, published
(mechanical gate: stub-run then `-profile test`), curated (**a named human signs off**;
never mechanical). Editing a curated pipeline replays every untouched decision from its
record, so only what you touched can move. See the federation spec.

**Telemetry is opt-in and off by default.** Invariant 1 makes this structural rather than a
promise: the pure packages cannot import an HTTP client, so telemetry can only live in
`mendel-api`. Anything that would put a network call in `comeni-core`, `mendel-resolver` or
`mendel-compiler` fails `tests/test_purity.py`, which is the intended outcome.

**Licences.** Code Apache-2.0 (`LICENSE`). Registry data CC-BY-4.0 (`LICENSE-DATA`) —
contracts cite papers, so attribution matters. Vendored nf-core modules keep their own.

**Repo status, decided 2026-08-02.** Pushed to `github.com/rafaelmdc/Comeni-Labs`, **private
until Plan 1 runs green**, then public. It is meant to move to a GitHub **org** — deferred,
not dropped, because `comeni` is taken by an existing GitHub *user* and users and orgs share
one namespace, so the org needs a suffixed name (`comeni-project` was the leading candidate).
**Transfer before publishing anything that hardcodes clone URLs.**

**Two things to do before flipping it public**, neither of which is urgent while it is private:

1. There is no `README`, `CONTRIBUTING` or `CODE_OF_CONDUCT`. An Apache-2.0 repo wants them.
2. **Re-read how these docs describe pegi3s / auto-phylo.** The Mendel spec §13 says their
   implementation "is not a model to follow", and the forge design says nearly every field
   from their sources is inferred. Both are fair and diplomatically worded — but Rafael is
   joining that lab, and going public means they can read it. His call, made with eyes open,
   not discovered afterwards.

## Commands

```bash
uv sync                          # set up the workspace
uv run pytest -v                 # all tests; no test may call a live model
uv run ruff check .              # lint (line length 100)
uv run ruff format .
uv run pytest tests/test_purity.py   # the invariant-1 guard

# build a pipeline from a typed goal, no AI involved
uv run mendel build --goal examples/rnaseq-goal.yml --out build/ --gate stub

# same build, with the lab's private contracts stacked over the public registry
uv run mendel build --goal examples/rnaseq-goal.yml \
  --registry examples/contracts --registry ./lab-contracts --out build/

# the forge
uv run forge ingest --modules modules/
uv run forge pending
uv run forge approve nf-core/samtools-sort.yml --by "$USER"
```

`make test`, `make lint`, `make dev`, `make migrate` wrap the common ones.

## v1 success criterion

From a plain-language prompt plus a test dataset, Mendel emits Nextflow that runs green on
the nf-core test profile and produces a counts matrix. Target is the **RNA-seq spine** —
~15–20 modules on the canonical path, *not* the full `nf-core/rnaseq` decision tree with its
alternative aligners, pseudo-aligners and UMI handling. That breadth is v2.

## Gotchas

- **`nf-core` `meta.yml` is a scaffold, not a contract.** It declares outputs as
  `type: file` with a filename pattern; `samtools/sort`'s output and `star/align`'s
  `bam_unsorted` are both `type: file, *.bam`. "Sorted" exists only in the English
  description. The semantic `state` overlay is the missing ~40% and is what routing depends
  on.
- **`frozenset` has no stable order.** `IREdge.states` carries a `field_serializer` that
  sorts on output. Byte-identical emission is a hard requirement; anything new that
  serialises a set needs the same treatment.
- **`-stub-run` is the fast validation tier.** nf-core modules all define stub blocks, so the
  whole DAG executes with dummy outputs in seconds. Iterate the repair loop there; only the
  final candidate pays for `-profile test`.
- **`--no-ai` must keep working forever** once Plan 2 adds it. It is how the deterministic
  guarantee stays testable, and it is the mode CI runs in. `--registry` is repeatable and
  ships in Plan 1, since Task 5 builds the stacking it exposes.
- **Import modules, not symbols, where tests monkeypatch.** `from x import f` binds past a
  later patch of `x.f`.
- **There is no vector memory store, and adding one is a design error.** Mem0/Zep/Letta answer
  "what did this user say before". Mendel's institutional memory is `contracts/`, `rules/`,
  `vocabularies/` and decision records — versioned, approved, diffable, citable. A fuzzy
  recall layer beside them could influence resolution without passing the forge, which breaks
  invariant 2. Federation is registry distribution, solved by git and a lockfile.

## Testing

Mirrors the purity split — this is what makes the determinism claim auditable rather than
rhetorical.

- `core` / `resolver` / `compiler`: **golden-file tests.** Goal in → exact IR out → exact
  `.nf` out. No network, no model, milliseconds. A change in generated Nextflow shows up as a
  reviewable diff in CI.
- `mendel-ai`: contract tests against recorded fixtures committed to the repo.
- End-to-end: `-stub-run` on every commit; full `-profile test` nightly.

## Prior art

`../braidworks` (same author) is the direct ancestor of the typed-routing model: declared
consumes/produces contracts, a registry graph, plan-then-execute separation, and confidence
and review flags carried as data rather than raised as exceptions. Read
`docs/architecture.md` there when the contract model is unclear.

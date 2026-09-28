# Comeni Labs

**One platform for planning, running and watching bioinformatics analyses.** A researcher
describes an analysis, gets a Nextflow pipeline, runs it without touching a cluster, watches it,
and is told what to do when it breaks.

**The loop is describe → build → run → watch**, and that is the priority order for any scope
decision. Describe, build and watch work; run works on a local executor (`k8s` and `awsbatch`
profiles are emitted, not launched). Diagnosing a failure is partial: only `cancel` acts. An
agent that proposes a fix to a pipeline is not built.

**This file is a brief, held to 300 lines by `make doc-sizes`.** What is true right now is
[`docs/notes/now.md`](docs/notes/now.md); why each rule exists is
[`docs/design/invariants.md`](docs/design/invariants.md). History is in the journal, never here.

## What this is, and how to say it

**Semi-deterministic construction.** The engine builds everything it can *prove* from declared
data, then hands out what is left as **typed, addressable questions**: each carries an id
(`produces[0].type_id`), what it asks, why it could not be settled, the legal answers, whether
that list is exhaustive, and a ranked `suggested` when the arithmetic is confident. A model
answers only those, by id, and **cannot produce a value outside the candidate set**, so a reader
can see exactly which parts of a pipeline a model touched and the rest is reproducible without
one. `Question` in `comeni_core/review/` is the type; `Hole` and `Ambiguity` are its two sides.
**When explaining this project, this paragraph comes first.**

> Same goal in → same pipeline out, and nothing was guessed silently.

- **The AI is the engine's primary operator** (decided 2026-08-14). It turns plain language into
  a goal and drives the CLI; `pipeline.yml` is the save file it picks up and re-emits. The model
  produces only a *goal*, and a deterministic engine produces the pipeline. That changes no
  invariant: an agent driving the CLI is a user of it. It does raise the bar for the artifact: a
  person reading a value with no reason sees a blank and asks; a model sees a blank and fills it.
- **Do not say** "a pipeline builder", "AI writes your pipeline", "deterministic pipeline
  construction" (that is how, not what), or lead with **Mendel** or **Wiener**. Those are internal
  engine names (describe/build and run/watch; **Nightingale**, analysis, is not started). A user
  never needs to know them.
- **Do not claim anything about where sequencing data goes on managed cloud.** Non-receipt holds
  for the build path; execution on AWS or a hosted service is undecided.
- **Say "does not receive patient data", never "anonymised".** Never claim IVDR/CLIA/CAP/ISO 15189
  compliance: we are a tool, the lab is the manufacturer. Curated means reference material a lab
  validates, never a validated test.
- `Comeni-Code` (the learning platform) is a separate repository. Do not build it here.
- **The repository is public.** auto-phylo is not discussed (operator's decision, 2026-08-04);
  pegi3s appears only as what is useful about it: ~190 containerised tools, a future forge source.

### Writing documentation

Repo documentation answers *what is this, what can I do with it, how do I start*. Four rules,
each written because it was broken:

1. **Lead with what the reader gets**, never with the mechanism.
2. **Name sections after what somebody does** (build, run, watch, add a tool). No page explains
   its own information architecture.
3. **Do not make a reader learn internal names**: Mendel, Wiener, the forge, `comeni-core`.
4. **No provenance in a task page.** Issue numbers, audit findings and the argument for a decision
   belong in `docs/design/` and `docs/notes/`.

## How we work

- **Where the work is:** [`docs/notes/now.md`](docs/notes/now.md) first, then any entry in
  [`docs/notes/journal/`](docs/notes/journal/) (those are not compacted yet). The task tree is
  GitHub issue **#119** (task → steps → substeps → tasks, each a sub-issue). Never point at a
  journal entry by name; a named pointer is what went stale in August.
- **Every defect gets a GitHub issue first**, mechanical ones too. Mechanical: fix test-first,
  close citing the commit. A **rule or protocol** question: brainstorm, the operator chooses, the
  choice is commented on the issue, then implement. The loop, the labels (`walk`, `mechanical`,
  `protocol`, `decided`) and the decision comment are in
  [`docs/internals/walking.md`](docs/internals/walking.md).
- **Rules are tuned, never forced.** The product's thesis is the balance between flexibility and
  restraint: a rule too strict to function is loosened, one too loose is tightened. Do not make a
  thing work "no matter what".
- **Work on a feature branch, never `main`**: the living pipeline is on `living-pipeline-design`,
  and `main` stays unpushed until it merges.
- **Brainstorm, then spec, then plan, always, before any code.** The operator brainstorms the approach
  (`superpowers:brainstorming`) and approves the written spec. **The plan is not reviewed:** write
  it from the approved spec and execute it.
  Explaining an approach while starting it is not a brainstorm (operator, 2026-09-28). A
  mechanical walk fix needs only a one-paragraph approach the operator approves.
- **Execute plans yourself** with `superpowers:executing-plans`, task by task. **Subagents are for
  review and design only**, never the default way to write code.
- **Plans** live in `docs/superpowers/plans/`, specs in `docs/superpowers/specs/`; finished ones
  go to an archive folder beside them. **Tick each `- [ ]` as it completes.** A step done
  differently is still ticked, with the deviation in the plan's execution record. Do not
  back-fill old plans.
- **Write plans against code** and expect to correct one you are executing: plans here have
  repeatedly predicted types that did not exist.
- **Stop and speak when an estimate breaks by more than about double.** Say the new number, what
  changed, and offer the choice. Describing a bad loop is not communicating; one diagnostic run
  that collects every failure beats ten patch-and-rerun cycles. Present decisions as choices
  with their costs.
- **Walk it, and look at it.** Every driven session has found defects no suite could. Compare a
  screen to its artboard in one viewport (`.design/_compare.html`), never by reading markup.
- **Compact the journal** when a step closes, by
  [`docs/notes/compaction.md`](docs/notes/compaction.md).
- **Guards must be watched failing** against the specific defect. A guard never watched failing
  may be inert (A14, open until every guard has a recorded revert in
  `tests/fixtures/guard-ledger.md`). A comment claiming a guard exists is worse than none: grep
  for the test's name before trusting it.
- **Nothing in a doc is a count.** Counts live where a command derives them: `make check` for tests,
  `make residue` for guard coverage, `len(DeclaredKind)` for kinds, `FREE_TEXT_FIELDS` for egress.
- **Tests:** read `tests/README.md` before adding a file. Ask `support.paths` for the root rather
  than counting `parent.parent`; **a loop is not an assertion**, so assert the collection is
  non-empty first. Pure packages get golden-file tests; model calls use recorded fixtures, never a
  live model; the stub gate runs nightly, not per pull request.

## Invariants

Violating any of these breaks the product claim, not just a test. Each is argued in
[`docs/design/invariants.md`](docs/design/invariants.md).

1. **`comeni-core`, `mendel-resolver`, `mendel-compiler`, `wiener-core` and `dag-core` do not reach
   the network.** Say *do not*, never *cannot*: two partial guards (`test_purity.py`,
   `test_purity_runtime.py`), `ctypes` banned, no `datetime.now` in `wiener-core`.
2. **AI authors artifacts offline; humans approve; runtime is pure lookup.** Nothing writes to a
   registry layer automatically.
3. **Runtime AI is confined to three declared points** (`AiPoint`): goal extraction, tier-4
   resolution, compiler repair (declared, not built). A fourth, characterisation at protection
   level 0, is **designed, not built** (`docs/design/authoring-protocol.md`).
4. **A tier-3 rule miss demotes to tier 4.** It never calls a model inside tier 3.
5. **Repair patches the IR and re-emits**, never the generated `.nf` text.
6. **Tier 4 is always flagged**, even at high model confidence.
7. **Vocabularies are closed.** An undeclared state fails to load; new states arrive through the
   forge's approval queue.
8. **Routing ties are ambiguity**, demoted to tier 4, never a coin flip.
9. **Every ambiguity emits a `DecisionRecord`**, replayed on rerun rather than re-asking a model.
10. **Determinism is a test:** same `Goal` → byte-identical `.nf`.
11. **The registry is a stack** of layers, each a directory of files that declare their own kind,
    loaded through `mendel_resolver.layers.load()`, stacked through `comeni_core.layered.stack()`.
    Identity is `Layer.index`, never `Layer.name`; a replacement is recorded as a `Displacement`.
12. **No subscription OAuth.** API keys or local models only.
13. **Self-hosted is not a degraded tier:** same registry, same resolver, byte-identical output.
14. **Data leaves through declared doors only** (`DOORS`, `DoorPath`), each with one typed payload;
    `FREE_TEXT_FIELDS` in `tests/guards/test_egress.py` is the count. Publication has no undo.
15. **Mendel does not receive patient data.** `DataProfile` is built only by
    `MeasurementRegistry.profile()`. The designed protection level 0 would loosen this for an
    uploaded sample; that is not built.

## The system, briefly

**Tiers.** Every module choice and parameter exits at exactly one tier and keeps it: **1**
structural (silent), **2** convention (green), **3** data-profiled, a declared rule matched a
measured fact (yellow: *check the premise*), **4** ambiguous (red, review required).

**Protection profiles** (`open`, `guarded`, `sealed`) are designed and **none is built** (#71); do
not start them on privacy grounds alone. The consultant's design adds a level **0** (a sample
uploaded, a model may read it) as the MVP's setting; it arrives with substep 14.7.4.

**Packages** (`packages/`): `comeni-core` (types, schema, IR, registry; pure), `mendel-resolver`
(four-tier ladder, rules, routing; pure), `mendel-compiler` (IR → Nextflow, gates; pure),
`dag-core` (graph layout for both canvases; pure), `wiener-core` (the run-state fold; pure),
`comeni-ai` and `mendel-ai` (model transport), `mendel-forge` (sources, scaffolds, holes),
`mendel-api` and `wiener-api` (FastAPI), `comeni-vendor` (fetch a module into a layer). Pure
packages declare `Protocol`s in `mendel_resolver/ports.py`; the arrow points adapter → resolver,
never the reverse.
`frontend/` is React 19 + TS + Vite + Tailwind 4, and **`frontend/src/api/` is generated**
(`make client`), never hand-edited. `ARCHITECTURE.md` describes all of it against real types.

**The registry** is a git submodule at `registry/` (`comeni-registry`), carrying each tool's
module beside its contract (`registry/tools/<org>/<tool>/module/`). `git clone
--recurse-submodules`, or `git submodule update --init`. `pipeline.yml` is the pipeline: every
step and setting with a `why:`, contracts pinned by digest, no paths or timestamps.

**Distribution.** Open source, self-hostable; revenue is the hosted service only. Three model
lanes: none (what CI runs), self-hosted (a key, or a local model over an OpenAI-compatible
endpoint), hosted. Releases are per package, tagged `<package>-v<version>`; read
`docs/internals/releasing.md` before cutting one; GitHub Releases only, no PyPI. Telemetry is
opt-in and off by default, and lives outside the pure packages. GitHub Actions are pinned by SHA
(`tests/repo/test_workflow_pins.py`).
Code is Apache-2.0; registry data CC-BY-4.0.

## Commands

`make help` lists them. `make check` is exactly what CI runs.

```bash
uv sync                          # set up the workspace
make check                       # lint, tests, types, docs, links, doc-paths, doc-sizes (~1 min)
make verify                      # check + the counts matrix + guards; Docker, ~2 min
make static                      # conformance + nextflow lint + preview; no Docker
make guards                      # purity, egress and construction guards
make dev                         # the whole stack, plus Vite on :5173
make migrate && make wiener-migrate
make client                      # regenerate frontend/src/api/ from the APIs
make ai-up OLLAMA_GPU=rocm       # a local model on an AMD card; `make ai-pull MODEL=...`

uv run mendel build --goal examples/rnaseq-goal.yml --out build/ --gate stub
uv run mendel emit build/pipeline.yml --out build/       # no registry, no network
uv run mendel upgrade build/pipeline.yml --dry-run       # re-resolve; --dry-run writes nothing
uv run mendel explain MD0104                             # any diagnostic, at length
uv run mendel conformance --registry registry/           # every contract against its module
uv run comeni-vendor check --registry registry/          # a module/ hand-edited?
uv run comeni-vendor add nf-core:samtools/sort --sha <sha> --licence MIT --registry registry/
uv run mendel publish build/pipeline.yml --gate test     # gate it, stamp the verdict
uv run mendel profile --have fastq.reads --out profile-build/
uv run mendel lint --registry registry/                  # is the layer arranged as it says?
uv run forge draft nf-core:fastqc --name fastqc --version 0.12.1   # sources, discover, show,
uv run forge land fastqc --registry ../comeni-registry --by "$USER" # fill, verify, check, land
# `land` needs --registry: registry/ here is a submodule at a detached HEAD, never a landing site.
uv run comeni-vendor check --registry registry/ --upstream   # has upstream moved? network (#64)
uv run mendel docs --registry registry/ --out /tmp/tool-docs --check
uv run mendel build --goal examples/rnaseq-goal.yml --registry registry/ --registry ./lab --out b/
cd frontend && npx vitest run && npx tsc -b              # tsc -b, never tsc --noEmit
```

**Run `make verify`, not only `make check`, after touching** `resolve.py`, `router.py`, the rules
package, `mendel_compiler/cli/`, `mendel_compiler/emit.py` or `comeni_core/artifact/pipeline.py`:
`make check` deselects the three tests that run a real tool. **Diagnostics** are declared in
`comeni_core/diagnostics.yml` and emitted through `coded()`, never written into a string by hand;
`uv run python tools/generate_diagnostics_doc.py` regenerates the page.

## Gotchas

- **Database tests need their own Postgres.** The Makefile `-include`s `.env`, which beats the
  environment, and authoring fixtures truncate. Use a throwaway on `127.0.0.1:5442`, and put
  `MENDEL_DATABASE_URL=…` on **make's command line**. Run Python tests from the repository root.
- **The stack:** the mendel `api` reloads from `./packages`; `ai-worker` and `wiener-api` are baked,
  so rebuild them after a backend change. Ollama's default context (2048) silently truncates.
  **The worker holds the host Docker socket**, which is root-equivalent: `WIENER_API_TOKEN` is the
  boundary in front of it. **The run directory is bind-mounted at the same absolute path** inside
  and out, because a path handed to the daemon resolves on the host.
- **Toolchain, verified 2026-08-02, do not re-audit:** uv, Python 3.12, Nextflow 25.10, Java 21,
  Docker. The nf-core CLI is not installed; `uvx nf-core` works.
- **CI has no Nextflow or Docker.** Any test passing `--gate` is green locally and red in CI; omit
  it unless the test is about gates (`test_gates.py` guards with `skipif`). **Check by
  shadowing:** put a `nextflow` that exits non-zero on `PATH` and run the fast suite.
- **The stub gate needs Docker and ~900s cold**, and `-stub-run` cannot see a hollow input: only
  `--gate test` catches a process handed nothing.
- **nf-core's module metadata (meta.yml) is a scaffold, not a contract**: "sorted" exists only in
  English. The state overlay is what routing depends on.
- **Routing:** a contract cannot satisfy its own input, and surplus ranks candidates
  (`(surplus, -priority, id)`), so "a BAM" never silently means "a sorted BAM".
- **A contract port is not a process argument**, and **the port name is the emit label**
  (`PROCESS.out.<name>`). `nf_inputs` declares the real signature; `NfInput.empty` carries the
  tuple width.
- **Read process names and containers out of the module's `main.nf`** under `registry/tools/`,
  never out of a plan. nf-core 4.x mostly uses `community.wave.seqera.io`; take the last quoted
  `container` string.
- **`frozenset` has no stable order**: anything serialised needs a sorting serializer.
- **A contract is a hand-written binding** to its module, checked by `mendel build` and
  `mendel conformance`. With no readable module source it is marked `unverified`; never assert a
  conformance property over modules that were not read.
- **Entry channels come from the vocabulary**, not the compiler: a type declares `entry_channel`.
  **A producer pin binds only where the pinned contract is a candidate**; `UnroutablePinError` is
  for a pin whose own inputs cannot be reached.
- **`--no-ai` must keep working** once it exists: it is how determinism stays testable.
- **A resolved value needs somewhere to go** (`ext.args` or `meta`); `params.<x>` is read by
  nothing. Emptiness is the forge's job; deadness is a routing bug.
- **Import modules, not symbols, where tests monkeypatch**; `uv sync` installs only what the root
  project lists in `dependencies`.
- **A `.pyi` replaces its module**: `tools/generate_types.py` emits the whole surface.
- **Jinja:** `{% endfor %}`, never `{%- endfor %}`. **`nextflow lint`** writes errors to stdout,
  `nextflow run` to stderr.
- **Anchor ignore patterns** (`/build/`): an unanchored one once swallowed a vendored module.
- **Frontend:** an unmapped Tailwind colour generates no CSS; cite issues as *issue 110*, since
  `#110` reads as a hex colour; layout bugs are invisible to jsdom, so screenshot.
- **Never `git submodule deinit` inside a worktree:** the config is shared with the main checkout.
- **Declared data is files, not a database**, and there is no vector memory store. Reach for one
  only for proposal deduplication or analogy retrieval, when those appear.
- **`ruff format` is not a gate**; 28 files are hand-wrapped deliberately.

## Where to look

| For | Read |
|---|---|
| what is true now, and what is next | [`docs/notes/now.md`](docs/notes/now.md), then [`docs/notes/journal/`](docs/notes/journal/) |
| the task tree | GitHub issue #119 |
| why each invariant exists | [`docs/design/invariants.md`](docs/design/invariants.md) |
| how it fits together, against real types | [`ARCHITECTURE.md`](ARCHITECTURE.md) |
| walking it: issues, decisions, rounds | [`docs/internals/walking.md`](docs/internals/walking.md) |
| how authoring works (the conversation) | [`docs/design/authoring-protocol.md`](docs/design/authoring-protocol.md) |
| where a test goes | [`tests/README.md`](tests/README.md) |
| `pipeline.yml`, field by field | [`docs/handbook/reference/pipeline-schema.md`](docs/handbook/reference/pipeline-schema.md) |
| every diagnostic | [`docs/handbook/reference/diagnostics.md`](docs/handbook/reference/diagnostics.md) |
| the words the interface uses | [`docs/handbook/reference/glossary.md`](docs/handbook/reference/glossary.md) |
| `../braidworks`, the ancestor of the contract model | its own architecture page |

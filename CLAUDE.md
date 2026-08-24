# Comeni Labs

Deterministic bioinformatics pipeline construction. A researcher describes an analysis in
plain language; **Mendel** resolves it to a Nextflow pipeline where every decision traces to
a constraint, a convention, a measurement, or an explicitly flagged judgement call.

The product claim, which every design decision serves:

> Same goal in → same pipeline out, and nothing was guessed silently.

**Mendel is the engine, and the AI is its primary operator** — decided 2026-08-14, see
`docs/design/mendel.md` §1. A human can drive it and the CLI is built so they can, but the
intended operator is the AI: it turns plain language into a goal, drives the engine, and
`pipeline.yml` is the **save file** it sets down, picks up, tunes and re-emits rather than
carrying a pipeline in its context. That is the inversion the product rests on — a chat window
has the model produce the pipeline, here the model produces only a *goal* and a deterministic
engine produces the pipeline, so the model's unreliability is confined to a typed input and
cannot reach the output. **It changes no invariant**: an agent driving the CLI is a user of it,
outside the engine, and invariant 3 constrains what Mendel calls rather than who calls Mendel.
What it does change is the standard the artifact is held to — a person reading a value with no
reason sees a blank and asks; a model sees a blank and fills it.

## Current state

> **Start with the latest entry in [`notes/journal/`](notes/journal/).**
> It is append-only and dated, so it cannot silently go stale the way this section can — and it
> carries what is next, what was decided, and what a fresh reader gets wrong. This section holds
> only what stays true between plans; the journal is the handoff.
>
> **Nothing here is a count.** Two numbers in this file were stale for three plans because
> nothing counted them (A71, A72), and a third — "748 fast tests" — was stale again by the time
> issue #41 rewrote this section. Counts live where a command can derive them: `make check` for
> tests, `make residue` for guard coverage, `len(DeclaredKind)` for kinds,
> `tests/test_egress.py` for the free-text fields.

**Plan 1 through Plan 1.15 are complete, the design audit has run, the forge's two phases are
done, and Plan 2.5 landed.** **Plan 3A — the forge interface — is COMPLETE as of 2026-08-19**, all nine phases, on the
branch `plan-3-slice-1`, **merged into `main` on 2026-08-19**. `make dev` brings the whole thing up: Postgres,
Redis, the API, the ARQ worker and nginx serving the built SPA, with Vite on the host for HMR. **Phase 7 was
responsiveness and it did not exist until an audit created it** — every registry-touching screen
cost ~250ms warm and one function was responsible
([`notes/audits/2026-08-19-performance-audit.md`](notes/audits/2026-08-19-performance-audit.md),
A132–A145). It is now **5–10ms**, `mendel build` is 0.38s where it was 1.47s, and the fast test
suite is 41s where it was 207s — with the emitted pipeline byte-identical.

**Plan 3B is COMPLETE as of 2026-08-19**, on `plan-3b-landing`, branched from `plan-3-slice-1`
and **also merged**. `/` is a landing page rather than the redirect phase 0 left there, behind one
endpoint, `GET /api/attention`. **The page counts and links and never renders an item**, and that
is not a style note — `docs/design/forge-review.md` §3 records an Overview page *designed and
cut* for answering the same question as the Queue, so the moment a contract id or a question
subject appears on the front door it has become the page that was cut. A test holds it. Its
signature element reuses `dashboard.md` §1 rather than inventing anything: certainty is drawn as
stroke, the same language the canvas will use, so `tokens.css` did not change.
**Plan 3D is COMPLETE as of 2026-08-19**, on `plan-3d-forge`, branched from `plan-3b-landing`
and **also merged**. It followed the operator's verdict that the forge was *unusable*, and the
spec was written after **walking the loop as a user** rather than reading the code — which found
that it was **not a looks problem**. `forge draft` opens seven `type_id` holes per tool and each
offered the whole twenty-two-type vocabulary *alphabetically*: measured against the 30 ports of
the 12 landed contracts, the right type was ranked first in **1 of 30**. Ranking by the port
name, an abbreviation of it, and the tool's own name puts it first in **25 of 30**, with
arithmetic over declared data and no model. `OpenQuestion.suggested` — which had every consumer
and no producer, so `QueueRow`'s *Confirm* branch was unreachable — now has one, and only where
something actually scored. `Sources` and `Contracts` were one query at two stages of a tool's
life and are now `GET /api/tools` behind a status board that answers *is everything okay* before
it lists anything. **Eight words the interface used without defining now have definitions**
([`docs/reference/glossary.md`](docs/reference/glossary.md), `?` from anywhere).

**Plan 3C is COMPLETE as of 2026-08-19**, on `plan-3c-builder`, and it built a **visualiser
rather than a builder**. `/build` shows a pipeline the resolver already
produced: DAG layout computed in Python so the canvas is as deterministic as the emitted `.nf`,
ports, tier rails, a provenance bar answering *how much was settled without judgement*, and a
settings card. **Nothing on it could be changed**, and the operator's reframing was that it must
be a Galaxy-style builder — you assemble, it checks you, and it also shows what the resolver
would do.

**Plan 3E did that, and it is COMPLETE as of 2026-08-23**, on `plan-3e-builder`,
**merged into `main` on 2026-08-23** — the last of 3A–3E, so every plan branch is now in
`main` and none is carried.
`validate(graph, layers) -> Verdict` is a pure resolver verb with nine `MD0500` diagnostics; a
**compatibility index** lets the browser colour a wire mid-drag *without a second implementation
of the rule*, held to the verb by a test over every port pair in the registry; drafts live in
Postgres under an opaque id, because `routes/build.py` records that the API may not accept a
path; and `compare` puts your graph beside the resolver's with **the resolver's own reason** for
every difference.

**A hand-drawn graph now emits real Nextflow.** Against `mendel build` on the same registry the
process sets differ by exactly one include — `TRIMGALORE`, which the resolver adds because
`star/align.reads` declares `state_required_conventional: [trimmed]`. That is the correct answer,
and it is what `compare` reports as `mendel-only`.

**Three things had to be built that the spec assumed existed**, each found by a guard refusing
the file the previous fix had just written: `Pipeline.of` needs an IR *and a `Goal`*, so
`mendel_resolver/materialise.py` derives one from the graph — entry channels are what you have,
terminal outputs are what you want; `MD0210` wanted the vendored modules beside the artifact; and
`MD0224` wanted settings, which now run the resolver's own `_resolve_param`, so a drawn node and
a resolved one come out at the same tiers with the same premises.

**A model's override is recorded separately from a person's** — `model_override` and
`model_override_by` on all three decision kinds, `SCHEMA_VERSION` 4→5, `comeni-core` 0.2.0.
`human_override` keeps its meaning, because a pipeline an agent assembled must not read as one a
person drew by hand. That is A130 arriving from the other direction.

**Wiener W1 is COMPLETE as of 2026-08-24**, on `wiener-w1`, **merged into `main` the same day**. Wiener went from zero
lines to *a pipeline runs, you watch it, and its waterfall is queryable* in a day: two plans,
26 tasks, nine checkpoints. `wiener-core` is pure and joined invariant 1 — the first time that
list has grown — and it paid off where §3.1 predicted, refusing the OpenTelemetry SDK when the
exporter was written. **`dag-core` is a fifth pure package**: the DAG layout lifted out of
`mendel-compiler` so the builder's canvas and the run graph are one implementation, depending on
nothing at all, not even `comeni-core`.

**Five defects were found by running it and none by a test written to pass**, and the pattern is
the useful part: `admit()` dropped the fifteen resource fields the record can never recover; the
record did not survive being read back, because it is written by field name and was validated by
alias; the fold was a no-op because `prior` was read after the row was inserted, so every ingest
replayed the whole run; a run arrived as two traces because the SDK invents a trace id for a
parentless span; and `* task.attempt` was decoration until an `errorStrategy` made a retry
possible. [`notes/journal/2026-08-24-wiener-w1.md`](notes/journal/2026-08-24-wiener-w1.md) is
the handoff.

**Mendel gained two things from Wiener needing them.** The emitted pipeline now says what it
asks for — nf-core's `conf/base.config` label mappings, a convention quoted rather than a
judgement invented — and a cap is kept separate from a request: `process.resourceLimits` is a
*site* fact written by Wiener's launcher, never a number in the artifact. Both were found by a
board with one half of every comparison empty.

**The whole stack comes up with one `docker compose up`**, which was the operator's constraint
rather than a convenience: Postgres, Redis, both APIs, the worker, nginx, the OTel collector,
ClickHouse and Grafana. Two consequences are worth knowing before touching it. **The worker holds
the host Docker socket** — that is how a container spawns Nextflow which spawns containers, and it
is root-equivalent, so `WIENER_API_TOKEN` in `.env` is the boundary in front of it and the worker
warns at startup if the socket is mounted without one (`docs/design/wiener.md` §12.1 records the
trade, and W5's `-profile k8s` removes it). And **the run directory is bind-mounted at the same
absolute path inside and outside** the container, because a path handed to the daemon is resolved
on the host — a named volume silently breaks that and a root-owned one breaks it loudly.

**The Mendel→Wiener courier exists as of 2026-08-24** — A179 closed. `GET
/api/pipeline/drafts/{id}/bundle` serves a kept artifact as a zip and the builder's *run* tab
posts it to Wiener, so **the browser is the courier and neither API learns the other exists**.
Two clicks rather than one, because uploading is what discovers the parameters: the artifact
declares its own holes and Wiener reads them out on upload. `docs/design/wiener.md` §12.

**Nobody has looked at these screens.** Checkpoints 3 and 5 drove the HTTP and WebSocket halves
and verified them; the browser half is unrun, which is exactly the gap 3E's lesson names.

**The entire forge still needs testing and general rework**, and the operator is rethinking its
design (2026-08-23). Nothing in 3E or Wiener touches `mendel-forge`.
The ordered list of every plan, with its status and the argument for its position, is
[`notes/README.md`](notes/README.md) — that file is the index, and repeating it here is how this
section got to 156 lines.

**The product claim is two claims, and they are not in the same state.** That split is the most
useful thing the 2026-08-14 design audit produced.

- ***"Same goal in → same pipeline out"* holds**, and is stronger than `ARCHITECTURE.md` §8
  claims.
- ***"Nothing was guessed silently"* did not hold** — five of the six values reaching the
  generated Nextflow carried no `why:` at all — and Plan 1.14 closed it. Every value now carries
  a reason a reader can act on, so the artifact's own header is true where it was false.

**`pipeline.yml` is the pipeline.** One artifact carrying the goal, every step and setting with a
`why:` (the tier, who settled it, which layer, the citation, the premise a rule read), every
contract pinned by content digest, every layer, the gate that passed and the digests of what was
emitted — no paths, no timestamps. Every setting declares the **route** that carries it to the
tool, so a resolved value reaching nothing is refused rather than emitted. It replaced
`pipeline.ir.json`, `mendel.lock.yml` and `PublishBundle`. `mendel emit` rebuilds the Nextflow
from it with **no registry and no network**; `mendel upgrade` re-resolves against the current
registry and replays every recorded decision. Read
[`docs/reference/pipeline-schema.md`](docs/reference/pipeline-schema.md), and
[`docs/guides/driving-mendel.md`](docs/guides/driving-mendel.md) for the loop end to end.

**A tier-3 rule targets a role, not a type id** (Plan 1.15), with three effects — `presence`,
`implementation`, `param` — and a **premise layer** builds the facts `when` reads, each carrying
where it came from. `ARCHITECTURE.md` §Rule tables is the description;
`notes/specs/2026-08-15-root-5-the-rule-format.md` is why each part is shaped that way.
`tests/fixtures/rule-corpus/` holds twenty real rules and is the assertion that the format can
express them.

**`mendel build` refuses a contract that disagrees with its module**, against the vendored
`main.nf` and `meta.yml`. `mendel explain <code>` for any diagnostic;
[`docs/reference/diagnostics.md`](docs/reference/diagnostics.md) for all of them.

**Nothing AI-shaped is built, and `mendel-forge` now exists without being AI-shaped.** That
distinction is the point of Plan 2 Phase 1. `comeni-core`, `mendel-resolver` and
`mendel-compiler` are pure; `mendel-forge` is the first **impure** package — classified in
`IMPURE_PACKAGES`, with `test_no_pure_package_imports_an_impure_one` holding the arrow — and it
is entirely deterministic: a source is read, facts are derived, and everything that cannot be
derived is a typed **hole** a person fills. `ports.py` declares `HoleFiller` and ships
`NoFiller`, which declines everything, so `--no-ai` is not a flag in the forge but the only
mode. `mendel-ai` exists (transport only) and **`mendel-api` and `frontend/` exist as of Plan
3A** — see the journal. **Phase 2 wires a model into the forge,
and its first question is the fifth egress door** — a model call sends tool documentation to a
provider, and invariant 14 says there are four. `ARCHITECTURE.md` §10 is the description;
`notes/specs/2026-08-16-the-forge.md` §10.3 is the argument; and
[`notes/journal/2026-08-17-the-forge.md`](notes/journal/2026-08-17-the-forge.md) **§Phase 2** is
the handoff — what is already built, three things that look like blockers and are not, and the
decisions Phase 1 deliberately left open.

### What is open

**A14 is critical and stays open.** A guard never watched failing may be **inert rather than
merely weak**, and it closes only when every guard in `tests/` has a recorded revert.
[`notes/audits/guard-ledger.md`](notes/audits/guard-ledger.md) is that record — append-only, one
row per revert, with the message it printed.

**Residue is measured per *guard*, not per file** — that is A69, and the distinction matters
because the file-level number reads as nearly done and is not. **`make residue` counts it**, with
`ARGS=--list` for the names. A69 closed when the number became derivable rather than asserted.

**A36 and A130 closed on 2026-08-16**, with #48 and #49. A36's separator now has a test that can
fail — deleting the tag was the audit's preferred option and is no longer free, because
`comeni-registry` is published and a layer digest is what a `pipeline.yml` pins. A130 closed in
the direction that can be proven: `Pipeline.ai.available: []` states that nothing was wired to a
model, `MD0225` refuses a value claiming otherwise, and `ValueSource.MODEL` exists so Plan 2's
adapter has somewhere truthful to write. **The other direction is not checkable** — an adapter
writing `resolver` on every value is indistinguishable from the ladder — and that limit is
documented on the field rather than implied.

**Round four's fifteen findings are all closed** (2026-08-15, issues #24–#36). This paragraph said
they were carried for a day after they were not, while the table below said otherwise — which is
the same drift A71 and A72 are about, in prose that had no counter behind it.

**A14 is the only carried finding left.**

**By the operator's decision on 2026-08-13, Plan 1.12 was the last audit-driven plan** — which
overrides the fix-then-re-audit loop's own exit criterion of *no critical finding surviving a
fresh audit*. [`notes/README.md`](notes/README.md) records that decision and the argument against
it, as it does for every ordering here.

### What to read

**[`ARCHITECTURE.md`](ARCHITECTURE.md) before writing code.** The five stages, the declared data
and its load order, routing, both tier ladders, ports versus channels, and the three guards —
written against the types that exist.

| Read this | For |
|---|---|
| [`ARCHITECTURE.md`](ARCHITECTURE.md) | **how it all fits together, against real types. First.** |
| [`docs/README.md`](docs/README.md) | the documentation front door — three doors, by what you are doing |
| [`docs/guides/driving-mendel.md`](docs/guides/driving-mendel.md) | the loop: goal → build → read → edit → emit → answer → upgrade |
| [`docs/reference/pipeline-schema.md`](docs/reference/pipeline-schema.md) | `pipeline.yml`, field by field |
| [`notes/journal/`](notes/journal/) | **what happened, what is next, what was decided.** Newest first |
| [`notes/README.md`](notes/README.md) | every plan in execution order, and the argument for that order |
| [`notes/audits/README.md`](notes/audits/README.md) | the rounds, the design audit, and the guard ledger |
| [`notes/specs/README.md`](notes/specs/README.md) | the specs — read the one behind a part before starting it |
| [`docs/design/mendel.md`](docs/design/mendel.md) | the original rationale. `ARCHITECTURE.md` is what the code *does* |
| [`docs/design/federation.md`](docs/design/federation.md) | provider access, registry stacking, publication, licensing |
| [`docs/design/clinical-data-protection.md`](docs/design/clinical-data-protection.md) | clinical use, the egress boundary, the protection profiles |
| [`docs/design/conformance.md`](docs/design/conformance.md) | whether "if it compiles, it runs" is reachable |
| [`docs/design/declared-data.md`](docs/design/declared-data.md) | why declared data is files and not a database, and where an index would be legitimate |
| [`docs/design/rule-tables-and-port-logic.md`](docs/design/rule-tables-and-port-logic.md) | the **superseded** rule format. Plan 1.15 replaced it |
| [`notes/specs/2026-08-13-the-rule-drafter.md`](notes/specs/2026-08-13-the-rule-drafter.md) | **where tier-3 rules come from.** Unscheduled on purpose; read before building any part of the forge |

## How to start implementing — decided 2026-08-02, read this first

> **Use `superpowers:executing-plans`. Subagents for review and design when needed.**

That is the operator's instruction, not a suggestion. Concretely:

- **Drive the plan yourself** with `superpowers:executing-plans`, sequentially, task by task.
  Do **not** use `subagent-driven-development` to farm out implementation tasks.
- **Subagents are for review and design only**, and only when the work calls for it — a
  second opinion on a design question, a review pass over something already written. Never
  as the default way to write code.
- **Work in a worktree**, not the main checkout. Plan 1 used `.worktrees/plan-1-spine`; that one
  is merged and removed.
- **Tick each `- [ ]` step in the plan as it completes** — decided 2026-08-18, and it is a break
  with what came before. Forge Phase 1 and Phase 2 are both complete and carry **0 of 119** and
  **0 of 87** boxes ticked, which makes those files indistinguishable from plans that never ran.
  Tick as you go rather than in a batch at the end. Where a step was carried out *differently*
  than written, tick it anyway and record the deviation in an execution-record table: a tick
  means *this step was carried out*, not *the code was pasted verbatim*, and plans here are
  corrected during execution by design. **Do not back-fill older plans** — ticking a box nobody
  watched being executed is a claim, not a record.
- **Execution order lives in `notes/README.md`**, not in the filenames — two plans share
  a date. Plans 1.5–1.12 are complete; **the design audit is next**, then Plan 2, then Plan 3.
  That audit asks a question the four guard rounds never did — whether the design itself
  delivers the claim — and `notes/audits/2026-08-14-design-audit-brief.md` is its
  method, because "revert and watch" cannot be run against a design. Round four ran and
  Plan 1.12 closed its criticals; by the operator's decision on 2026-08-13 no further audit round
  gates Plan 2, which overrides the loop's *no critical finding surviving* exit criterion. That
  file records the decision and the argument against it, as it does for every ordering here —
  the sequence was once asserted and believed for a day before anyone asked. **Plan 1.7 was called "Plan 2.5" until 2026-08-05**;
  the number recorded when it was written, not when it runs, and journal entries up to that
  date still use the old name.

### Stop and speak when the estimate breaks — decided 2026-08-16

**An estimate that is wrong by more than about double is a decision point, not a hill to push
through.** Say the new number, say what changed, and offer the choice. The operator can always
say "carry on"; they cannot un-spend an evening.

This is written down because 2026-08-16 ended with three hours on a fixture sweep estimated at
one, and the work was abandoned unfinished at 1am. Three failures, in order:

- **The first surprise was not reported.** A sweep predicted to touch a handful of files came
  back with 102 failures, and the reaction was *one more pass and it will be green* — about eight
  times. The moment to speak is the first measurement that contradicts the plan, not the tenth.
- **Being told to communicate produced narration, not a change of process.** The same
  run-a-2.5-minute-suite, patch-one-batch, re-run loop continued, now described out loud.
  **Describing a bad loop is not communicating.** Saying *"this loop is wrong, here is what I
  should do instead"* is.
- **An offered escape route was not revisited.** The operator suggested a cheaper fallback; it
  was reasonably declined at the time, and never reconsidered once the cost of the honest route
  became clear. A rejected option should be re-offered when the premise it was rejected on
  changes.

**Two habits that would have caught all three:**

1. **One diagnostic run that collects every failure, then one fix pass.** Ten patch-and-rerun
   cycles cost more than the single comprehensive run they were avoiding — and each cycle hides
   how large the remainder is.
2. **Present decisions as choices, with the cost of each.** A number and two options is a
   sentence; it is also the whole of what the operator needs to steer.

**This is not in tension with the rigour the rest of this file asks for.** Watched-failing guards
and `make verify` reward long autonomous cycles, and that is right — but rigour and silence are
different things, and conflating them is what happened here.

**Toolchain was verified on 2026-08-02** — do not re-audit it: `uv` 0.11.18, Python 3.12.12
(the plan's floor exactly), Nextflow 25.10.4, Java 21, Docker 29.6.2. `nf-core` CLI is not
installed and does not need to be; `uvx nf-core` works and github.com/nf-core/modules is
reachable.

**Plan 1.7 is written** — `notes/plans/2026-08-04-publication-and-the-registry-split.md`,
nine tasks, against the types that exist rather than the ones the spec predicted. Three of those
predicted types did not exist and the plan creates them (`PipelineIR.registry_layers`,
`PipelineIR.shadowed`, `PublishBundle.goal`); one did and is the key to replay
(`DecisionRecord.human_override`). The catalogue and review screens moved to Plan 3, because they
need `mendel-api`. Two egress-guard failures were found by running the guard while writing it,
and their fixes are steps rather than warnings.

That rule earned itself again on 2026-08-03: the measurements plan predicted a YAML row syntax
that does not parse, a producer pin that makes the spine unbuildable, a `mendel profile` whose
`want` cannot route, and a `.pyi` that would have hidden three types from every type checker.
All four were written in good faith against types that did not exist yet. **Write plans against
code, and expect to correct a plan you are executing.**

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

1. **`comeni-core`, `mendel-resolver`, `mendel-compiler` and `wiener-core` do not reach the
   network.** Two partial guards, and the claim is their union — say *do not*, never *cannot*. A
   static AST scan (`tests/test_purity.py`) rejects the imports, the dynamic import forms, bare
   `exec`/`eval`/`compile`, and a module reached as an attribute of an allowed one; a runtime
   assertion (`tests/test_purity_runtime.py`) installs an audit hook over a real build and fails
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
   **`wiener-core` joined on 2026-08-24** (`docs/design/wiener.md` §3.1), and it is the first
   time this list has grown. A fold over events has no legitimate need to open a socket, which
   is the same argument that made `ctypes` costless — and it is load-bearing in a place nobody
   planned: **the OpenTelemetry SDK is a network client**, so this guard is what keeps the span
   *mapping* pure and the *export* on the other side of the line, without anybody having to
   remember. What it does **not** yet cover is a clock: `datetime` is on that package's
   allowlist for the class and must never be `datetime.now`, because §6.1's claim — same events
   in, same decisions out — dies the first week one is read inside the fold. The allowlist
   cannot express *this name but not that attribute*, so a separate scan holds it.
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
11. **The registry is a stack**: public curated base, then private overlays. A layer is a
    **directory of declared files, each of which says what it is** — a `declares:` line
    naming one of `DeclaredKind`, and for a vocabulary or a measurement an `id:` beside it.
    **The layout is free**, and the convention the public registry uses is to group a tool's
    files together: `tools/nf-core/star/align.contract.yml` beside the type it produces.
    Every kind stacks **through one mechanism** — `comeni_core.layered.stack()`,
    parameterised by a `Kind` that declares only how its files parse, key and merge.
    Hand-written loaders disagreeing on six axes is what audit root B was.
    **The count lives in `DeclaredKind` and not in this sentence.** It said "four" from Plan
    1.9 to Plan 1.15 and would have been wrong the day a fifth kind arrived, which is A33's
    lesson and A71/A72's: a number repeated in prose is a number that goes stale while
    everything around it stays true. `len(DeclaredKind)` is the honest count.
    **What weakened, recorded rather than discovered** (comeni-registry#1): the directory used
    to make a misfiled document impossible — `contracts/` held contracts, and a misspelled
    `contract/` was caught by `MD0003` because nothing read it. That was prevention *by
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
12. **No subscription OAuth.** Claude Pro/Max tokens in third-party tools violate Anthropic's
    Consumer ToS (documented 2026-02-19, enforced since 2026-01). API keys or local models only.
13. **Self-hosted is not a degraded tier.** Same registry, same resolver, byte-identical
    output. The hosted instance sells convenience, never capability. Anything that would only
    work on our infrastructure is a design error.
14. **Pipeline data leaves through four declared doors and no others** — goal extraction,
    tier-4 resolution, compiler repair, publication.
    **The doors track the prompt taint path**, which is what
    `docs/design/clinical-data-protection.md` §4.2 states and what this one-line summary lost:
    *free text enters at exactly one door*, and the question for anything else is whether it is
    downstream of it. The four are one path — prompt, goal, build, pipeline, publish.
    **The forge is not on that path and is not a fifth door** (decided 2026-08-17,
    `notes/specs/2026-08-17-forge-phase-2.md` §1). It has no prompt, takes no `Goal` and writes
    no `pipeline.yml`; it reads vendored modules and registry files and produces registry data a
    build later consumes — the offline authoring half of invariant 2. `AiPoint` corroborates
    this without being changed: invariant 3 declares three runtime AI points and the forge is
    not one of them. `DOORS` and `tests/test_egress.py` did not change when Phase 2 wired a
    model into the forge, and that is the point.
    Each door carries one declared payload type, and
    **fourteen** fields across the whole surface may hold free text: `PromptRequest.prompt`,
    `GateFailure.tool_message`, `ResolvedValue.reason`, one `reason` per decision kind,
    `Why.reason` — the citation beside every value in `pipeline.yml` — and since Plan 1.14 the
    `axis_reason` on `Why` and `ResolvedValue` plus `ParamDecision.override_reason`.
    **The tenth is the first genuinely new author**: the nine before it are written by a
    contract author, a rule author or the resolver, and `override_reason` is written by the
    person answering a tier-4 question, in the artifact, after resolution. It exists because
    until Plan 1.14 that person had nowhere to say why, and `upgrade` replaced what they wrote
    with "selected the first of 1 candidates without judgement" (A77).
    This said "exactly two" for a plan and a half while the guard held four, then six, seven,
    and now ten; the guard is the honest count and this sentence is the one that drifts (A33).
    **Every increase up to the ninth arrived by a refactor rather than by a new kind of string
    crossing** — A16 splitting `DecisionRecord` into three, `Pipeline` taking door 4, and Plan
    1.14 splitting `reason` in two because it was answering both *why this axis* and *why this
    answer*, which is how the registry came to cite the STAR paper as the reason HISAT2 was
    chosen (A79/A107). **The tenth broke that run**, and it is written down here rather than
    absorbed: `override_reason` is a new author writing at a new moment, and the argument for
    it is that the alternative is a reviewer's reasoning living nowhere. Whether that argument
    holds is the sort of thing a literal list exists to put in front of somebody, and it has
    now done so five times.
    **Eleven through fourteen arrived together, with Plan 2.5**, and they are a *refactor*
    increase of the A16 kind rather than four new kinds of string: `Ambiguity` became a
    `comeni_core.review.Question`, so `what` and `why_open` — which the forge had carried on
    every `Hole` since Phase 1 — reach door 2 too, along with `Excerpt.locator` and
    `Excerpt.text`. They were **let through rather than stripped**, on a measurement: the
    forge's prompt search took a local model from 69% to 88%, and two of the three fixes
    behind that were *the question never said what it was about* and *the evidence was not
    readable*. A door handing a model bare candidates rebuilds the 69% configuration on the
    build path. `test_the_door_carries_what_the_forge_measured_a_model_needs` holds it, so
    removing them fails rather than quietly regressing.
    **`Excerpt` is the first entry that is not an author.** Every other field is composed by
    somebody; these two are *quoted* — a source file already holds the text and an excerpt
    copies it. That is a weaker claim than the rest of the list makes, and it is written down
    because *"it is only quoted"* is exactly the reasoning that widens a boundary unnoticed.
    What bounds it is the source: excerpts come from vendored modules and registry files,
    which are public, and never from a prompt or a goal.
    **Door 4 carries a `Pipeline`**: the artifact on disk *is* the payload, so what a person
    reads before publishing and what crosses the boundary cannot disagree. `PublishBundle` is
    retired. The guard's roots come from `DOORS` rather than from what happens to live in
    `egress.py` — scanning the module found three doors out of four the moment the publication
    payload moved, and the one it missed was the door with no undo. Everything
    else is closed vocabulary; no payload may carry an `Any`-typed field, and none may carry
    a plain `str` — every string is a declared ID alias or marked `Mark.FREE_TEXT`, because a
    bare `str` bypasses the marker in one line and a prompt fits in it perfectly. The rule is
    now an **allowlist**: `test_every_payload_field_is_a_declared_shape` enumerates what a
    leaf may be rather than what it may not, because a blocklist can only forbid what
    somebody named — which is how `object`, `Path` and `Any` each arrived one audit apart.
    Enforced by `tests/test_egress.py`, which holds both lists literally, so widening the
    boundary means editing a test that says these are all the ways data leaves. Publication
    is the door with no undo.
15. **Mendel does not receive patient data.** No input accepts a sample identifier, filename or
    path. `Goal` holds type IDs, states and declared measurements — a shape, not data. Profiling
    happens where the data is; the emitted pipeline references `params.input` as a placeholder
    the lab fills at run time, and `mendel profile` writes `value: null` because it has emitted
    a pipeline and not run one.
    Since measurements became declared data the model can no longer refuse an undeclared key, so
    the guard moved rather than weakened: `MeasurementRegistry.profile()` is the only validating
    constructor, `tests/test_construction.py` enforces that nothing else builds a `DataProfile`,
    and `mendel build` re-routes every goal's profile through it. Delete that one call and
    `profile: {sample_name: ...}` builds cleanly — which is how it was watched failing.

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

Module choices carry a tier too, in `IRNode.selection`, and `needs_review()` lists a tier-4 one
by node rather than only as a `DecisionRecord` a reviewer would have to join by hand.

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

**None of this table is implemented yet, and saying so is the point** —
[#71](https://github.com/comeni-project/Comeni-Labs/issues/71). A search for
`ProtectionProfile`, `SEALED` or `GUARDED` across every package returns nothing, because every
row describes a subsystem that does not exist: the prompt door, compiler repair and tier-4
resolution are all Plan 3 or later. **The profiles govern the build path**, and offline
authoring in `mendel-forge` is outside them for the same reason it is not a fifth egress door.
A laboratory wanting no model calls from an installation does not configure `MENDEL_MODEL`,
which is stronger than a check: there is nothing to reach a provider *with*.

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
    declared/          what a registry layer holds, and how it stacks
    goal/              what is asked for, and what was measured
    review/            what is open, and how it gets closed — Question, Answer
    plan/              what was decided — the IR, the tiers, the records
    artifact/          pipeline.yml, the lockfile, the gates, the doors
    spell/             how a value is spelled on its way to a tool
  mendel-resolver/   four-tier ladder, rules, routing, ports           PURE
    rules/             the rule format, the tables, the validator
  mendel-compiler/   IR → Nextflow DSL2, validation gates, repair      PURE
    cli/               the verbs — resolve_verbs, artifact_verbs, report
  mendel-ai/         generate(shape) over LiteLLM; closed-choice helpers  impure
  mendel-forge/      sources, scaffolds with typed holes, verify, land  impure
    filler.py          ModelFiller — a model behind the HoleFiller seam
    sources/           the Source protocol, and the nf-core adapter
    cli/               the transport over ops.py; it holds no logic
  mendel-api/        FastAPI surface; mounts the forge, projects questions  impure
    routes/            questions, health — validate, dispatch, serialise
    questions.py       OpenQuestion: one schema, two consumers
  wiener-core/       run state: admit, fold, decide, spans, stats           PURE
  wiener-api/        launch, ingest, project, stream, export                impure
  dag-core/          where to draw a graph. Both canvases, one arithmetic   PURE
registry/      A GIT SUBMODULE of comeni-project/comeni-registry — THE LAYER
examples/      rnaseq-goal.yml — an example goal, and nothing else
vendor/        nf-core modules, modules.json, .nf-core.yml, conf/ — vendored source
docs/          guides/ reference/ concepts/ design/ — written for a stranger
notes/         plans/ audits/ specs/ journal/ — provenance, not documentation
frontend/      React 19 + TS + Vite + Tailwind 4. src/api/ is GENERATED from openapi.json
```

**The subpackages inside `comeni-core` are a pipeline through the system**, named for the stage
rather than the type: what is *declared*, what is *asked*, what is *open*, what was *planned*,
what is *emitted*, and how it is *spelled*. `review/` is Plan 2.5's, and it is the one stage both
halves of the system pass through — the forge asks about a contract it is drafting and the
resolver asks about a pipeline it is building, and until 2026-08-18 those were two vocabularies
for one idea. **Its base classes are inert**: whether an unanswered question *blocks* lives in
the container and the port, never on the type. `HoleFiller.fill()` may return `None` and
`AmbiguityResolver.resolve()` may not, and that is the whole of the difference. Issue #41 split them out of one flat directory of nineteen modules; the
public surface of `comeni_core` did not change, and `comeni_core.__init__` is what holds it
stable. `mendel_resolver.rules` and `mendel_compiler.cli` were single modules and became packages
in the same change — `rules/__init__.py` re-exports, because a package's `__init__` is its own
surface rather than a second spelling of something else's.

**The registry left, on 2026-08-16 (issue #46).** `registry/` is a **git submodule** of
[`comeni-registry`](https://github.com/comeni-project/comeni-registry), pinned to a commit and
mounted at the path it already occupied — so every test that loads `ROOT / "registry"` is
unchanged, and `git clone --recurse-submodules` is how you get it. Forget, and `make check` and
`layers.load()` each refuse in one sentence naming `git submodule update --init`.

**It was predicted to be "a path change and nothing else", and it was not.** The submodule puts
`LICENSE`, `README.md` and a `.git` *file* beside the declared kinds, and `.git` holds
`gitdir: …/worktrees/<name>/modules/registry` — so `digest_of_directory`, which walked
`rglob("*")`, made the **layer digest machine-dependent**. `make verify` was green throughout;
what caught it was building the spine on both branches and diffing `pipeline.yml`. A layer's
digest now covers an **allowlist** — `declared_entries()`: the `DeclaredKind` directories plus
`registry.yml`, which is what invariant 11 already says a layer *is*. Same definition is what
`layers.load()` scans for symlinks, so there is one answer to "what are a layer's files".

**Drift is gone rather than checked.** There is one copy now, so
`tools/check_registry_drift.py`, `make drift` and the nightly job were deleted with it.

It is **not a curated registry**: every contract in it is a test fixture that happens to be
true. Every file in it declares its own kind, so the loader globs the whole layer and buckets
by content — which is why the goal file stayed in `examples/` rather than moving in beside the
contracts, and why `registry.yml` at the layer root is a manifest rather than a stray.

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
the `mendel_resolver.ports` protocols. **`--no-ai` is still not a flag, and forge Phase 2 did
not add one** — the forge's model path is opt-in through `forge fill --model`, so its default
*is* the no-AI lane, the same argument that made `NoFiller` not-a-flag. `mendel build` has no AI
path at all until the tier-4 ambiguity resolver arrives with Plan 3.

**Registry.** Public curated base — the `comeni-registry` repo, data files with signed tags —
plus zero or more private overlays via repeated `--registry`. A lab that never publishes is
the normal case. Contributing upstream is a proposal into the forge queue.

**Pipelines are publishable artifacts**: one `pipeline.yml` carrying the goal, every step and
setting with a `why:`, every contract pinned by content digest, every layer, and the gate
verdict — the four-part `Goal` + `PipelineIR` + `DecisionRecord[]` + lockfile bundle is retired
into it (Plan 1.10). Three tiers — private, published (mechanical gate: stub-run then
`-profile test`), curated (**a named human signs off**; never mechanical). Editing a curated
pipeline replays every untouched decision from its record, so only what you touched can move.
See the federation spec.

**Telemetry is opt-in and off by default.** Invariant 1 is what enforces it: telemetry lives
in `mendel-api`, and a network call added to `comeni-core`, `mendel-resolver` or
`mendel-compiler` fails `tests/test_purity.py` or `tests/test_purity_runtime.py`.

This used to be sold as *structural* — "the pure packages **cannot** import an HTTP client" —
and that was false as written. Audit A1 built a `comeni_core/telemetry.py` importing only
allowlisted names that opened a TCP socket and shipped a `Goal` down it, with the guard green.
The guards are now stronger and the claim is now weaker, which is the right direction for
both: **cost-raising, not a proof.** A determined author of code in this repository can still
reach the network from a pure package. What they cannot do is reach it *by accident*, or
reach it and have the tests say nothing.

**Releases are per package, and versions are independent.** Tags are
`<package>-v<version>` — `comeni-core-v0.2.0` — and pushing one runs
`.github/workflows/release.yml`, which refuses if the tag and that package's `pyproject.toml`
disagree. **`0.0.x` for a fix, `0.x.0` for a feature, `x.0.0` for a break**; a new diagnostic
code is a *feature*, because a runbook can cite it, and a `SCHEMA_VERSION` bump is always a
break for `comeni-core`. The bump is judged, not derived — read
`docs/guides/releasing.md` before cutting one. GitHub Releases only; no PyPI, decided
2026-08-16.

**Every GitHub Action is pinned by commit SHA with its version in a trailing comment**, and
Dependabot rewrites both. A mutable `@v7` can be repointed by whoever controls the action, which
is the one part of the supply chain invariant 1's posture had not reached. `tests/test_workflow_pins.py`
holds it.

**Licences.** Code Apache-2.0 (`LICENSE`). Registry data CC-BY-4.0, in `comeni-registry` with
its own `LICENSE` — contracts cite papers, so attribution matters. Root `LICENSE-DATA` was
deleted with issue #46: a licence file for content the repository no longer holds is a claim
about nothing. Vendored nf-core modules keep their own.

**Repo status.** `github.com/comeni-project/Comeni-Labs`, transferred to the org on
2026-08-03 and **public since 2026-08-04**. `README`, `CONTRIBUTING` (a root stub pointing at
`docs/guides/contributing.md`, because GitHub reads the root path), `SECURITY` and `CHANGELOG`
are in place, CI runs on every pull request, and the nightly
workflow runs the stub gate.

The org is the **umbrella**, not one of the products — `comeni-labs`, `comeni-code` and
`comeni-registry` sit under it as equals. Naming `comeni-labs` as the org was considered and
rejected for that reason: Comeni Code is not a Lab, so `comeni-labs/comeni-code` reads wrong.

Bare `comeni` is unavailable everywhere that matters — the GitHub user, and `comeni.org`,
`comeni.com` and `comeni.net` are all registered and parked. `comeni.eu` was free as of
2026-08-03 and is the recommended umbrella domain: it keeps the bare brand, and the clinical
positioning is already IVDR- and GDPR-shaped. **No domain has been bought yet.**

**Because it is public now**, two things follow. Write for a stranger: `docs/` is split by
audience — `guides/`, `reference/`, `concepts/`, `design/` — and `notes/` holds the
plans and audits, labelled as working notes rather than documentation. And **auto-phylo is
not discussed**: it was removed from the prior-art section on 2026-08-04 by the operator's
decision. `pegi3s` appears only as what is useful about it — a repository of ~190
containerised tools with documentation, and a future forge ingestion source.

## Open issues

Tracked at `github.com/comeni-project/Comeni-Labs/issues`, because a loose end named only in a
conversation is a loose end lost.

| # | What | Blocked on |
|---|---|---|
| ~~1~~ | routing ties should ask a human; scoring should vary by purpose | **closed 2026-08-14** as `not planned`, in a bulk pass. Reopen it rather than rediscovering it |
| ~~2~~ | `sealed` must block tier-3 decisions on asserted measurements | **closed 2026-08-14** as `not planned`, in a bulk pass. Reopen it rather than rediscovering it |
| ~~3~~ | generated `.d.ts` and a `/measurements` endpoint | **closed 2026-08-14** as `not planned`, in a bulk pass. Reopen it rather than rediscovering it |
| ~~4~~ | ~~`DataProfile` belongs in `comeni-core`~~ | **done** — it lives in `comeni_core/goal/profile.py` |
| ~~7~~ | goal extraction: what crosses door 1, per protection profile | **closed 2026-08-14** as `not planned`, in a bulk pass. Reopen it rather than rediscovering it |
| ~~8~~ | ~~the emitted spine is not runnable~~ | **done** — Plan 1.5 |
| ~~10~~ | ~~answering a tier-4 parameter clears the flag without changing the pipeline~~ | **done** — Plan 1.10. `via:` carries the value to the tool, and an override keeps its tier while leaving `needs_review()` |
| ~~11~~ | revise the v1 criterion — the module count measures surface area | **closed 2026-08-14** as `not planned`, in a bulk pass. Reopen it rather than rediscovering it |
| ~~16~~ | signed publish bundles: the egress guard forbids `bytes`, so signing must be detached | **closed 2026-08-14** as `not planned`, in a bulk pass. Reopen it rather than rediscovering it |
| ~~18~~ | the error surface is half-declared — most `raise` sites are bare `ValueError`; `MD0300`–`MD0399` reserved | **closed 2026-08-14** as `not planned`, in a bulk pass. Reopen it rather than rediscovering it |
| ~~38~~ | the measurement vocabulary has no author, and it gates every tier-3 rule | **the floor is closed, the drafter is not (2026-08-15).** Twelve measurements where there were six, derived from the twenty corpus rules, each cited and each declaring whether a tool can produce it (`assertion_only`, `MD0315`). **Five of the original six turned out to be assertion-only, including `strandedness`.** What remains open is the *drafter*: nothing writes a measurement, and the issue's sharpest point is that the drafting question and the measuring question are the same one — a contract has `meta.yml` as ground truth and a measurement has no equivalent. That is Plan 2's forge |
| ~~39~~ | the tier-3 rule format cannot express the rules the forge will need | **closed 2026-08-15.** Plan 1.15 narrowed it to arithmetic; a `derives:` **`transform`** closes that — a chain of *named unary operations with a literal operand*, left to right. No parser, no precedence, and no way to name a second fact, which is what §13.2 asked for: arithmetic without a solver. **Nineteen of the twenty-one corpus rules load**; R02b is the contortion, newly caught by `MD0311`, and R20 is refused by design |
| ~~43~~ | data storage — one SQL source, or data spread across files? | **closed 2026-08-16.** Files, and it is the modern convention rather than a local quirk — nixpkgs, Homebrew, conda-forge, Bioconda and nf-core modules all keep human-curated catalogue data as files in git. `docs/design/declared-data.md` is the argument, including why crates.io moving its index off git does not transfer |
| ~~46~~ | move the registry completely out of this repo | **closed 2026-08-16.** `registry/` is a git submodule pinned at `v0.2.0`; all 33 test files that load `ROOT / "registry"` are unchanged, and the drift subsystem is deleted rather than repointed |
| ~~48~~ | a tier-4 setting's `why.reason` stays stale after a human answers it; `MD0223` is blind to `for_value: null` | **closed 2026-08-16.** Three conditions — no recorded value, tier 4, and a `human_override`. Answering a tier-4 question is now a two-part edit, and the one-part edit exits 2 |
| ~~49~~ | `MD0000`–`MD0099` reserved and empty; loading refuses with a Pydantic traceback | **closed 2026-08-16.** `MD0001`–`MD0009`. Six were existing refusals gaining a prefix; only the YAML and schema wraps are new, and both sit in `stack()` because that is the one place every kind loads through |
| ~~41~~ | code and documentation organisation | **closed 2026-08-16.** Eleven tasks, three emitted digests unmoved. `comeni_core` is five subpackages by lifecycle stage, the working notes left `docs/` for `notes/`, and `make links` checks every relative link in `docs/` and the root |
| 67 | `mendel explain` never shows the `fix:` field — the long form is the code and the explanation only | undecided; one change, since `forge explain` calls the same function |
| 64 | `forge check` is offline — it compares the registry against the *vendored* source, never against upstream | after the forge MVP, by the operator's decision 2026-08-16 |
| 77 | the catalogue cannot report a real total — discovery reads only vendored modules, so `forge discover` sees **13 tools** rather than the ~1,600 nf-core + pegi3s will bring. The Tools board renders `—` rather than `13`: an absence is not a zero. Distinct from #64, which is about *checking* against upstream | needs a `Source.catalogue()`, and a decision about caching — the board must stay inside 0.5s, so it is the worker's job, not the request's |
| 65 | the pegi3s source adapter — a container registry, and what may honestly be read out of documentation prose | designed for rather than built; `tests/opaque_source.py` is its shape, so the `Source` protocol has had two implementations since day one |
| ~~24–36~~ | round four's thirteen carried findings, A60–A69 and A73–A75 | **all closed 2026-08-15.** The guards were hardened rather than the findings argued away: alias resolution in two scans, six stdlib transports banned, nine ID aliases given a shape, the publication payload frozen, and the totality guard given paths instead of names |

## Commands

`make help` lists them. `make check` is exactly what CI runs on a pull request.

**`make check` is not verification of a change to `resolve.py`, `router.py`, `rules/`,
`mendel_compiler/cli/`, `mendel_compiler/emit.py` or `comeni_core/artifact/pipeline.py`.** It
deselects `tests/test_counts.py` — the three tests that run `--gate test` on the nf-core
dataset and assert the counts matrix is right, that featureCounts got the strandedness that
was measured, and that a resolved setting reached the tool. That is the only check exercising
the v1 criterion. Touch any of those six files and run **`make verify`**, which is `check` +
those three + the guards, and takes about two minutes.

`emit.py` and `pipeline.py` joined the list in Plan 1.10, and three of the six became
directories in issue #41 — the rule holds for anything under them. Rewriting `emit()`'s signature and
its `ext.args` composition is precisely the kind of change `make check` waves through: nothing
outside `test_counts.py` runs a tool, so a flag that stops reaching one is invisible to every
other test in the repository.

The files are named rather than left to judgement on purpose: Plan 1.8 changed all four and
reported each task verified on `make check` alone. Nothing was broken and the omitted tests
took 44 seconds, so the cost was never the reason — there was a habit, and no command that
made the full set the easy thing to type. See A14.

```bash
uv sync                          # set up the workspace
make check                       # lint + tests + stub freshness — the CI gate, ~1 min
make verify                      # check + counts matrix + guards; Docker, ~2 min
make static                      # conformance + nextflow lint + preview; no Docker, ~6s
uv run pytest -v                 # all tests; no test may call a live model
uv run ruff check .              # lint (line length 100)
uv run pytest tests/test_purity.py tests/test_purity_runtime.py \
  tests/test_egress.py tests/test_construction.py               # the guards

# why anything was refused, at length. The bands are in diagnostics.yml; the generated page
# is the count. docs/reference/diagnostics.md is generated from comeni_core/diagnostics.yml —
# `make docs` regenerates it, and CI checks it. A code is DECLARED there and EMITTED through
# `coded()`, and both directions are tested: emitted-but-undeclared, and declared-but-never-
# emitted. Never write a code into a string by hand.
uv run mendel explain MD0104

# vendor an nf-core module (needs vendor/.nf-core.yml, vendor/modules/, vendor/conf/)
uvx nf-core modules install --dir vendor samtools/sort

# build a pipeline from a typed goal, no AI involved
uv run mendel build --goal examples/rnaseq-goal.yml --out build/ --gate stub

# `build/pipeline.yml` IS the pipeline: every step, setting, decision and reason.
# Edit it, then rebuild the Nextflow from it — no registry, no network.
uv run mendel emit build/pipeline.yml --out build/

# re-resolve against the current registry. --dry-run is `verify` and writes nothing.
uv run mendel upgrade build/pipeline.yml --out next/
uv run mendel upgrade build/pipeline.yml --dry-run

# certify a built directory: gate it, and stamp the verdict into pipeline.yml
uv run mendel publish build/pipeline.yml --gate test

# emit a pipeline that measures, plus profile.yml naming what measures what
uv run mendel profile --have fastq.reads --out profile-build/

# one Markdown page per tool, from the registry data alone. --check is what
# comeni-registry's CI runs; it writes nothing and exits 1 on a stale page.
uv run mendel docs --registry registry/ --out /tmp/tool-docs

# regenerate the measurement type stub; --check is what CI runs
uv run python tools/generate_types.py

# same build, with the lab's private contracts stacked over the public registry
# a layer is a directory of files that each carry a `declares:` line
uv run mendel build --goal examples/rnaseq-goal.yml \
  --registry registry/ --registry ./lab-registry --out build/

# the forge: where declared data comes from. docs/guides/driving-the-forge.md is the loop.
uv run forge sources                       # the ingestion sources registered
uv run forge discover                      # every tool a source can read
uv run forge draft nf-core:fastqc --name fastqc --version 0.12.1
uv run forge show fastqc                   # filled fields, and every hole with its reason
uv run forge fill fastqc roles qc_per_sample --list --by "$USER" --why "it QCs a sample"
uv run forge verify fastqc                 # the five-rung ladder
uv run forge check                         # does the registry still match its sources
uv run forge land fastqc --registry ../comeni-registry --by "$USER"

# --registry is REQUIRED for `land` and defaults for everything else. Landing is the one
# verb with a git commit behind it, and registry/ here is a submodule at detached HEAD.
```

`make dev` brings up the whole stack — Postgres, Redis, the API, the worker and nginx — and
starts Vite on the host for HMR; `make prod` runs the same stack with the unsafe parts removed;
`make migrate` applies migrations;
`make client` regenerates `frontend/src/api/` from the API's own schema. **Never hand-edit
that directory** — a generated client is what makes the IR types unable to drift between
the halves, and editing it is how that guarantee is lost quietly.

**`ruff format` is not a gate and CI does not check it.** 28 files are hand-wrapped in ways
the formatter would undo; a formatting sweep belongs in its own reviewable commit rather than
as noise across every future pull request.

## v1 success criterion

From a plain-language prompt plus a test dataset, Mendel emits Nextflow that runs green on
the nf-core test profile and produces a counts matrix. Target is the **RNA-seq spine** —
~15–20 modules on the canonical path, *not* the full `nf-core/rnaseq` decision tree with its
alternative aligners, pseudo-aligners and UMI handling. That breadth is v2.

**Status after Plan 1.5** — a `test` profile is emitted, so `Gate.TEST` runs; the spine
executes on the nf-core RNA-seq test dataset and produces a counts matrix, and
`tests/test_counts.py` asserts featureCounts ran with the strandedness that was measured.
What remains unmet is the plain-language prompt (Plan 2) and the module count: **10 distinct
processes, not 15–20**. The remainder are QC breadth — `samtools stats`/`flagstat`/`idxstats`,
duplicate marking, RNA-specific QC — not correctness.

**Whether that clause survives is [#11](https://github.com/comeni-project/Comeni-Labs/issues/11),
and it is undecided.** The argument there is that a module count measures surface area, and a
pipeline with twenty modules that ignores every parameter is worse than one with ten that does
not. Do not quietly build toward the number, and do not quietly drop it — this criterion has
already been wrong once, when it named a gate that could not pass.

## Gotchas

- **`nf-core` `meta.yml` is a scaffold, not a contract.** It declares outputs as
  `type: file` with a filename pattern; `samtools/sort`'s output and `star/align`'s
  `bam_unsorted` are both `type: file, *.bam`. "Sorted" exists only in the English
  description. The semantic `state` overlay is the missing ~40% and is what routing depends
  on.
- **Routing: a contract cannot satisfy its own input, and surplus ranks candidates.**
  `SAMTOOLS_SORT` consumes and produces `alignment.bam`, so it is a candidate for its own
  dependency and recurses forever without cycle exclusion. And `producers_of` matches on superset,
  so an empty requirement matches every producer — ranking by `(surplus, -priority, id)` keeps
  "get me a BAM" from silently meaning "get me a sorted BAM".
- **Entry channels come from the vocabulary, not the compiler.** A type declares `entry_channel`;
  `mendel-compiler` has no built-in idea what a FASTQ is. Same reason `nf_inputs` is declared
  rather than parsed: it has to work for a pegi3s image or an in-house process too.
- **`frozenset` has no stable order.** `IREdge.states` carries a `field_serializer` that
  sorts on output. Byte-identical emission is a hard requirement; anything new that
  serialises a set needs the same treatment.
- **`-stub-run` is the fast validation tier.** nf-core modules all define stub blocks, so the
  whole DAG executes with dummy outputs in seconds. Iterate the repair loop there; only the
  final candidate pays for `-profile test`.
- **`--no-ai` must keep working forever** once something adds it — which nothing has. Forge
  Phase 2 made the forge able to call a model and did *not* add the flag: `forge fill --model`
  is opt-in, so there is nothing to switch off and nothing to leave accidentally on. It becomes
  meaningful when the tier-4 resolver lands in Plan 3, and then it is how the deterministic
  guarantee stays testable and the mode CI runs in. `--registry` is repeatable and
  ships in Plan 1, since Task 5 builds the stacking it exposes.
- **Import modules, not symbols, where tests monkeypatch.** `from x import f` binds past a
  later patch of `x.f`.
- **`uv sync` installs nothing you don't depend on.** `[tool.uv.sources]` says *where* a
  workspace member comes from; the root project must also list it in `dependencies` or it is
  never installed and imports fail.
- **A contract port is not a process argument.** Only one of six spine processes matches its
  port count — `featurecounts` takes one channel carrying two ports, `samtools/sort` takes three
  of which two model nothing. `ModuleContract.nf_inputs` declares the real signature, and
  `NfInput.empty` carries the **tuple width**, because Nextflow matches arity and a 2-tuple in a
  3-tuple slot dies on "Path value cannot be null".
- **Read process names and containers out of `vendor/modules/**/main.nf`, never out of a plan.**
  It is `SUBREAD_FEATURECOUNTS`, not `FEATURECOUNTS`. nf-core 4.x mostly uses
  `community.wave.seqera.io`, not quay.io — take the *last* quoted string in the `container`
  ternary. `tests/test_spine_contracts.py` compares contracts against the modules on disk so a
  guess fails in milliseconds instead of at pipeline launch.
- **CI has no Nextflow, and a developer machine does.** `make check`'s lane installs neither
  Nextflow nor Docker, so **any test passing `--gate` to `mendel build` is green locally and red
  in CI** — `mendel: gate lint: FAIL / nextflow not found on PATH`, exit 1. Omit `--gate` unless
  the test is *about* gates; `tests/test_pipeline_file.py::_build` is the shape to copy. The two
  tests in `test_gates.py` that genuinely need it are `skipif`-guarded on
  `shutil.which("nextflow")`. **Check it by shadowing rather than by remembering**: put a
  `nextflow` on `PATH` that exits non-zero and run the fast suite — anything that fails and is
  not in `test_gates.py` was relying on your machine. That is how a `run_gate` monkeypatch on the
  wrong module was found (#41) and how a stray `--gate lint` was found the next day (#49).
- **The stub gate needs Docker and ~900s on a cold cache.** nf-core 4.x captures versions with
  `eval()`, which runs even under `-stub-run`, so the tool must exist — hence
  `-profile stub_data,docker`. Without `docker.runOptions = '-u $(id -u):$(id -g)'` every work
  directory is root-owned and undeletable by whoever made it.
- **`nextflow lint` writes errors to stdout; `nextflow run` writes them to stderr.** Read
  `GateResult.output`, which is both.
- **Jinja: `{% endfor %}`, never `{%- endfor %}`.** With `trim_blocks` the dash eats the line
  ending and every loop iteration collides onto one line. Read the golden file before committing
  it — that is what caught it.
- **Guards must be watched failing.** `test_purity.py` and `test_egress.py` only mean something
  because someone broke them on purpose and saw the message. Doing that to the egress guard found
  a hole: a bare `user_note: str` passed every rule it had.
- **A `.pyi` replaces its module rather than adding to it.** A stub covering half a module
  makes the other half invisible to every type checker — a correctness cost, not an
  autocomplete one. `tools/generate_types.py` emits the whole public surface of
  `comeni_core.goal.profile`, and a test asserts it stays complete and parses.
- **A producer pin binds only where the pinned contract is a candidate.** featureCounts asks
  for `alignment.bam[coordinate_sorted]`, whose only producer is the sorter; the aligner rule
  applies one level down, on the sorter's own BAM input. Treating a pin as binding everywhere
  makes the spine unroutable. `UnroutablePinError` is for the genuine contradiction — pin
  selected, its own inputs unreachable.
- **`build/` in `.gitignore` swallowed a vendored module.** It was meant for the CLI's default
  output directory and also matched `vendor/modules/nf-core/hisat2/build/`, so the module every
  short-read decision depends on was never committed and no test noticed — the main checkout had
  the files untracked on disk. A worktree is what surfaced it. Anchor such patterns: `/build/`.
- **`-stub-run` cannot see a hollow input.** nf-core stubs never read their inputs, so a
  process handed `Channel.value([[:], []])` where a genome belongs is exactly as green as one
  handed a genome. Two shipped that way — STAR built an index from nothing and aligned against
  no annotation. `NfInput.empty` now requires a `because`, and only `--gate test` catches the
  rest.
- **A resolved value needs somewhere to go.** nf-core modules read `task.ext.args` and `meta`;
  a `params.<x>` in the emitted workflow is read by nothing. `ModuleContract.ext_args` carries
  flags a module always needs. Measured facts go through `meta`, where the module does its own
  translation — which is why the strandedness rule was deleted rather than wired: `-s 2` is
  featureCounts' encoding of a fact, not a decision, and the module already contains it.
- **Emptiness and deadness are different problems.** Few parameters and no defaults is
  *emptiness*, and it is the forge's job — hand-authoring a registry was never the plan. A
  resolved value reaching no tool is *deadness*, and no amount of forge output fixes it.
- **A contract is a hand-written FFI binding.** `mendel build` checks every contract against
  the vendored module and refuses to emit if they disagree — `mendel explain MD0104` for any
  code. Where module source is absent the contract is marked `unverified` on the IR rather
  than trusted. Never assert a conformance property over modules that were not readable: the
  first version reported every declared `meta_key` dead when no module source existed at all.
- **The port name is the emit label.** `produces[].name` is what the compiler reads as
  `PROCESS.out.<name>` — it is not a name for the semantic thing, which is what `type_id`
  carries. Three contracts got this wrong and MD0105 found all three; each was latent only
  because no goal had yet routed to that port.
- **Declared data is files, and a database is a design error — `docs/design/declared-data.md`.**
  Decided 2026-08-16 (issue #43). Every comparable catalogue — nixpkgs, Homebrew, conda-forge,
  nf-core modules — keeps human-curated data as files in git, because a database has no diff,
  blame, review, signature or merge, and those five *are* what a reviewed, cited registry sells.
  `diagnostics.yml` is the TypeScript/Rust shape already: one declarative file, generated
  consumers. A database is legitimate only as a **derived, gitignored index** once loading is
  measurably slow, which at 37 files it is not.
- **There is no vector memory store, and there is none for the MVP** — decided 2026-08-17,
  narrowing a flat "adding one is a design error". Mem0/Zep/Letta answer "what did this user
  say before". Mendel's institutional memory is `contracts/`, `rules/`, `vocabularies/` and
  decision records — versioned, approved, diffable, citable. A fuzzy recall layer beside them
  could influence resolution without passing the forge, which breaks invariant 2. Federation is
  registry distribution, solved by git and a lockfile.
  **What replaced the generic argument is a measurement**: grounding a model in the registry
  turned out to need *exact* retrieval, not similarity — `candidates.for_field` names which
  contracts already use each role and type, and every fact it retrieves is versioned,
  attributable to an approving human, and visible in a diff. Embeddings would give the same
  shape of help with none of those properties, and exemplar *ranking* at scale is `ORDER BY`
  rather than cosine distance.
  **At scale it is needed, and the case is specific rather than general** (operator, 2026-08-17):
  **proposal deduplication** and **analogy retrieval**. Once a model can propose vocabulary
  entries, two drafts will propose `qc.report` and `quality.summary` for one thing — an exact
  lookup cannot see that they are the same, and no `ORDER BY` finds "contracts like this tool"
  when the role is exactly what is unknown. Those two are semantic by nature. Reach for a store
  when *those* problems appear, not for "the AI needs memory".

## Testing

Mirrors the purity split — this is what makes the determinism claim auditable rather than
rhetorical.

- `core` / `resolver` / `compiler`: **golden-file tests.** Goal in → exact IR out → exact
  `.nf` out. No network, no model, milliseconds. A change in generated Nextflow shows up as a
  reviewable diff in CI.
- `mendel-ai`: contract tests against recorded fixtures committed to the repo.
- End-to-end: the `-stub-run` gate runs **nightly** in `.github/workflows/nightly.yml`, not
  per commit — it needs Docker and up to ~900s cold, which is too slow to gate a pull
  request and too important to run only before a release. `.github/workflows/ci.yml` is the
  fast lane: ruff, pytest and the generated-stub check, on 3.12 and 3.13.

## Prior art

`../braidworks` (same author) is the direct ancestor of the typed-routing model: declared
consumes/produces contracts, a registry graph, plan-then-execute separation, and confidence
and review flags carried as data rather than raised as exceptions. Read
`docs/architecture.md` there when the contract model is unclear.

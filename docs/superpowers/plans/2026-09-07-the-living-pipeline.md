# The Living Pipeline — Conversational Build and Spawn MVP

> **For Claude:** REQUIRED DESIGN STEP: invoke Claude's `frontend-design` skill (called
> `frontend/design` in the earlier project plan) for Task 1. Produce and inspect the named
> artboards and interaction storyboard before changing production React. Then use an
> executing-plans workflow and implement one task at a time. Run the narrow check for each task
> before widening the suite. Do not grow the current `Builder.tsx` monolith and do not delete
> the working manual builder until the replacement has passed Task 14's browser walk.

**Date:** 2026-09-07

**Status:** in progress — Tasks 1 to 10 complete

**Goal:** Replace the builder's unwired one-shot Assistant placeholder with a durable,
continuous authoring conversation. A researcher describes what they have, what they want to do,
and what they want to obtain; Comeni restates the analysis, builds a typed pipeline visibly one
step at a time, offers real registry-backed choices, fills parameters transparently, and keeps
the canvas and `pipeline.yml` preview synchronized. The same engine supports **Build** (guided)
and **Spawn** (automatic) policies.

**Product phrase:** the draft is a **living pipeline**. The conversation, canvas, settings, and
YAML preview are views of one changing draft, not four competing representations.

**Architecture:** A model turns natural language into a typed `Goal` or a typed authoring intent.
The existing resolver—not the model—constructs the complete pipeline blueprint. An authoring
service converts that blueprint into ordered, typed proposals. Build waits for the person at
meaningful decisions; Spawn accepts every safe proposal and uses the declared tier-4 resolver
for the remaining closed choices. The browser owns proposal previews, optimistic reveal,
selection, layout transitions, and animation. The server owns model access, registry truth,
provenance, persistence, authoritative validation, and canonical YAML serialization.

**Primary path:** describe → confirm goal → resolve blueprint → reveal/choose modules → answer
open settings → review living pipeline → keep → gate → run.

**Tech stack:** Python 3.12, FastAPI, Pydantic, SQLAlchemy/Alembic, ARQ/Redis, `comeni-ai`, React
19, TanStack Query, the existing canvas primitives and product tokens, CSS/Web Animations API.
Do not add a frontend state library, animation library, or YAML library for this MVP.

---

## 0. Current reality and reuse map

The implementation agent should read these before editing:

- `CLAUDE.md`, especially the product claim, the three runtime AI points, invariant 6, and the
  current-state notes about the builder and input cardinality.
- `frontend/src/build/Builder.tsx`, `useBuilder.ts`, `useGraph.ts`, `usePipelineDraft.ts`,
  `Rail.tsx`, `Sources.tsx`, `Node.tsx`, `Wires.tsx`, `ArtifactView.tsx`, and `useKeep.ts`.
- `frontend/src/home/First.tsx`: the natural-language door is deliberately disabled today.
- `packages/mendel-api/src/mendel_api/routes/build.py` and `services/build.py`: `Goal` already
  resolves to a laid-out `BuiltPipeline`; `DraftGraph` already draws and validates.
- `packages/mendel-api/src/mendel_api/models.py`, `jobs.py`, `ai_worker.py`, and the Forge job
  services: these are the durable-state, queue, pending-turn, and invocation-audit precedents.
- `packages/comeni-core/src/comeni_core/goal/asked.py` and `goal/profile.py`: the typed boundary
  for what the user has, wants, and knows about the data.
- `packages/comeni-core/src/comeni_core/artifact/egress.py`: goal extraction is already pipeline
  egress door 1. Evolve that door deliberately; do not create a quiet sixth door.
- `packages/comeni-core/src/comeni_core/artifact/pipeline.py`: `AiPoint.PROMPT`, `TIER_4`, and
  `REPAIR` are the three runtime AI points. This plan does not add a fourth.
- `packages/mendel-resolver/src/mendel_resolver/ports.py`: `AmbiguityResolver` is the existing
  seam for tier-4 model choice.
- `packages/mendel-resolver/src/mendel_resolver/materialise.py`: drawn graphs are currently
  attributed wholesale via `by`. A mixed human/resolver/model session needs finer provenance.
- `packages/mendel-compiler/src/mendel_compiler/pipeline_file.py`: this is the only canonical
  YAML serializer. Reuse `dump`; never reproduce it in TypeScript.
- `packages/comeni-ai/src/comeni_ai/`: provider-neutral validated generation and conversation.
  The deprecated `packages/mendel-ai/` is a compatibility shim and must receive no new code.
- `docs/notes/journal/2026-09-01-the-fan-out-and-the-sheet.md`: in this repository “fan-out”
  already means that N sample items must produce N process invocations; it is not only graph
  branching.

What exists now:

| Existing seam | Reuse |
|---|---|
| `Goal -> orchestrate.build -> BuiltPipeline` | complete blueprint and authoritative reasons |
| `DraftGraph` plus `validate` and `draw` | editable working graph |
| compatibility index and candidate endpoint | local wire checks and real alternatives |
| `useGraph` | local graph operations; extract/reuse, do not fork its rules casually |
| server layout plus client-owned offsets | stable final coordinates and immediate gestures |
| ARQ AI queue | slow authoring/model work with visible pending state |
| `AiInvocation` | shared audit row; `agent="builder"` was anticipated by its design |
| `PromptTemplate`, `Client`, `choose_one`, `converse` | versioned prompts and validated replies |
| `Scope.SAMPLE`, `Scope.RUN`, `StepInput.gather` | collection flow and N→N/N→1 semantics |
| existing Run orchestration | keep → lint → run sheet → submit after authoring |

What is wrong with the present interaction:

- `Rail.Assistant` is static copy and explicitly says the result will never be chat.
- `First` shows the prompt but disables it.
- the manual builder surrounds the graph with implementation-oriented controls instead of
  guiding a researcher through the analysis.
- the graph shows one channel but does not explain “many items”, “once per sample”, or “collect
  all”; `PortView` even documents a doubled many-port encoding without carrying cardinality.
- `Builder.tsx` is already a large integration component. Adding a transcript, job lifecycle,
  proposal cards, and motion directly to it would make the feature unmaintainable.
- `DraftGraph` is saved as a whole and `ir_of(..., by=...)` attributes the whole drawing to one
  author. A living session can contain resolver decisions, model decisions, and later human
  changes in the same draft.

Build the new surface beside the old one, reuse its small primitives where they still fit, and
cut over only after a real browser walk.

---

## 1. Decisions Claude should not reopen during implementation

### 1.1 “Living pipeline” names one draft

Conversation, canvas, settings, validation, and YAML preview must all address the same draft id
and revision. A chat message must never hold a private graph that is later copied into the real
builder. A direct canvas edit must appear in the conversation as a compact receipt, and a choice
accepted in the conversation must appear on the canvas immediately.

The conversation is workflow history. `DraftGraph` remains the working pipeline shape.
`pipeline.yml` remains the durable artifact. Deleting or truncating chat history must not change
what a kept pipeline means.

### 1.2 Build and Spawn are policies over one proposal engine

Do not implement two builders.

| Behaviour | Build | Spawn |
|---|---|---|
| Goal summary | person confirms or edits | show and proceed when valid; pause only on material ambiguity |
| Resolver tiers 1–3 | reveal with reason; continue | accept automatically |
| Tier-4 closed choice | show candidates and wait | ask model through `AmbiguityResolver` |
| Missing candidate/model refusal | wait visibly for a person | also wait; never fabricate |
| Settings | reveal progressively | fill deterministic/model-safe values, leave human gaps |
| Result | `DraftGraph` | the same `DraftGraph` |

Mode is chosen when the session starts and recorded. An optional “finish automatically” action
may switch Build to Spawn only if Task 1's design makes it clear; do not make mode switching a
prerequisite for the MVP.

### 1.3 The model never authors YAML, graph JSON, UI markup, or compatibility

The model may return only declared Pydantic response shapes:

- an understood `Goal` plus a short summary and typed open questions;
- one of a closed set of authoring intents;
- a choice from candidate ids supplied by the server;
- a bounded explanation referring to known step/question ids;
- a proposed goal or setting revision that still requires validation and, when consequential,
  explicit acceptance.

It must never return `DraftGraph`, `Pipeline`, YAML, React/HTML, coordinates, arbitrary API
calls, or invented module alternatives. The registry and resolver already own those answers.

### 1.4 Resolve the whole blueprint, reveal it incrementally

After goal confirmation, resolve the complete pipeline once. Store the resulting pipeline and
registry digest as the session blueprint. Order proposals deterministically by the existing
layout's `(rank, order, id)` or an equivalent topological order.

The complete blueprint solves two problems:

1. Each “next module” is selected with downstream compatibility already known; the agent does
   not make locally plausible choices that later dead-end.
2. The browser knows each proposed node's final target position before reveal, so nodes can
   materialize and wires can grow without the graph jumping after every response.

Build still presents one module at a time. Keeping the blueprint private in session state is not
the same as spawning it into the draft.

### 1.5 Client owns immediacy; server owns authority

Client-side:

- render the transcript and typed blocks;
- preview a candidate as a ghost node on hover **and keyboard focus**;
- optimistically reveal an accepted proposal;
- animate nodes, wires, parameters, collection markers, and YAML highlights;
- keep selection synchronized between chat and canvas;
- use the cached compatibility index for drag/hover feedback;
- pan, zoom, move nodes, edit fields, and maintain transient UI state;
- reconcile an optimistic state with the authoritative response.

Server-side:

- model/provider calls and prompt history bounds;
- registry lookup, resolution, candidates, and compatibility truth;
- stamping who made each decision;
- session, turn, proposal, and draft persistence;
- revision checks and stale-proposal refusal;
- authoritative validation and canonical `pipeline_file.dump` output.

Do not add WebSockets or token streaming for the MVP. POST a turn, render it immediately as
pending, enqueue it on the existing AI queue, and poll only while work is pending. The Forge
already proves that lifecycle.

### 1.6 Linear-first is a UI scope, not a destructive graph restriction

Optimize Task 1 and the MVP walkthrough for a primary left-to-right analysis chain. Do not build
branch creation, branch labels, conditionals, loops, or branch rejoining controls now.

Do not make existing DAGs invalid and do not delete the existing wire model. If a resolver
blueprint contains an auxiliary branch, lay it out with the existing engine and render it with
neutral wires. The guided conversation may describe the primary chain first and auxiliary steps
afterward. General branch authoring is a later design problem.

### 1.7 Many files are a collection, not many graph nodes

The MVP visual grammar must cover:

- **1→1:** one run-scoped value, such as a reference;
- **N→N:** a sample/item-scoped channel processed once per item;
- **N→1:** a gathering input such as MultiQC collecting all reports.

Render one logical channel with `×N`, `many items`, or a known safe count—not N copies of the
node or N parallel wires. If `measurement.n_samples` is present, the UI may say `×12 samples`.
Otherwise say `×N items`; do not invent a file or sample count. Actual filenames and sample ids
remain run-time data and must not enter Mendel merely to decorate the canvas.

The input grouping question is part of goal understanding: “24 files” may mean 24 independent
items, 12 paired samples, several lanes per sample, or one combined dataset. Do not infer one
silently.

### 1.8 Provenance is per decision, not per session

A resolver-settled step must keep its original tier and reason merely because Build paused to
explain it. A person choosing a different candidate becomes the human author of that choice. A
tier-4 choice made in Spawn records the configured model id. A later manual edit must not relabel
the untouched rest of a spawned pipeline as human.

Add a server-owned provenance sidecar to `PipelineDraft`; do **not** accept it in `DraftIn`.
Define a closed Pydantic shape under `comeni_core.plan` that can retain, by node/setting/channel
key, the original `Why` and any `DecisionRecord` needed to materialize the accepted choice.
`PipelineDraft` stores its JSON dump. `drafts.update` diffs the old and new graph: unchanged
items retain provenance, changed/new items are stamped human by the server, and removed items
lose their sidecar entry. Authoring-service commits stamp resolver/model/human origins directly.

Extend `materialise.ir_of` to accept this optional sidecar. `None` must preserve today's manual
builder behaviour byte for byte. Never put trusted provenance fields into browser-writable
`DraftGraph` merely because that is the easiest payload to send.

### 1.9 An authored draft retains the confirmed Goal

Add a nullable, server-owned `goal` JSON column to `PipelineDraft`. A conversational draft uses
the confirmed `Goal`; an old/manual draft with no stored goal continues to use `goal_of(graph)`.
This prevents the incremental graph from replacing the researcher's requested constraints with
the narrower goal derivable from whichever nodes happen to be visible at that moment.

### 1.10 YAML grows as a projection, never as appended model text

Add a read-only preview service that materializes the current draft in memory and returns
`pipeline_file.dump(pipeline)` without writing an artifact. The client may diff successive text
and animate changed lines or sections. The final Keep action still validates, writes, reads back,
and stages modules through the existing compiler path.

For an unchanged draft revision, preview bytes before Keep and artifact bytes after Keep must be
identical except for fields that Keep intentionally stamps. Put that relationship in a test.

### 1.11 Motion follows domain events

Animate `proposal_shown`, `proposal_accepted`, `edge_committed`, `parameter_committed`,
`proposal_rejected`, and `validation_changed`. Do not animate arbitrary fetch completion or model
tokens. Provide `prefers-reduced-motion` behaviour from the first animation task. Use CSS
transitions/keyframes or the Web Animations API; do not add an animation dependency unless the
design checkpoint demonstrates a concrete missing capability and records the reason.

---

## 2. Authoring state and protocol

Use closed enums and discriminated Pydantic unions. Names may be adjusted to existing style, but
the protocol must express these states rather than infer them from absent fields.

```mermaid
stateDiagram-v2
    [*] --> understanding: initial prompt stored
    understanding --> goal_review: typed goal returned
    understanding --> failed: provider/refusal exhausted
    goal_review --> resolving: person accepts goal
    goal_review --> understanding: person revises in prose
    resolving --> building: blueprint stored
    resolving --> failed: build/provider failure
    building --> building: proposal accepted/rejected
    building --> complete: no proposal remains
    building --> resolving: accepted goal revision
    complete --> resolving: accepted goal revision
    failed --> understanding: retry prompt call
    failed --> resolving: retry build
```

Suggested durable records:

| Record | Owns |
|---|---|
| `PipelineAuthoringSession` | draft id, mode, phase, confirmed goal, blueprint, registry digest, cursor, row version, timestamps |
| `PipelineAuthoringTurn` | ordered user/assistant content, pending/answered/failed state, base revision, invocation id, timestamp |
| `PipelineAuthoringProposal` | discriminated proposal payload, pending/accepted/rejected/stale state, chosen option, actor, draft revision |

One session has at most one pending mutation proposal in the MVP. Explanatory assistant turns do
not need a proposal. Every mutating request carries `expected_revision`; a stale acceptance
returns a coded conflict and changes nothing.

Suggested frontend/server blocks:

```text
narrative        bounded prose, optionally referring to known step ids
goal_summary     typed Goal plus plain-language have/do/get summary
question         one typed question with closed options or a declared open value
step_proposal    process, contract, ports, reason, tier, alternatives
setting_request  setting, current value, domain, reason and premise
change_set       exact nodes/settings affected by a conversational revision
receipt          immutable account of a committed direct or conversational edit
notice           pending, refusal, stale, validation or completion state
```

Every interactive block has a stable id. Every option has a stable id. The browser posts ids and
the expected revision, not a copied contract object. Render blocks with an exhaustive TypeScript
switch so a new backend kind fails typechecking until it has a UI.

Bound conversation context. Follow the Forge precedent (`CHAT_TAIL = 6`) unless evaluation shows
a different number is needed. Ground every authoring call on the confirmed goal, current known
step ids/contracts, current pending options, registry digest, and bounded tail—not on the
transcript alone. Exclude draft labels, filenames, paths, tool output, and run data.

---

## 3. File structure

Expected new backend files:

| Path | Responsibility |
|---|---|
| `packages/mendel-api/src/mendel_api/authoring/types.py` | modes, phases, block/proposal/response schemas |
| `packages/mendel-api/src/mendel_api/authoring/prompts.py` | committed prompt ids and loader |
| `packages/mendel-api/src/mendel_api/authoring/prompts/builder.goal.v1.md` | prose → typed goal |
| `packages/mendel-api/src/mendel_api/authoring/prompts/builder.chat.v1.md` | follow-up → typed authoring intent |
| `packages/mendel-api/src/mendel_api/authoring/state.py` | pure session/proposal transitions |
| `packages/mendel-api/src/mendel_api/services/authoring.py` | persistence, blueprint ordering, proposal commits |
| `packages/mendel-api/src/mendel_api/services/authoring_ai.py` | context, model calls, admission, invocation audit |
| `packages/mendel-api/src/mendel_api/routes/authoring.py` | HTTP transport only |
| `packages/mendel-api/migrations/versions/<revision>_living_pipeline.py` | sessions, turns, proposals, draft columns |

Expected new frontend files should live under `frontend/src/build/living/`, not at another
top-level route and not inside the existing `Builder.tsx`:

| Path | Responsibility |
|---|---|
| `LivingBuilder.tsx` | small screen composition only |
| `useAuthoringSession.ts` | queries, pending polling, mutations and reconciliation |
| `authoringReducer.ts` | transient client state and optimistic reveal |
| `Conversation.tsx` | transcript and composer |
| `blocks/*.tsx` | one renderer per discriminated block kind |
| `LivingCanvas.tsx` | accepted, proposed and selected pipeline views |
| `CollectionChannel.tsx` | 1→1, N→N and N→1 visual grammar |
| `motion.ts` | event-to-animation policy and reduced-motion helper |
| `ArtifactPreview.tsx` | canonical text plus client-side changed-line emphasis |

The design skill may improve these component boundaries. Keep the ownership boundaries even if
the filenames change.

Expected modified seams:

- `comeni_core.plan.draft`, `artifact.egress`, and the egress guards;
- `mendel_resolver.materialise.ir_of`;
- `mendel_api.models`, migrations, `jobs`, `ai_worker`, `main`, draft service/routes, build view;
- generated `frontend/src/api/schema.d.ts` via `make client`, never by hand;
- `frontend/src/api/types.ts`, home prompt, router, and the existing builder cutover seam;
- handbook pages and a dated journal entry only after the live walkthrough.

---

## Task 1 — Design the living pipeline with Claude's design skill

**Required skill:** Invoke Claude's `frontend-design` skill (`frontend/design` in the prior
plan). State in the implementation transcript that the skill is being used. This is an explicit
deliverable, not advice.

**Read first:** `frontend/src/tokens.css`, `main.css`, current build components, the builder
handbook page, and the 2026-08-29/30 builder design journal entries. Preserve the product's visual
identity, but do not preserve the current builder's information architecture merely because it
exists.

**Create:** a source-controlled `.design/living-pipeline/` package with a README naming the
artboards, their dimensions, interaction states, and the exact command used to render them.
Follow the existing `.design` convention: source, not screenshots alone.

- [x] Design a desktop Build state with the living canvas and conversation as the two primary
  surfaces; inspection, problems, browsing, and YAML are contextual surfaces.
- [x] Design the opening composer with a clear Build/Spawn choice.
- [x] Design goal summary, edit, ambiguous grouping question, module proposal, alternatives,
  parameter question, pending model, refusal, validation finding, completion, and stale proposal.
- [x] Design hover **and focus** preview of an alternative as a ghost node/substitution.
- [x] Design Spawn's rapid staged reveal without pretending each automatic choice was human.
- [x] Design collection flow for `×N items`, `×12 samples`, `once per item`, and `collect all`.
- [x] Design widths near 1440, 1180, 900, and a narrow stacked layout. No essential operation
  may require hover or a desktop pointer.
- [x] Design reduced-motion equivalents for every animation-bearing state.
- [x] Put difficult content in the artboards: long contract ids, four ports, long reasons, a
  failed model turn, and 15 modules. A design that works only on five short boxes is not done.
- [x] Open the rendered artboards side by side and record the comparison in the design README.
  Do not approve a design by reading its HTML or source.

**Checkpoint:** no production React changes before the artboards and interaction storyboard are
inspectable. The design should explicitly label what is MVP and what is deferred branching.

### Execution record — 2026-09-07

`frontend-design` was invoked and followed. Nothing under `frontend/` was touched.

**Delivered:** [`.design/living-pipeline/`](../../../.design/living-pipeline/) — eleven
artboards at 1400×880 generated from one fixture by `build_living.py`, a shared `_lhead.html`,
`canvas.living.json` with twelve notes arguing the decisions, and a README carrying the design
plan and the board-by-board comparison record. Registered in `.design/README.md` and
`.gitignore`.

| Step | Carried out as written? | Deviation |
|---|---|---|
| desktop Build state | yes | `LivingBuild` |
| opening composer, Build/Spawn | yes | `LivingOpen` |
| the eleven interaction states | yes, plus one board | *completion* had no home until `LivingDone` was added, which also draws the artifact/YAML surface the first ten boards omitted |
| hover **and** focus preview | yes | `LivingChoose` draws both, with the same ghost |
| Spawn's staged reveal | yes | `LivingSpawn` |
| collection flow | yes | `LivingCollect` — this is the board that needed the most iteration |
| 1440 / 1180 / 900 / narrow | **deviated** | authored at **1400**, matching the twenty-four existing artboards and `_prev.py`'s default, rather than the plan's 1440. The breakpoints are 1180 and **1000** — a third one, argued in `LivingQuiet` and the README |
| reduced motion | yes | `LivingQuiet`, and no new movement was added: six domain events map onto the five existing ones |
| difficult content | yes | `LivingDense` — fifteen steps, a 52-character contract id, a five-port signature |
| open them side by side | yes | the README's comparison table is the record. Twenty defects, none visible in the HTML |

**Three things a reader of the plan should know before Task 2:**

1. **`impl-settled`'s *no prompt box on the populated page* was examined and not overturned.**
   The rail is not a creation affordance; it is the pipeline's provenance record made
   navigable, and it appears on an authoring session only. The argument is in
   `canvas.living.json`'s `n-settled` note and the README.
2. **Two encodings are proposed that the product does not have**, both extensions of a language
   it does: *author is drawn as stroke while tier stays colour*, and *collection is drawn on the
   wire*. `tokens.css` is unchanged and no hue was added.
3. **The canvas is not where a large pipeline is read.** `LivingDense` took three attempts and
   the finding is that beyond about six steps you pan, and the transcript carries the whole. That
   is the strongest argument for the collapsed decision row, and it should shape Task 9 and
   Task 10.

**Two additions outside `.design/living-pipeline/`:** `_prev.py` gained a `--dir` flag (the
boards live in a subdirectory) and the shared head carries the breakpoints, so `--width 900`
renders the stacked layout rather than a squeezed 1400. Without that the narrow pass was
meaningless, which is how the first nine boards passed it.

---

## Task 2 — Define the typed authoring protocol and egress boundary

**Files:** create `authoring/types.py`; modify `artifact/egress.py`; add focused schema and guard
tests.

- [x] Write failing tests for every block discriminator, proposal state, phase transition input,
  extra-field refusal, bounded prose, stable ids, and mutually exclusive reply fields.
- [x] Define `Build` and `Spawn` as a closed enum and define the session, turn, proposal, and
  response DTOs.
- [x] Define separate model-response shapes for initial goal understanding and follow-up intent.
  Keep the JSON schema shallow enough for the local model; prefer one object with validated
  exclusive fields over a deeply nested union if recorded evaluation proves it follows better.
- [x] Evolve pipeline egress door 1 from a bare initial prompt into a declared authoring request
  that can carry the bounded tail, current `Goal`, known steps, and offered option ids safely.
  Keep it one pipeline door and keep `AiPoint.PROMPT`; update their prose to match reality.
- [x] Add each genuinely new free-text field to `tests/guards/test_egress.py` explicitly. Do not
  weaken the recursive allowlist or smuggle a serialized graph through one `Text` field.
- [x] Add a test that draft labels, paths, run inputs, samplesheet rows, and tool output are not
  reachable from the authoring request.
- [x] Run `uv run pytest tests/guards/test_egress.py packages/mendel-api/tests/test_authoring_types.py -v`.

**Checkpoint:** an authoring request and reply can be explained field by field; neither can carry
YAML, a graph, arbitrary API verbs, or untyped context.

---

### Execution record — 2026-09-09

`make check`: **2470 passed**, 118 skipped, up from 2450. Task 2's own command
(`pytest tests/guards/test_egress.py packages/mendel-api/tests/test_authoring_types.py`) is 69
passed.

| Step | Carried out as written? | Deviation |
|---|---|---|
| failing tests first | yes | 19 in `test_authoring_types.py`, plus two guard changes. Three were **watched failing against the specific defect**: `chose` as a plain `str`, the exclusivity validator deleted, and `Notice` dropped from the union |
| `Build`/`Spawn` closed enum; session, turn, proposal, response DTOs | **deviated** | `Mode`, `TurnState`, `ProposalState`, the eight blocks and both reply shapes are here. There is **no `Session` DTO** — §2's session record owns a blueprint, a cursor and a row version, which are durable columns and Task 3's subject. What Task 2 defines is the vocabulary a session is made of; defining the record here would have meant guessing the schema Task 3 writes |
| separate goal/follow-up reply shapes, shallow | yes | `GoalUnderstanding` and `AuthoringIntent`, one level deep. Exclusivity is a `model_validator`, not a nested union — the plan's own preference |
| evolve door 1; keep one door and `AiPoint.PROMPT` | yes | `PromptRequest` → `AuthoringRequest`; `goal_extraction` and `DoorPath.PIPELINE` unchanged, so `test_pipeline_data_still_leaves_through_exactly_four` never moved. `PromptRequest` is **retired**, not kept beside it |
| new free-text fields listed explicitly | yes | two: `AuthoringRequest.prompt` (the same field renamed) and `AuthoringTurn.content` (genuinely new). The recursive allowlist was not touched |
| a test that labels, paths and samples are unreachable | yes | `test_the_authoring_door_cannot_reach_a_name_a_path_or_a_sample`, written as a **mark allowlist**. Both halves watched failing: an `NfPath` field, and a `draft_name: Text` |

**Three things a reader should know before Task 3:**

1. **`Goal` was free to carry.** It reaches door 1 with **zero** free-text fields anywhere in the
   seven models below it, and it already crosses door 4 as `Pipeline.goal` — so it was already
   past the leaf allowlist and the taint surface did not widen. That was checked before the
   field was added, not after.
2. **The containment test found a mark the author had not listed.** `Mark.PORT_NAME` reaches
   door 1 through `Goal.have`. Harmless, and the point is that reading the fields did not find
   it — `Goal` brings its own vocabulary and the walk is what noticed.
3. **A new `Mark.OPTION_ID` exists**, with an `OptionId` alias validated as a bare identifier.
   That is what makes *a model cannot produce a value outside the candidate set* a property of
   the type rather than a check somebody remembers to run: prose, a path and a contract body are
   all refused before anything asks whether the option was offered.


## Task 3 — Persist sessions without making the database the pipeline

**Files:** modify `models.py`; add one Alembic migration; create `authoring/state.py` and
`services/authoring.py`; update model, migration, and fixture cleanup tests.

- [x] Write the migration/model tests first. The offline Alembic comparison must fail before the
  migration exists.
- [x] Add the three authoring workflow tables described in §2 with RESTRICT foreign keys and no
  cascade. Add a unique one-session-per-draft constraint if the design does not support several.
- [x] Add `goal`, provenance sidecar, and integer revision columns to `pipeline_draft`. Backfill
  old rows as `goal = null`, empty provenance, revision 0; those rows must still open and keep.
- [x] Explain each table in its model docstring using the repository's test: deleting authoring
  history must not change a build, while deleting the pipeline draft still removes the working
  copy. Do not store contracts, types, credentials, provider errors, or runtime sample data.
- [x] Implement the pure state machine and compare-and-swap transitions. A stale proposal becomes
  `stale` or returns a coded conflict; it never applies to a newer draft.
- [x] Make turn order explicit and stable. A user turn appears immediately; its assistant turn
  can be pending, answered, or failed.
- [x] Add service tests for reload, retry, duplicate delivery, two-tab stale acceptance, and a
  session whose model call finishes after the draft changed.
- [x] Update exact-table guards deliberately and run:
  `uv run pytest packages/mendel-api/tests/test_models.py packages/mendel-api/tests/test_migrations.py packages/mendel-api/tests/test_authoring_state.py -v`.

**Checkpoint:** restart the API between creating a session and reading it; the transcript,
pending proposal, confirmed goal, draft, and revision all return unchanged.

---

### Execution record — 2026-09-09

`make check` (no database, as CI runs it): **2496 passed**, 131 skipped. Task 3's own command
plus the service tests, against a real Postgres: **51 passed**.

| Step | Carried out as written? | Deviation |
|---|---|---|
| migration/model tests first, offline comparison failing | yes | the comparison named all three tables and **36 columns** before the migration existed. The harness already existed and is generic, so adding the models *is* the failing test |
| three tables, RESTRICT, no cascade, unique one-session-per-draft | yes | verified in a real database, not only in rendered DDL: all five foreign keys report `confdeltype = r` |
| `goal`, provenance, revision on `pipeline_draft`, backfilled | yes | verified by inserting a pre-migration-shaped row and reading back `goal IS NULL`, `provenance = {}`, `revision = 0` |
| each table explained by the repository's test | yes | and the exact-table guard's own docstring now carries the argument for all three |
| pure state machine and compare-and-swap | yes | `authoring/state.py`. Two mutations watched failing: the stale check removed, and the duplicate-delivery check removed |
| turn order explicit and stable | yes | `seq`, with a unique index on `(session_id, seq)`. `at` is not an ordering |
| service tests for the five scenarios | yes | all five, plus the checkpoint. Two mutations watched failing: a late model answer applied anyway, and a refused acceptance bumping the revision |
| update exact-table guards **deliberately** | **more than written** | the exact-table list, *and* `clean_forge` — see below |

**Four things a reader should know before Task 4:**

1. **`failed_from` is a column the plan did not ask for, and §2 requires it.** The diagram draws
   **two** arrows out of `failed` — back to `understanding` and to `resolving` — and `phase`
   alone cannot choose between them. This is `ForgeAdaptation.failed_stage`'s argument arriving a
   second time, and without it a failed build is retried as a prompt call, which re-asks a person
   a question they have already answered.
2. **`clean_forge` had to change, and that is the cost of a shared audit table.**
   `pipeline_authoring_turn` references `ai_invocation`, so truncating it without naming the
   authoring tables is refused by Postgres — **94 errors**, all from one fixture. That table was
   built to be shared (`agent` is the column saying whose call it was) and the living pipeline is
   the second agent to use it. A third adds a line to that fixture.
3. **`Settlement.refusal` carries a `coded()` message, not a bare code**, and
   `test_every_declared_code_is_emitted` is what forced it. `MI0202` was declared, appeared in
   the generated diagnostics page and answered `mendel explain`, while no code path could
   produce it — the string was being assembled by hand.
4. **Five tests in `test_forge_jobs.py` and `test_full_cycle.py` fail on this branch and are not
   ours.** Verified against a database migrated to `d3b81c5a4f07` with this work stashed: the
   same five, with the same `MF0001: 'fake' is not a catalogue source`. They are database-gated,
   so CI has never run them.

**The checkpoint was run literally.** One process created a session, wrote a turn, moved it to
`goal_review` with a goal and left a proposal pending; a **second interpreter** read back the
phase, the goal, the revision, both turns in order and the pending proposal, unchanged.


## Task 4 — Preserve mixed decision provenance

**Files:** modify `comeni_core.plan.draft`, `mendel_resolver.materialise`, draft services/routes,
and their tests.

- [x] Write a failing test containing three nodes: one resolver-settled, one model-selected, and
  one later replaced by a person. Keep it and assert all three sources, ids, tiers, and reasons
  in `pipeline.yml`.
- [x] Define the server-owned provenance sidecar from §1.8. Prefer closed lists keyed by declared
  `NodeId`/`DecisionKey` over free-form mappings. Keep it separate from browser-writable graph
  data.
- [x] Teach `ir_of` to reuse accepted selection/presence/setting provenance when supplied and to
  retain today's all-human semantics when it is absent.
- [x] Teach draft creation/update to preserve unchanged sidecar entries and stamp changed graph
  choices as human. Test node replacement, parameter edit/clear, channel scope edit, deletion,
  and a pure position move—which must change no pipeline provenance.
- [x] Use a stored confirmed goal when present; preserve `goal_of(graph)` for old/manual drafts.
- [x] Remove the whole-draft `by` shortcut only when every caller has moved; until then retain a
  compatibility wrapper and prove it produces the old bytes.
- [x] Run the materialisation, artifact, draft service, and provenance tests before broader API
  work.

**Checkpoint:** editing one setting in a spawned draft changes the author of that setting only.
Untouched steps remain attributed to the resolver/model that actually chose them.

---

### Execution record — 2026-09-09

`make check`: **2506 passed**, up from 2496. With a database, the API suite is 439 passed and the
same five pre-existing `forge_jobs`/`full_cycle` failures Task 3 recorded.

| Step | Carried out as written? | Deviation |
|---|---|---|
| failing test with three differently-settled nodes | yes | `packages/mendel-resolver/tests/test_provenance.py`, 12 tests, all eight failing before `ir_of` learned the parameter |
| server-owned sidecar, closed lists, keyed by declared aliases | **deviated** | `ChannelSettled` is keyed by the **ports** a channel feeds, not by its name. A channel's name is *derived* — `channels_of` computes it from the registry — and `drafts.update` diffs two graphs without loading one. Keying on the derived thing would make every edit pay for a registry load to answer a question the draft already contains |
| `ir_of` reuses provenance; `None` keeps today's semantics | yes | two tests hold the byte-for-byte promise, and `DraftProvenance()` is asserted equal to `None` so that an edit which retains nothing is not a different pipeline |
| creation/update preserve, stamp, and drop | yes | all five cases. **A position move is structural**: `DraftGraph` carries no coordinates, so a drag produces a byte-identical graph and the diff is never reached — the test is what notices if a coordinate is ever added |
| stored confirmed goal when present | yes | asserted through `keep` and read back out of `pipeline.yml`, not through the helper that reads the column |
| keep `by` until every caller moves, prove the old bytes | yes | `test_the_whole_draft_by_still_produces_the_old_bytes` |
| run the four suites | yes | plus the whole API suite against a real Postgres |

**Three things a reader should know before Task 5:**

1. **`Pipeline.of` gained an `ai` parameter, and Task 4 did not ask for it.** It had to: `MD0225`
   refuses a setting recording that a model settled it in a build recording `ai.available: []`,
   and that field was **hardcoded empty** in `materialise.of`. A model-authored setting could not
   reach `pipeline.yml` at all. It is **stated by the caller, never derived from the sidecar** —
   deriving it would make the check circular, since a value claiming a model settled it would
   certify that a model was there to settle it. A Spawn draft kept without declaring one is
   refused, and `test_a_spawned_draft_kept_without_declaring_a_model_is_refused` holds that.
   Task 6's authoring service is what actually knows the configuration.
2. **`drafts._load` now returns `Stored(graph, provenance, goal)`.** Reading the sidecar beside it
   was a *second* storage read, and it broke eight tests that stub the seam — correctly, because
   two reads means two authorities on whether a draft exists and only one of them is stubbed. The
   server-owned columns travel with the graph or they are a second source of truth.
3. **A stamp is written explicitly rather than left to `ir_of`'s fallback.** Dropping a changed
   entry would let the fallback decide, and the fallback follows the whole-draft `by` — so a
   person editing one step of a Spawn draft later kept with `by=<model>` would have their edit
   recorded as the model's. An explicit `HUMAN` stamp cannot be reinterpreted by whoever calls
   `keep`.

**Watched failing against the specific defect:** the diff with nothing recognised as unchanged —
the old whole-draft behaviour — fails five of these tests, including the checkpoint. And
`test_a_persons_setting_keeps_its_own_words` was found to pass **with or without** the sidecar
being read, because the fallback for a typed value is already `HUMAN`; a discriminating test
(`test_a_model_answered_setting_is_not_attributed_to_a_person`) was added and the param path only
then turned out to be ignoring provenance entirely.


## Task 5 — Implement versioned goal and authoring prompts

**Files:** add the authoring prompt package, prompt files, `services/authoring_ai.py`, fixtures,
and prompt/response tests. Add `comeni-ai` as an explicit `mendel-api` dependency; do not import
from deprecated `mendel_ai`.

- [x] Write `builder.goal.v1`: convert the user's have/do/get language into a typed `Goal`, a
  concise summary, and only questions whose answers can change the pipeline. Include declared
  type and measurement vocabulary; reject invented ids during admission.
- [x] Make file grouping explicit in the prompt. “Many FASTA/FASTQ files” must produce either a
  safe typed interpretation or a grouping question, never an assumed sample structure.
- [x] Write `builder.chat.v1`: return explanation, goal revision, option selection, setting
  proposal, continue, or unsupported. No generic mutation command and no arbitrary tool id.
- [x] Ground the prompt on the declared authoring request and bounded tail. Model explanations
  must refer to known step/question ids; reject invented references.
- [x] Use `Client.respond`/`converse` and record prompt id, digest, model, provider, timing, token
  counts, state, and safe failure code in `AiInvocation` with `agent="builder"`.
- [x] Add recorded/fake transport cases for paired RNA-seq counts, many independent FASTA items,
  paired-file ambiguity, a goal correction, “why STAR?”, selecting an offered alternative, an
  invented option, invalid JSON, provider failure, and no configured model.
- [x] Assert prompt templates ship in the built wheel and are immutable by version: behavioural
  changes add `v2`, never edit a prompt already cited by an invocation.
- [x] Run the authoring AI tests without a live provider.

**Checkpoint:** the recorded cases either return an admitted typed reply or a visible coded
refusal. No test reaches the network. **Met** — 21 cases, every refusal carrying a declared code,
and the transport is a seam every test supplies by hand.

**Five things a reader should know before Task 6:**

1. **It is the first writer of `ai_invocation`.** The table, its migration, its `agent` column and
   its place in `clean_forge` have existed since the forge workflow landed, and nothing ever wrote
   a row: the forge's review chat calls a provider and records nothing. `agent="builder"` is what
   that column was built for. **The forge joining it is still owed** and is not Task 5's to do.
2. **`Client.generate`, not `respond`.** The step says `respond`/`converse`; both were tried and
   neither is right here. `respond` sends a prompt as-is, which would mean pasting each reply
   shape's JSON Schema into a committed `.md` — a second copy of a Pydantic model, stale the
   first time a field moves. `generate` with no evidence appends the schema after the rendered
   template, so the instruction is still last and the shape is shown rather than described.
   `converse` is unused because the bounded tail is rendered into the template's own
   `{{conversation}}` section, which is what puts it inside the digest.
3. **The protocol gained three intents, and Task 2 had shipped three.** §1.3 names six things a
   chat reply may be, and `AuthoringIntent` could express half of them — so a prompt naming
   *continue* would have had it come back as an empty `explain`. `setting`, `proceed` and
   `unsupported` were added, plus `refers_to` so an explanation's step references are a set
   difference rather than a regex over English. `GoalUnderstanding` gained `questions`, because a
   first call with nowhere to put the grouping question can only infer one.
4. **A model-raised question carries labels and never option ids.** `AskedQuestion` is
   deliberately not a `Question`: the engine mints the ids when it stores it, so the next turn's
   `chose` is checked against a set the engine issued rather than one the model wrote itself.
5. **A fake transport rather than recorded fixtures, and the reason is which thing is under
   test.** `RecordedTransport` keys on a digest of the exact prompt, which is right for the Forge,
   where the question *is* the subject. Here the subject is admission and audit — what happens to
   an answer on the way back in — and keying on the prompt would turn every wording change in a
   committed template into ten `KeyError`s. The prompts have their own tests next door.

**Watched failing against the specific defect:** neutering the two refusal branches in
`_admit_goal` and `_admit_intent` — `if unknown:`/`if invented:` → `if False:` — fails exactly the
six admission tests and leaves the other two in that selection passing. Before that, the wheel
guard was watched by building one, and the two grouping phrases were found missing because the
prose had wrapped them across a line break, which is the failure that assertion exists to catch.

**One defect found by a constraint rather than a test:** the first `clean_invocations` fixture
truncated the authoring tables and `ai_invocation` alone, and Postgres refused it — `forge_message`
references `ai_invocation` too. The fix was to delete the rival fixture and use `clean_forge`,
whose docstring already said so.

**Reused rather than added:** `MI0106` covers *no model is configured* for the builder as well as
the forge, with `authoring` added to its `fires_on`; `InvocationState` is imported from
`mendel_forge.workflow` because a refused call and a failed one mean the same thing whoever made
it. `Purpose` is declared locally, because purposes genuinely are per-agent and `agent` is the
column that separates a builder `chat` from a forge one.

---

## Task 6 — Add the tier-4 model adapter and blueprint engine

**Files:** add a builder-owned `AmbiguityResolver`; extend authoring service and build view tests.

- [x] Implement the adapter through the existing `AmbiguityRequest` door and `choose_one`. It can
  choose only an offered candidate and returns `Resolution` with model id, reason, confidence,
  and `ValueSource.MODEL`.
- [x] Build mode resolves with the flag-only path so tier-4 questions remain visible. Spawn mode
  resolves with the model adapter. A declined/no-candidate ambiguity remains open in both modes.
- [x] Store the complete resolved `Pipeline`, registry digest, and proposal order as the session
  blueprint. Do not ask the model to enumerate modules after the resolver already did.
- [x] Convert the blueprint to step proposals in deterministic layout/topological order. Include
  incoming edges only when both endpoint steps have been accepted.
- [x] Populate alternatives from the resolver's decision candidates and existing candidate
  service. Never ask the model to invent a plausible alternative list.
- [x] On accept, commit the step/edge/settings into the session's draft and provenance sidecar in
  one transaction. Return the new revision and next proposal.
- [x] A resolver-settled proposal acknowledged unchanged retains its resolver provenance. A
  person choosing a tier-4/default or alternative option records a human decision. Spawn's
  model-selected tier-4 choice records the model.
- [x] Detect a changed registry digest before applying a stored proposal. Mark it stale and
  re-resolve rather than applying an option against a registry that no longer supplied it.
- [x] Test a one-step pipeline, the RNA-seq example, N→N flow, an N→1 gatherer, a branched
  blueprint rendered in deterministic order, and a model refusal.

**Checkpoint:** identical goal + registry + policy produces identical blueprint/proposal order.
No per-module model calls occur for tiers 1–3. **Met** —
`test_the_same_goal_and_registry_and_policy_give_the_same_blueprint` compares the stored bytes, and
`test_spawn_calls_no_model_for_anything_the_resolver_settled` runs Spawn against a transport that
records every prompt and finds none.

**Six things a reader should know before Task 7:**

1. **Door 2 had never been crossed.** `AmbiguityRequest` was declared in Plan 1 and the only place
   in the repository that constructed one was the egress guard's own totality test.
   `resolver.request_for` is its first producer, and it is written as `model_dump()` minus `kind`
   because that is exactly the shape the guard proves — two spellings would be two shapes.
2. **A declined tier-4 answer falls back to the flag rather than failing the build.** `choose_one`
   refuses a value outside the offered set; the adapter then resolves exactly as Build would have.
   A provider outage turns one Spawn question back into a Build question, not a failed session.
   A question with **no** candidates still raises `NoCandidatesError`, as `FlagOnlyResolver` does,
   so whether a build fails never depends on the mode.
3. **`Resolution.confidence` stays `0.0`**, and the step said to return a confidence. `choose_one`
   returns a value and a sentence, and a model's self-rating is not a measurement; what separates a
   model's answer from the flag is `how=MODEL` and `by=<model id>`, which are facts. Invariant 6
   flags tier 4 at any confidence, so nothing downstream reads it.
4. **The shipped registry produces no producer tie**, so Spawn's model path is exercised at the
   adapter level (13 tests with a fake transport) and not end to end — the spine's one tier-4
   question has `[None]` as its only candidate and is never put to a model. A real tie needs an
   overlay with two conforming contracts, which is fixture work Task 12 is better placed to do.
5. **Alternatives exclude any contract that consumes the type it would stand in for.** Found
   twice by running rather than reading: the first smoke run offered `samtools/sort` as an
   alternative to STAR, and the first test run offered MultiQC to FastQC. Both *produce* the type
   and both *consume* it — `CLAUDE.md`'s *a contract cannot satisfy its own input*, which the
   router enforces and the candidate service, answering a narrower question, does not.
6. **`pipeline_authoring_session.registry_digest` was `String(64)` and a `Digest` is 71
   characters.** A Task 3 defect: Postgres would have refused the first blueprint ever stored, and
   nothing stored one until now. The unpushed migration was widened to 80 in place, and the
   defect was reproduced for real before the fix — a database migrated at the old revision
   refused all seven commit tests with `value too long for type character varying(64)`.
   **`forge_revision.registry_digest` has the same shape** (`forge_jobs.py:960` writes a full
   `Digest` into `String(64)`), predates this plan, and is not fixed here.

**Deviations:** a third committed prompt, `builder.tier4.v1`, because `choose_one` takes a
question and a question sent to a provider is product code; tier-4 calls are kept in memory by
the adapter and written by `authoring_ai.record_calls` after the build, because the adapter runs
inside the resolver's loop, which must stay free of I/O; and a registry that moved re-resolves
*within* `building` rather than adding an arrow to §2's diagram — the session never leaves the
phase, only its blueprint changes, and `MI0206` says so.

**Watched failing against the specific defect:** committing an edge regardless of acceptance
fails the two edge tests and nothing else; never noticing a moved registry fails only the stale
test; and letting a tier-4 default keep the flag's `resolver` label fails only the human-author
test. `test_accepting_every_step_rebuilds_the_blueprint_through_ir_of` is the one that holds the
whole commit: a fully accepted draft, materialised through `ir_of`, names the same contracts,
wires and authors at the same tiers as the blueprint.

**`make check` skips every database test**, and not because of this task: the Makefile's
`-include .env` re-exports `MENDEL_DATABASE_URL`, overriding one set on the command line. The API
suite was run directly against a throwaway Postgres — 528 passed, and the 5 failures are the
pre-existing `MF0001: 'fake' is not a catalogue source` ones.

---

## Task 7 — Expose the authoring API and queue lifecycle

**Files:** create `routes/authoring.py`; modify `main.py`, `jobs.py`, `ai_worker.py`; add route,
OpenAPI, worker, and health tests.

Minimum surface:

```text
POST /api/pipeline/authoring
GET  /api/pipeline/authoring/{session_id}
POST /api/pipeline/authoring/{session_id}/messages
POST /api/pipeline/authoring/{session_id}/proposals/{proposal_id}/decide
POST /api/pipeline/authoring/{session_id}/retry
GET  /api/pipeline/authoring/{session_id}/preview
```

Exact paths may follow existing router style, but every operation needs a stable `operationId`.

- [x] Create an empty draft and authoring session together, store the initial user turn, enqueue
  one AI job with a semantic id, and return 201 with the visible pending state.
- [x] Post follow-up turns as 202. Use `jobs.job_id_for("builder", "turn", session, turn)` so
  at-least-once delivery cannot produce two answers.
- [x] Add the authoring job to the AI worker allowlist and keep it off the ordinary worker.
- [x] Let deterministic proposal acceptance remain a normal request; do not put a button click
  behind the slow queue.
- [x] Polling GET returns the whole authoritative session view needed to restore the page. Bound
  pagination only if the transcript evaluation actually needs it; do not truncate history on
  screen merely because model context is bounded.
- [x] Return visible no-model, refused, failed, stale, and retry states. Do not log or return raw
  provider errors.
- [x] Extend AI health only if the existing endpoint cannot explain why Build/Spawn is disabled.
- [x] Regenerate the client with `make client`; never hand-edit `schema.d.ts`.
- [x] Run route/worker/OpenAPI tests and `git diff --exit-code frontend/src/api/schema.d.ts`
  only after the generated file has intentionally been reviewed and staged in the change.

**Checkpoint:** submit a turn with a fake queued job, reload immediately, observe pending, run the
job, reload, and observe the admitted assistant blocks exactly once. **Met, and taken one step
further** — `test_a_turn_is_pending_on_reload_and_answered_exactly_once` then delivers the job a
second time and finds the transcript unchanged, one model call, and one `ai_invocation` row.

**Five things a reader should know before Task 8:**

1. **Exactly once is two mechanisms, and only one of them is the job id.**
   `builder:turn:<session>:<seq>` collides a re-delivery at the queue; `turn_context` returning
   `None` for a turn that is no longer pending stops a delivery that slipped past Redis's memory
   *before* a call is spent. Removing the second fails the checkpoint on its model-call count.
2. **Accepting a goal moves the draft revision.** The confirmed goal becomes the draft's goal,
   which changes what keeping it builds, and Task 3's rule is that any acceptance is a change to
   the draft. A client must read `revision` from the decide response rather than assume it.
3. **A missing model and an unreachable one fail the session; a refused answer does not.**
   `MI0106`, `MA0002`, `MA0003` and `MA0007` move to `failed`, where `retry` adds a *new* pending
   turn rather than reopening the failed one — whose notice is the record of why. `MA0004` and the
   admission codes leave the phase alone, because the person can say it differently.
4. **A goal revision while building is not implemented.** §2 draws `building → resolving` on an
   accepted goal revision; this task answers a revision during `goal_review` by re-understanding
   it, and during `building` or `complete` with a notice saying to start a new session. It needs
   a proposal that can replace a whole blueprint, which is a design question, not a route.
5. **`Goal` is now `Goal-Input` and `Goal-Output` in the generated client.** Pydantic emits two
   schemas once a model with a serializer appears in a response as well as a request, and the
   session view returns the confirmed goal. Nothing in `frontend/src` referenced the old name and
   `tsc` is clean, so FastAPI's global `separate_input_output_schemas` was left alone.
   **Correction, recorded in Task 10:** that `tsc` was `tsc --noEmit -p .`, which checks nothing.

**Deviations:** `authoring_jobs.py` rather than extending `jobs.py`, following `forge_jobs.py`'s
arrangement, with its own `AI_JOBS` set — the existing
`test_the_two_worker_function_lists_are_disjoint` held the AI allowlist equal to the forge's set
and failed when the builder's jobs arrived, and it now holds it equal to the union of every
owner's declared set rather than to a list written in the worker. AI health was not extended:
`configured` and `worker_available` already explain why Build and Spawn are unavailable, and the
session view adds `model_configured` for the page itself. `preview` shares `keep`'s
materialisation through one extracted function, so the two cannot disagree about the text.

**Watched failing against the specific defect:** dropping the pending check from `turn_context`
fails only the checkpoint test. The provider-failure test reaches the page with an endpoint in the
exception and asserts the address is absent from the response body.

---

## Task 8 — Build the client-side session controller

**Files:** create `frontend/src/build/living/useAuthoringSession.ts`, `authoringReducer.ts`, and
focused tests; extend the generated-type seam in `frontend/src/api/types.ts`.

- [x] Model transient states explicitly: server snapshot, optimistic proposal acceptance,
  previewed option, selected step, animation event queue, composer text, and reconciliation.
- [x] Keep server data in TanStack Query and interaction state in a reducer. Do not mirror the
  entire query response into ad-hoc `useState` fields.
- [x] Poll only while the session or newest turn is pending. Stop on answer, refusal, failure, or
  unmount.
- [x] Apply an accepted proposal optimistically from the already received typed payload. Disable
  only that proposal while its request is in flight; the canvas remains inspectable.
- [x] Reconcile by proposal id and revision. On a stale/conflicting response, discard the
  optimistic event and show the server notice; never silently overwrite newer work.
- [x] Reuse or extract `useGraph` operations for direct editing after the guided build. Do not
  maintain separate graph mutation rules for “chat graph” and “manual graph”.
- [x] Do not persist prompt/transcript content to `localStorage`. Durable state already lives on
  the server; transient drafts in the composer may use component state.
- [x] Test reducer transitions with plain objects and fake timers before component tests.

**Checkpoint:** reducer tests reconstruct the same visible graph from a fresh server snapshot as
from the optimistic event sequence that produced it. **Met** —
`draws the same graph from the optimistic sequence as from the server's snapshot after it` compares
three pictures: optimistic, reconciled, and fresh.

**Four things a reader should know before Task 9:**

1. **The server gained two fields, and the plan's own rules required both.** The session view
   carries the draft `graph` — the canvas cannot restore from one read without it — and a step
   proposal carries the `edges` accepting it would add, because *apply an accepted proposal
   optimistically from the already received typed payload* cannot draw wires from a node alone.
   The server computes those edges with the same filter `committed` uses, and
   `test_a_proposal_carries_exactly_the_wires_accepting_it_would_add` holds the two equal.
2. **Only the proposal as offered is drawn early.** Choosing an alternative disables the card and
   waits: its wires depend on its ports, and a guessed wire the server then removes is a picture
   corrected in front of the person.
3. **Reconciliation is two rules, and a mutation found that one of them had no test.** A drawing
   retires when the server's revision passes the one the request was made against, or when its
   proposal is no longer pending once the request has returned. Disabling the revision rule
   failed nothing — the id rule covered every existing case — until a test for the real race
   was added: a poll that sees the commit before the POST's own response resolves.
4. **`useGraph`'s mutation rules are now `graphOps.ts`**, pure functions both the manual builder
   and the reducer call. The 37 existing builder tests pass unchanged on the extraction.

**Watched failing:** the storage guard first matched the bare word and fired on the hook's own
docstring saying it does not use storage — the prose-scan trap again — and was narrowed to use
(`localStorage.` / `[`), then watched failing against a probe file calling
`window.localStorage.setItem` before the probe was removed.

---

## Task 9 — Implement the designed living-builder shell

**Required:** use Task 1's approved design outputs. If implementation reveals a missing state,
return to the design skill and add the state to the artboards before improvising it in React.

**Files:** create the small components under `frontend/src/build/living/`; temporarily expose the
new surface at a development-only/secondary route while the current `/build` remains intact.

- [x] Compose two primary surfaces: living canvas and conversation. Do not recreate the current
  stack of permanent palette, tabs, inspector, problems, and artifact chrome.
- [x] Keep pipeline name, save/validation state, Build/Spawn identity, and Run discoverable
  without competing with the conversation.
- [x] Make module browsing, technical step inspection, validation findings, and YAML contextual
  drawers/overlays as established by the artboards.
- [x] Split block renderers and canvas primitives from orchestration. `LivingBuilder.tsx` should
  wire state and callbacks, not contain every card and SVG path.
- [x] Reuse product tokens and fonts. Add semantic motion/collection tokens only when repeated;
  do not introduce a second color system.
- [x] Add component tests for shell regions, pending/restored/error states, drawer focus return,
  narrow stacking, and no-JavaScript-layout assumptions.
- [x] Render the implementation and Task 1 artboard side by side at every designed width. Record
  mismatches before fixing them; source reading is not visual verification.

**Checkpoint:** a static fake session containing every block state is readable and operable before
the live API is connected. **Met** — `/build/living?fake=1` renders all eight block kinds, all five
notice kinds, collapsed history, a pending turn and a proposal with an alternative, with no API.

### Execution record — the side-by-side

Rendered with `_prev.py` (through a shim pointing `google-chrome-stable` at Playwright's Chromium)
and headless Chromium against Vite, at 1400 and 900, beside `LivingBuild` and `LivingTrouble`.
Mismatches were written down before anything was fixed.

| # | What the pictures showed | Outcome |
|---|---|---|
| 1 | port rows ~4px low; the third clipped into the footer | **fixed** — the artboard's render puts row one on the header rule, whatever its CSS says |
| 2 | the log's spine looked missing at 1400 | **withdrawn** — visible at 900; faint, not absent |
| 3 | a native blue radio circle beside square cards; no *Show me why* | **fixed** — square dot drawn, native radio kept for keyboard and screen reader; *Show me why* sends a real turn |
| 4 | collapsed rows read `tier 2`, not `step 1` / `step 3 · measured`; no line above the card | **fixed** |
| 5 | **Run dimmed** where the artboard shows it live | **kept**: until Task 13 connects Keep/Run, a live-looking Run that does not run is a control leading nowhere |
| 6 | no input source node (`reads ×12 samples`), single-stroke wires | **Task 11's** collection grammar |
| 7 | status says `revision 4` where the artboard says `saved 3s ago` | **kept** — the session exposes no save time, and inventing one is inventing a fact |
| 8 | stacked at 900: conversation, composer, then canvas | **matches** |

**Five things a reader should know before Task 10:**

1. **The server grew four more fields, each the page's minimum.** `placement` — the blueprint's
   own `dag-core` positions, for visible steps only, so nothing moves as the graph grows and the
   plan is not put on the page as empty slots; `history`, every answered proposal, because the
   log is the pipeline's provenance record and the view held only the pending one; `steps_total`,
   a count and not the steps; and `name` plus each turn's `at`, for the header and the ordering.
2. **The canvas does not lay anything out.** Positions come from the blueprint; ports and tiers
   from `POST /pipeline/draw` once per revision, ghost included. A hand-added step takes the drawn
   layout's position — one implementation, which is why `dag-core` exists.
3. **The first full suite caught a colour leak** — two `rgba(…)` literals, the selected halo and
   the option focus ring — through `names no colour outside the token file`. Both are now
   `color-mix` over `--link`.
4. **`+ Add step` opens the existing `Browse` overlay** and saves through the draft's own `PUT`,
   so the server stamps it as the person's. The receipt for that edit is Task 10's.
5. **`/build` is untouched.** The living builder is at `/build/living` until Task 14's walk.

**Watched failing:** removing the drawer's focus restore fails only the drawer test; removing
`onFocus` preview fails only the keyboard-preview test. `zooms toward the cursor` timed out once
in the full run with Vite and Chromium running beside it, and passes 17/17 alone.

---

## Task 10 — Implement conversational cards and bidirectional selection

**Files:** block components, `Conversation.tsx`, composer, and integration tests.

- [x] Render the initial have/do/get summary as an editable typed goal card. Editing structured
  fields does not need another model call; a new prose interpretation does.
- [x] Render one module proposal with what it does, why it is present, its input/output types,
  provenance tier, and real options. The recommended option must be explicit.
- [x] Make option hover and keyboard focus preview the candidate on the canvas without mutating
  the draft. Touch users get an explicit Preview action or the same information expanded.
- [x] Render parameter choices using their declared domains; open-domain values use the existing
  guarded value types and server validation.
- [x] Require a confirmation card for a model-parsed change set that removes/replaces several
  nodes. Show the exact affected steps before Apply.
- [x] A direct canvas/settings edit appends a compact deterministic receipt; do not call the
  model to narrate a fact the client already knows.
- [x] Selecting a chat card focuses/highlights its graph object. Selecting a node reveals its
  relevant decision card or inspector without losing transcript position.
- [x] Follow-up messages appear immediately and show queued/working/refused states. Enter sends;
  Shift+Enter inserts a line break. One pending model turn per session is sufficient for MVP.
- [x] Test keyboard-only operation and screen-reader names for every choice; hover is enrichment,
  never the only route.

**Checkpoint:** complete a fake guided pipeline using only the keyboard and then using a touch-like
pointer with no hover. **Met** — `?fake=guided` is a session that answers itself, and
`Conversation.test.tsx` completes it twice: tabbing to each control and pressing Enter, then with
`[TouchA]` taps only, using **Preview** to see the alternative in the slot on the way.

### A correction to Tasks 7, 8 and 9 — the typecheck that checked nothing

**Every "tsc clean" reported for Tasks 7, 8 and 9 was `npx tsc --noEmit -p .`**, and the root
`tsconfig.json` is `files: []` with project references — so that command type-checks no file and
exits 0. It was found here, when it stayed silent about props this task had just made required.
The real check is `tsc -b` (what `npm run build` runs), and at HEAD it failed: Task 8's and Task 9's
source-scanning guards imported `node:fs` and used `__dirname` inside `.test.tsx` component tests,
which the app config cannot resolve. **The frontend build was broken for two commits.**

Fixed the way the repository already does it: both scans moved into
`src/build/living/sources.test.ts`, added to `tsconfig.app.json`'s exclude list beside
`tokens.test.ts` and `norule.test.ts`. `tsc -b` now reports 0 errors, and it is the only typecheck
this plan's records cite from here on. The Vitest results reported for those tasks were real; only
the typecheck claims were not.

### Execution record

**Six things a reader should know before Task 11:**

1. **Four server additions, each the least the cards needed.** A goal decision may carry the goal
   as edited, held to the declared vocabulary by `authoring_ai.admit_goal` — the same check a
   model's goal gets, with no model call. A step proposal says what it reads (`consumes`). A
   vocabulary read serves the card its choices. And `POST …/edits` records a direct edit: saves the
   draft stamped as the person's, **moves the revision**, writes a receipt the server composes from
   the difference, and re-offers a pending step at the new revision — or the next step, if the
   person just added the offered one by hand. The browser sends a graph and nothing a log could be
   told.
2. **Task 9's `+ Add step` used a plain draft `PUT`** that changed the pipeline and left the log
   silent about it. It now goes through the edit verb, as do settings and change sets.
3. **Two defects found by rendering the guided session**: the goal was drawn twice — read-only in
   its turn and editable beneath — and the typed goal sat under its prose where `LivingGoal` leads
   with it. Both fixed; the first now has a test that was watched failing against it.
4. **One found by the real typecheck**: rebuilding `have` from bare type ids dropped the states of
   inputs the person had not touched. It asked where `states` went; the card now keeps them.
5. **A change set applies removals only.** The block names steps it would add by node id, and a
   node id is not a contract — so additions are shown as *proposed next* and arrive through the
   proposal flow. No server path emits a change set yet.
6. **Recorded against `LivingGoal`, not changed:** the artboard folds the grouping question inside
   the goal card, where the server sends questions as their own blocks; and its resting card shows
   plain rows where this shows edit chips at all times.

**Watched failing against the specific defect:** *Add it* removed from the tab order fails only the
keyboard checkpoint; a Preview that does nothing fails only the touch checkpoint; dropping kept
states fails only the states test; applying a change set on the first press fails only the
two-press test; drawing the offered goal in its turn fails only the drawn-once test; removing the
re-offer fails both edit tests on the server. One mutation first printed `no tests` because the
edit produced invalid syntax, and was redone rather than counted.

---

## Task 11 — Animate the canvas and show collection flow

**Files:** `LivingCanvas.tsx`, `CollectionChannel.tsx`, `motion.ts`, relevant build view DTOs and
tests.

- [ ] Extend `ChannelView` with its materialized `scope` and extend `PortView` with whether the
  input gathers many. Read these from `Pipeline.channels` and `Step.inputs`; do not re-derive
  them from type names in React.
- [ ] Add a safe multiplicity view: known scalar `n_samples` may become `×12 samples`; otherwise
  sample/item scope becomes `×N items`. Never send or display filenames from Mendel.
- [ ] Render one collection channel, not repeated wires. Label N→N as `once per item` and N→1 as
  `collect all` in the expanded/selected view established by the design.
- [ ] Reveal a pending proposal as a clearly provisional ghost. Acceptance settles the node;
  rejection withdraws it; neither state may look committed before the server agrees.
- [ ] Draw committed edges when both endpoints are accepted. Use SVG stroke reveal or an
  equivalent native animation tied to `edge_committed`.
- [ ] Animate parameter commitment and changed YAML sections without moving unrelated objects.
  Preserve object permanence during replacement.
- [ ] Use blueprint target coordinates for staged reveal. Continue to let the client own manual
  offsets after a drag and retain the existing Tidy/server-layout escape hatch.
- [ ] Implement `prefers-reduced-motion`: state changes remain visible through immediate placement
  and highlighting, with no spatial travel.
- [ ] Test event classes/order and reduced-motion behaviour. Do not pretend jsdom pixel assertions
  replace the Task 14 browser checkpoint.

**Checkpoint:** demonstrate 1→1, N→N, and N→1 in the browser. The N→N example must show several
items flowing through one logical linear pipeline, not several branches.

---

## Task 12 — Implement Spawn through the same engine

**Files:** authoring policy service, mode controls, session controller, and end-to-end fake-model
tests.

- [ ] Make the opening mode choice set only the session policy; it must not select a different
  route, graph type, YAML writer, or component tree.
- [ ] In Spawn, automatically accept resolver-settled proposals and model-admitted tier-4 closed
  choices in one server transaction or an idempotent sequence. Keep every proposal/decision in
  history so the completed result is explainable.
- [ ] Stop on a missing candidate, unsupported open value, model refusal, stale registry, or
  illegal graph. Present the same actionable card Build would have presented.
- [ ] On first arrival, replay the accepted proposal event sequence as a short staged reveal.
  Cap total duration and group bursts for a long pipeline. On reload, show the completed graph
  immediately; do not replay a ten-second animation every time. Store only the last-seen event
  sequence number in `sessionStorage`, never transcript content.
- [ ] Keep model provenance on model choices and resolver provenance on deterministic choices.
  “Spawn” is not permission to label the whole graph AI-authored.
- [ ] Test that Build and Spawn over an all-deterministic goal end at equal `DraftGraph` and YAML,
  while their interaction histories differ. Add a tier-4 case proving author provenance differs
  only at the actual model decision.

**Checkpoint:** Build and Spawn converge on one artifact for the RNA-seq fixture; Spawn merely
traverses the proposal policy automatically.

---

## Task 13 — Add canonical YAML preview and reconnect Keep/Run

**Files:** authoring preview service/route, `ArtifactPreview.tsx`, existing Keep/Run integration,
and tests.

- [ ] Materialize current graph + confirmed goal + provenance sidecar in memory and return
  canonical `pipeline_file.dump` text with the draft revision. An empty/illegal partial graph
  returns a declared unavailable/finding state, not fake YAML.
- [ ] Debounce preview refresh after accepted commands and field edits. Do not request it per
  animation frame or keystroke.
- [ ] Diff old/new text in the browser only for presentation. Highlight inserted/changed lines
  or sections, then settle to ordinary artifact text. The server remains the serializer.
- [ ] Distinguish preview from kept artifact clearly. Previewing must not set `DraftRow.kept`,
  write files, stage modules, or make a gate available.
- [ ] Make the living session reuse its existing draft id. Do not let `useKeep` create a second
  draft because its local ref did not know the session already owns one.
- [ ] Keep the existing Run sequence: save/keep, lint, run sheet, submit. Show open human
  decisions before the run sheet and preserve coded refusals.
- [ ] Test preview purity, preview/Keep byte relationship, no duplicate draft, artifact reload,
  and Run against a completed authored draft.

**Checkpoint:** watch modules and parameters appear in YAML during authoring, then Keep and confirm
the artifact view shows the same pipeline without a second implementation having serialized it.

---

## Task 14 — Cut over, walk the real loop, and update documentation

**Files:** `First.tsx`, router/current builder seam, tests, handbook pages, `CLAUDE.md` current
state, and a dated journal entry.

- [ ] Enable the home prompt and Build/Spawn choice. No live-looking control may lead nowhere;
  when no model is configured, state that plainly and preserve a route to manual building.
- [ ] Make `/build?session=<id>` restore the living session and `/build?draft=<id>` open an
  existing draft. Decide through Task 1's design whether an old draft opens directly in the
  living shell or its manual editing state; do not silently open the RNA-seq example instead.
- [ ] Preserve direct module browsing, settings, swapping, validation, artifact, and Run actions
  that still matter. Remove the old `Rail.Assistant` contradiction only when the new path is
  reachable.
- [ ] Keep the old builder mountable during the walk. Delete or archive it in a separate cleanup
  change after requirements have migrated to tests; do not erase `Restored.test.tsx` assertions
  just because their old components moved.
- [ ] Run focused Python tests, frontend Vitest, `make client`, TypeScript, lint, `make check`,
  `make guards`, and `make verify` in that order. Fix the narrowest failure first.
- [ ] Bring up the real stack. Remember that backend source is baked into the image; rebuild the
  API/AI worker after backend changes.
- [ ] With a configured local or hosted model, walk at least:
  1. Build: paired-end RNA-seq → gene counts;
  2. Spawn: the same request;
  3. many FASTA/FASTQ items with an ambiguous grouping answer;
  4. one alternative module selection;
  5. one parameter correction;
  6. one follow-up “why?” question;
  7. reload while a turn is pending;
  8. model refusal/no-model state;
  9. Keep → lint → run sheet on the completed draft.
- [ ] Put the implementation and design artboards side by side at the designed widths. Exercise
  reduced motion, keyboard-only, touch-like input, long content, and a 15-module graph.
- [ ] Confirm through logs/audit rows that only declared AI calls occurred and through the final
  artifact that resolver/model/human provenance is per decision.
- [ ] Update `docs/handbook/your-first-pipeline.md`, `builder.md`, `product-loop.md`, and
  `core-words.md` from observed behaviour. Remove alpha statements that are no longer true; do
  not document proposed controls as shipped before the walk.
- [ ] Write a dated journal/handoff entry naming what was exercised, what failed outside tests,
  what remains deferred, and the real model used. Update `CLAUDE.md`'s current-state pointer in
  the same change.

**Final checkpoint:** a new browser session can describe, confirm, visibly build, revise, keep,
and begin running a living pipeline. Build and Spawn share one draft/proposal engine, collections
read as collections, and the final artifact explains every decision without requiring the chat
transcript.

---

## 4. Explicit non-goals for this MVP

- arbitrary branch creation, branch conditions, loops, scatter syntax, or branch rejoining UI;
- one canvas node per input file or sample;
- sending filenames, sample identifiers, samplesheet rows, or patient data to Mendel/model;
- model-generated YAML, Nextflow, `DraftGraph`, coordinates, React, or API verb sequences;
- token-by-token streaming, WebSockets, collaborative cursors, or simultaneous multi-user chat;
- a general plugin/tool-calling agent framework;
- replacing the registry, resolver, compatibility index, compiler, or canonical artifact writer;
- a second frontend state management library or animation dependency;
- redesigning the Forge or Runs surfaces;
- deleting the manual builder in the same change that first makes the living builder work.

## 5. Completion criteria

This plan is complete only when all are true:

1. The initial prose is stored, queued, and admitted as a typed goal with visible failure states.
2. The researcher confirms a plain-language have/do/get summary before construction.
3. Build reveals modules in stable order with reasons and registry-backed alternatives.
4. Spawn uses the same engine and stops honestly when automatic policy cannot decide.
5. Conversation and canvas edits converge on one revisioned `DraftGraph`.
6. Resolver, model, and human provenance survive together into `pipeline.yml` accurately.
7. Many files/samples render as one collection channel with N→N or N→1 behaviour.
8. Node, wire, setting, and YAML changes animate from domain events and respect reduced motion.
9. Reload restores the session and a pending AI turn without duplication.
10. Preview uses the canonical Python serializer and does not create a kept artifact.
11. Existing drafts and the manual route remain usable through cutover.
12. The browser walk, not only the test suite, has exercised Build, Spawn, refusal, reload,
    collection flow, direct revision, Keep, and Run handoff.

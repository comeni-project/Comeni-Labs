# The consultant build, and the diagram that runs the engine — design

**Issue:** #136 (step 14.7.8, under #126), with #117 (pacing) and #174 (the fact-first card).
**Decided** by the operator on 2026-10-04, in the brainstorm this spec records. It replaces the
*knowingly optimistic* stage ④ of `2026-09-28-the-consultant-design.md` §8, and rules 8–14 of
`docs/design/authoring-protocol.md`, where they differ.

The operator's framing: *this is getting so complex that, if we don't start using good patterns
and having the diagram as the source of truth, we will burn ourselves later.* Build and Spawn
were made for testing the early MVP, and nothing here is designed around them.

## 1. What a person gets

After *that's right* on the goal card, the build opens with its size, counted by the engine:

```
Eleven steps; two need you.
Go through it together, or set it up and stop only where I need you?
```

The walk follows the pipeline's own graph, a step at a time, in the blueprint's order: the steps
the person sees on the canvas are the steps the conversation talks about. (Revised 2026-10-05:
the stages this section first opened with are gone; see §4.)

Each step is a card carrying four things, from declared data only: what it does, why it is
here, what it makes, and what to check. A step whose rule lacks a fact asks for the fact first
(*your read length decides the aligner*). A step no rule settles is a choice. The build ends
with a wrap-up: what you'll get, what you need to run it, and who decided what. Then **Keep**.
At any time the person may ask anything; the AI answers in its own words, marked **AI**.

## 2. The decisions

| Decision | Choice | Why |
|---|---|---|
| Ask anything (rule 13) | **in, as free chat**, given the build's facts as context | it changes nothing in the pipeline; only a confirmed typed action does |
| Rule 12, *only from sources* | **loosened for chat only**; step cards stay sourced | the cards read as the pipeline's own explanation |
| Every message's source | **one minimal mark: AI, engine, or curated** | the project is complex enough |
| Overview stages | ~~the family of what each step makes~~ **no stages** (revised 2026-10-05): the walk follows the blueprint's order and the overview is a count | a grouping the canvas does not show is a second system the person has to infer; every grouping rule tried either reordered the walk past a step's inputs or fragmented across parallel branches |
| Build and Spawn | **retired**: one consultant build, with pacing as a strategy | they were test-era policies welded into `Mode` |
| Step cards' words | **the curated and engine text as is, no AI rewording** (option a) | decide on data: the walk checks readability (#210) |
| The architecture | **the diagram runs the engine**: sessions sit on a node, commands are edges, entering a node runs its handler | updating the flow means updating the diagram |
| Diagrams | **one protocol diagram, with sections**; the sample's inside is a section, not a page | one source of truth |
| Where it lives | **a new pure package, `mendel-authoring`**: the protocol, the interpreter, the commands, the build plan, the strategies, the ports; `mendel-api` keeps only the shell | the wiring has one direction a test can hold; *we are moving in a hairball direction* |

## 3. The architecture: the diagram runs the engine

### 3.1 Two packages, one direction

| `mendel-authoring` (new, **pure**) | `mendel-api` (the shell) |
|---|---|
| the protocol: sections, nodes, edges (the diagram's only source) | the handlers, one stage module per section |
| the interpreter: node + command → edge, or a refusal | the facade: `perform`, `read` |
| the commands, phases, events, outcomes and blocks, as types | the rows, the migrations |
| the build plan; the `Pacing` and `Tier4Answers` strategies | the jobs, the routes, the model calls |
| **ports**: what a handler is, what the interpreter needs from the shell | the binding of its handlers to the protocol's nodes |

- **The arrow points shell → core**, as `mendel-api` → `mendel-resolver` does. `mendel-authoring`
  never imports `mendel-api`, FastAPI, SQLAlchemy, ARQ or a model client. It depends on
  `comeni-core`, and on `mendel-resolver` only if a blueprint type needs it.
- **It joins invariant 1**: the packages that do not reach the network. `test_purity.py` and
  `test_purity_runtime.py` list it.
- **The diagram's generator imports only `mendel-authoring`.**
- **The binding test lives in the shell's tests**, since only the shell knows its handlers. It
  holds the core's acting nodes and the shell's registered handlers to the same set.

### 3.2 How the protocol runs

**The protocol is the program.** `mendel_authoring.protocol` declares one `Protocol`, whose
sections are the stages. The engine interprets it:

- **A session sits on a node.** `pipeline_authoring_session.at` holds the node id; the phase is
  read off the node (each node declares its phase). A migration derives `at` for existing
  sessions from their phase and pending proposal.
- **A command is an edge.** Everything a person or a job does arrives as a typed command:
  `Describe`, `AnswerGap`, `UploadSample`, `ConfirmGoal`, `ReviseGoal`, `ChoosePacing`,
  `Continue`, `AnswerFact`, `Choose`, `Ask`, `Keep`, `Retry`. `perform(session_id, command)` finds
  the outgoing edge from the current node that the command names. With none, it refuses with a
  declared code naming the node and the command.
- **Entering a node runs its handler.** A handler does the node's work and returns the outcome
  that picks the next edge (*nothing missing*, *a gap*, *needs a fact*). Work for the AI worker is
  a handler that queues a job; the job's completion is a command.
- **Nodes are acting or showing.** An acting node has exactly one handler, registered with
  `@handles("<node id>")` in its stage's module. A showing node is an outcome the person sees.
  **The binding test** holds the built acting nodes and the registered handlers to the same set,
  in both directions.
- **A section can be within a request.** The sample's inside (the level check, the inspector,
  the AI reading, the hand-back) does not move the session. Its nodes name the steps a request
  takes and reports, so the card's steps and the picture share ids.

**Stage modules behind one facade, in the shell.** `mendel_api/services/authoring.py` (2,300
lines today) splits by section into `mendel_api/stages/`: `describe`, `gathering`, `samples`,
`goal`, `building`. A thin `mendel_api/services/session.py` holds the dispatcher (which runs the
core's interpreter and the shell's handlers in one transaction) and the read model (`read()`).
The routes call only it.

**Policies are strategies.** `Pacing`: *together* or *only where needed*. `Tier4Answers`: *stop
for the person*, or *a model, flagged* (off; designed). Both are read from the Settings menu; a
Pacing of *ask me every time* asks. They replace `Mode`.

**Pure core, impure shell.** Everything in `mendel-authoring` is pure: no database, clock,
network or model; golden-tested. Only the shell's handlers and facade touch rows, the queue or a
model.

**What is reused.** The blueprint (resolved once, revealed in order, final positions known),
`committed` (placing a step in the draft), the declared alternatives, Keep, and the chat route
(as *ask*). **What goes.** `Mode`, the Build/Spawn toggle, the old step proposal kinds, and every
hand-written `advance(phase, event)` call.

## 4. The build plan (pure)

**Revised 2026-10-05** in the 14.7.8.2 brainstorm (operator). What changed from the 2026-10-04
draft: no stages; `plan_of` takes the blueprint and a narrow port, not a registry and facts;
`Blueprint` moves into `mendel-authoring`; the resolver records which facts a rule lacked.

**Where it sits.** After the goal is confirmed and the blueprint resolved, and before **Keep**:
the build plan is the content of the walk, one card per step. It runs in the build conversation,
not at compile time or run time, and **no model is involved**: every word comes from declared
data or from the resolver's own record.

### 4.1 The pieces

All in `mendel-authoring`, one job each, composed at the top:

| Module | Holds |
|---|---|
| `ports.py` | `Declared`: what the plan reads from the registry (a contract by id, a tool by id, a family by id). The shell adapts its loaded layers to it; the pure side never imports a loader |
| `blueprint.py` | `Blueprint` (moved from `mendel_api/services/blueprint.py`, **without `mode`**, which nothing read) and `committed`, with its helpers |
| `brief.py` | `brief_of(step, declared) → Brief`: the four fields of a step's card |
| `needs.py` | `need_of(step, decisions, declared) → Need`: nothing, a fact, or a choice |
| `wrapup.py` | `wrap_up(blueprint, declared) → WrapUp` |
| `pacing.py` | `Pacing` (*together*, *only where needed*) and `waits(plan, pacing)` |
| `plan.py` | `plan_of(blueprint, declared) → BuildPlan`: one entry per step, in the blueprint's order (its brief and its need), and the wrap-up |

The shell keeps `resolve` (the compiler and the model resolver build a `Blueprint` and hand it
over), and `alternatives` and `proposal` until part 3 deletes them: a choice's candidates come
from the resolver's decision record from then on.

### 4.2 A step's card (`brief_of`)

Every field is used **as written**, never reworded, and carries its source, `engine` or
`curated`, for part 4's marks.

| Field | From | Source | When there is none |
|---|---|---|---|
| does | the tool's declared `description` (`tool.yml`; the tool id is the contract id's first two segments, `nf-core/star`) | curated | left out; nothing is invented |
| why | the step's `why.reason`, and `why.axis_reason` when there is one (the rule and its citation, at tier 3) | engine | always present |
| makes | each output type of the step's contract, in its family's description (types carry no description of their own) | curated | none |
| check | tier 3: each premise's own sentence (`PremiseRecord.prose()`: *read_length is 150, measured by …*); tier 4: the open question; tiers 1 and 2: nothing | engine | left out |

### 4.3 What a step needs (`need_of`)

- **A fact**, when the step's `ProducerDecision` names facts in `unknown`: the rule would decide,
  and its premise is unknown (#174). It carries the facts and the decision's candidates, so
  *choose a tool instead* turns it into a choice (tier 4, *you chose*).
- **A choice**, when any decision on the step, its tool or a setting, is tier 4 and waits on no
  fact. It carries the decision's candidates, each with its tool's description.
- **Nothing**, otherwise.

**`ProducerDecision.unknown`** (`comeni-core`): `list[MeasurementId]`, empty by default and left
out of the dump when empty, so every existing `pipeline.yml` loads and serialises byte for byte
as before. The router writes it where it already holds the list (`unapplied_implementation`'s
second value, through `_ask`); until now it reached the record only as prose (*"…could not apply
(read_length unknown)"*), and a plan cannot parse prose. Empty means *not waiting on a fact* or
*recorded before this field*, as `Why.premise` reads.

### 4.4 The wrap-up (`wrap_up`)

- **What you'll get:** the goal's wanted types, in their families' words.
- **What you need to run it:** the pipeline's input channels, and any setting left to the run.
- **Who decided what:** every step's selection and every setting, counted by tier and source
  (engine, rule, you, AI).

### 4.5 The walk, and pacing

- **The overview** is a count read off the plan: steps, and how many need the person.
- **The walk follows the blueprint's order**, which is the layout's, so every step comes after
  its inputs for any pipeline, branches included.
- **`waits(plan, pacing)`**: *together*, every step; *only where needed*, the steps whose need is
  not nothing. The shell places the rest at once, their briefs on the canvas.
- **A fact answered** is recorded as gathering records one; the shell re-resolves and calls
  `plan_of` again. The plan is recomputed whole and holds no history: which steps the person
  already accepted is the draft's, which the shell already keeps.

### 4.6 Testing

- **Goldens** in `packages/mendel-authoring/tests/`, over small hand-written blueprints (the pure
  package's tests do not run the resolver): the RNA-seq shape without a read length (the aligner
  needs `read_length`, nothing else needs anything), and with one (the aligner is tier 3, its
  check the measured premise); one tier-4 setting, a choice that is not about a tool.
- **Each module:** `brief_of` leaves *does* out for a tool with no `tool.yml`; `need_of`'s three
  cases; `waits` under both pacings; `wrap_up`'s counts.
- **Determinism:** `plan_of` twice, byte-identical JSON.
- **The real thing**, in `mendel-api`'s tests: the RNA-seq goal resolved against the registry with
  no read length, then `plan_of`; the aligner needs `read_length`. **Watched failing** before the
  router writes `unknown`.
- **The router:** `unknown` recorded where the rule cannot apply, empty where it can; `make verify`.
- **The migration:** a stored blueprint holding `"mode"` loads once it has run.
- **`committed`'s tests** move with it, unchanged.

## 5. Stage ④, as the diagram runs it

```
card ──ConfirmGoal──▶ resolve ──▶ overview ──▶ pace? ──(setting, or ChoosePacing)──▶ step
                         └─(can't build)─▶ failed
step ──(waits)──▶ continue? ──Continue──▶ next step
step ──(needs a fact)──▶ fact ──AnswerFact──▶ re-resolve ──▶ step
step ──(needs a choice)─▶ choice ──Choose──▶ next step
step ──(placed)──▶ next step;   (none left) ──▶ wrap-up ──Keep──▶ kept
any time: ask ──Ask──▶ answer   (AI, marked; moves nothing; a suggested action is a card)
```

| Node | Kind | What happens |
|---|---|---|
| resolve | acting, engine | resolve the blueprint, build the plan |
| overview | showing | the counts: steps, and how many need the person (engine) |
| pace? | acting | read the Pacing setting; *ask me every time* shows the question |
| step | acting | the next step's card; placed on the canvas, or held until *continue* |
| fact | showing | the fact-first card; answering re-resolves from this step |
| choice | showing | tier 4: the declared candidates; *you chose* |
| wrap-up | acting, engine | what you'll get, what you need to run it, who decided what |
| kept | acting | Keep: writes `pipeline.yml` |
| ask → answer | acting, AI | free chat over the plan and the current step, marked AI |

## 6. Ask anything

The chat route becomes the *ask* edge, available from every node in the conversation. The AI is
given the plan, the current step's brief and the goal as context, and answers in its own words,
marked **AI**. It may cite a source it was handed. It moves the session nowhere. If it suggests an
action (*replace STAR with HISAT2*), the action comes as a card the person confirms, through the
command that card's node accepts. A recorded transport tests it; no live model in tests.

## 7. One diagram, with sections

| Section | Holds |
|---|---|
| ① You describe it | understanding the want, the family step |
| ② The engine gathers what it needs | gaps, answers, upload |
| ②a Inside: reading a sample | the level check, the inspector, the AI reading, the hand-back (within a request) |
| ③ You check the goal | the card, the read-back |
| ④ Your consultant builds it with you | §5 |
| Any time | ask → answer, retry from a failure |

`tools/generate_protocol_doc.py` imports only `mendel-authoring` and writes one page; `INSPECTING`
and `detail=` go. If the one page
is too dense on screen, the generator draws a section at a time, never a second source.

## 8. When it fails

| Case | What happens |
|---|---|
| a command with no edge from the current node | refused, a declared code naming the node and the command |
| a handler raises | the transaction rolls back; the session stays on its node |
| the blueprint cannot be built | the `failed` node, as today (MI0207, a provider failure) |
| a fact answered with a value the measurement refuses | refused as gathering refuses it (MI0208) |
| a re-resolve after a fact cannot be built | the `failed` node; retry resumes at `resolve` |
| a job's completion for a session that moved on | ignored: the job's command has no edge from where the session now is |
| a session row from before `at` existed | the migration's derived node; a test covers each old phase |

## 9. Testing

- **The binding test**, both directions, in the shell's tests; watched failing, recorded in the
  guard ledger.
- **The interpreter:** every edge of the protocol taken once in a table test; every other
  command refused by name.
- **Purity:** `mendel-authoring` in both purity guards; a test that it imports nothing from the
  shell.
- **Behaviour unchanged after 14.7.8.1:** the whole existing suite, untouched, through the
  dispatcher.
- **Goldens:** the plan and the wrap-up from scenario 1's blueprint, with read length known and
  unknown (§4.6).
- **Pacing:** which steps wait, per strategy.
- **The fact-first card:** answering re-resolves the step to tier 3; choosing keeps tier 4.
- **Ask:** recorded transports; an answer moves the session nowhere.
- **The diagram:** every section drawn; every session's `at` is a built node.
- **The walk:** scenario 1 both ways with `gemma3:12b`; readability of the cards checked (#210).

## 10. Built in five parts

Each part gets its own plan, written when the part before it has landed: part 1 moves the files
the later plans would name.

1. **14.7.8.1 The diagram runs the engine:**
   - the pure package `mendel-authoring`: the protocol, the state machine and the session types
     move into it from `mendel-api`, and it joins the purity guards;
   - one sectioned protocol;
   - `at` and its migration;
   - commands, the dispatcher-interpreter, handlers and the binding test;
   - the stage modules and the facade (§11, plan 1c);
   - **behaviour unchanged.**
2. **14.7.8.2 The build plan:** the pure core of §4, `Blueprint` and `committed` moved into
   `mendel-authoring`, and `ProducerDecision.unknown`.
3. **14.7.8.3 Stage ④:**
   - the handlers of §5;
   - `Mode`, Build/Spawn and the old step proposals removed;
   - the Pacing setting made live.
4. **14.7.8.4 Ask anything:** §6, and the AI / engine / curated marks on every message.
5. **14.7.8.5 The cards and the walk:** artboards first, approved by the operator; the cards;
   the walk.

The `comeni-core` version bump (`ProducerDecision.unknown`), and `mendel-authoring`'s first
release, are judged at release time. No `stage` label is added to `Family` (§4).

## 11. Part 1's second half: how the shell is put together (14.7.8.1c)

**Decided** by the operator on 2026-10-04, in a brainstorm held after 1b landed. Part 1 is two
plans: 1b made the diagram move every session; 1c moves the code behind it into the stage
modules, and makes one person's action one transaction. Behaviour is unchanged.

### 11.1 What moves, and what is fenced off for part 3

| Code | Goes to |
|---|---|
| ① describing: opening a session, the model's reading stored, words said | `stages/describe.py` |
| ② gathering: the needs listed, the next question offered, an answer recorded, phrasing | `stages/gathering.py` |
| ②a a sample: the upload, the reading, the hand-back | `stages/samples.py` |
| ③ the goal card: confirm, *not quite*, a correction in words, the read-back | `stages/goal.py` (new) |
| ④ what part 3 **keeps**: resolve the blueprint, offer a step, commit a step into the draft, re-resolve when the registry moved (MI0206), the *can't build* note (MI0207) | `stages/building.py`, as small functions part 3 calls |
| ④ what part 3 **deletes**: `Mode`, `spawn_forward`, `SpawnStop`, the Spawn branches of the routes and the build job | `services/spawn.py`, as is, marked for deletion |
| the read model (`read`, `calls`, `pending_id`) and the facade | `services/session.py` |
| the shared row helpers (`_now`, `_id`, `_swap`, the engine's turn) | `stages/_rows.py` |

`settle_step` stays only as a thin wrapper over the kept functions, until part 3 replaces it.
`services/authoring.py` is deleted.

### 11.2 One action, one transaction

- **Nothing that calls a model runs inside a transaction.** A model is called only in a job on
  the AI worker; the job's result is its own command with its own transaction. Resolving without
  a model is computation and runs inside the action's transaction, so a failure between
  resolving and storing leaves nothing half-written. Spawn's build job, which resolves with a
  model, stays as it is in `spawn.py` until part 3 deletes it.
- **An exception rolls back; a refusal commits.** A handler that raises leaves the session on its
  node with nothing written (§8). A handler that *returns* a refusal (a stale step re-offered,
  MI0206; a duplicate marked, MI0203; the resolver failing onto `failed`) commits what it
  recorded, and the refusal then reaches the person.
- **Jobs are queued after the commit.** A handler adds the jobs it wants to its context; the
  facade queues them once the transaction has committed, so a job never reads data that is not
  yet saved, nor runs for an action that rolled back. The nodes whose only work was to queue a
  job (`family`, `ask`, `suggest`, `readback`) become acting nodes that queue it and wait, and
  the binding test grows by them; `upload` queues the sample's reading. Spawn's `resolve`, which
  queues its build job, stays as it is until part 3.
- **The transaction is ambient.** The facade opens it; every `session_scope()` beneath joins it
  rather than committing, and only the outermost commits. Moved code keeps its shape, so the move
  can be read as a move.

### 11.3 What calls what

- **The routes and the jobs call only the facade:** `session.perform(session_id, command)` and
  `session.read(session_id)`. `perform` is async: it runs the transaction off the event loop,
  then queues.
- **The tests move to the same names**, by a script, in one commit that changes call sites and
  imports only, no assertion. The tests that monkeypatch a moved helper are fixed in that commit.
  `authoring.move` becomes a test helper.
- **Commands are typed:** a frozen dataclass per command in `mendel_authoring.commands`, holding
  exactly its fields, whose name the interpreter reads. 1c types the commands the shell performs
  today; parts 3 and 4 add theirs as types from the start. The shell still checks what only the
  rows know: an option never offered (MI0205), a value that does not fit (MI0208).

## 12. Forks: the diagram switches on a setting (14.7.8.3a)

**Decided** by the operator on 2026-10-06, in the 14.7.8.3 brainstorm, and built **before stage
④** because stage ④ is its first user. Part 3 is split: **3a** forks (this section), **3b** stage
④ (§5, the Dev setting of §12.4, `Mode` removed, Pacing live). Later part numbers are unchanged.

### 12.1 What a fork is

A **fork** is a node that switches on a **subject**; its outgoing edges are the **cases**. The
pure interpreter reads the subject's current case from a **snapshot** the shell passes in, and
takes that edge. No handler runs, and no `if` in a handler decides the path: the branch is in the
diagram, drawn as a diamond labelled with its subject (*Pacing?*, *Dev mode?*), each edge
labelled with its case.

```python
fork("pace", on=SettingSubject.of(PACING))
_e("pace", "step", case="together", built=True)
_e("pace", "step_quiet", case="stop_where_needed", built=True)
_e("pace", "ask_pacing", case="ask", built=True)
```

### 12.2 The subject is pluggable

A subject is a small frozen model in `mendel_authoring/forks.py`, subclassing `Subject`:

- `options() -> frozenset[str] | None`: the closed set of cases, or `None` for an open domain;
- `value(snapshot) -> str`: the current case, read from the snapshot;
- `title`: what the diamond says.

**Today: `SettingSubject`**, made from a setting's own declaration (`SettingSubject.of(setting)`),
so its cases cannot drift from the menu: a choice's option values; a toggle's `on` / `off`; any
other kind is open. **Later**, without touching the interpreter: a parameter, a fact, a property
of the plan. Adding one is one class.

**The snapshot** (`Snapshot`) is plain data: `settings: dict[str, JsonValue]` today, a field per
kind of subject as they arrive. The shell builds it; the interpreter never reads a store.

### 12.3 Checked when the protocol loads

`Protocol` already refuses to exist when inconsistent; forks add:

- a fork does not act (the interpreter decides it) and does not wait;
- every edge out of a fork, **built or planned**, names a `case`, and only edges out of a fork do;
  coverage counts planned edges too, so a designed option is drawn dashed and still covers its
  case (revised 2026-10-06, final review); the interpreter takes only built edges, so a run
  reaching a planned case is refused (MI0216);
- a subject with **closed** options has **exactly one** edge per option, and no other case;
- a subject with an **open** domain has a `DEFAULT` edge (`case="*"`);
- no case twice.

So a new Pacing option without its branch, or a fork on an open value with no fallback, fails
when the protocol is imported, which is every test run, not a session.

**At run time**, a case with no edge (a snapshot holding a value the subject does not list, and no
`DEFAULT`) is refused with MI0216, naming the fork and the value.

### 12.4 The Dev setting (built in 3b)

A toggle, off by default. On: the walk shows **registry gaps** as marked cards naming the file to
fix (a tier-4 setting with no declared domain, a tool with no `tool.yml`, a contract marked
`unverified`). Off: the engine routes around them (a value with no domain is left to the run, #252).
It is stage ④'s second fork, after Pacing.

### 12.5 Testing (3a)

- Over a small test protocol, not the real one (whose first fork arrives in 3b): each case taken
  from its snapshot; `DEFAULT` taken for an unlisted value; a missing case refused (MI0216).
- Each load-time refusal of §12.3, by a protocol that breaks it.
- `SettingSubject.of` over a choice, a toggle and a text setting.
- The drawing: a fork is a diamond with its subject's title, its edges labelled with their cases.

## 13. Stage ④ built (14.7.8.3b)

**Decided** by the operator on 2026-10-06, in the 14.7.8.3b brainstorm. It builds §5 on the forks
of §12 and the build plan of §4. Where it differs from §5, this section wins. **§14 replaces its
walk** (the fact, the cursor, the draft built step by step).

### 13.1 The decisions

| Decision | Choice | Why |
|---|---|---|
| What the browser shows before part 5 | **the existing block kinds**: a step is a `StepProposal` carrying its brief and need; a fact is a `Question` on the gap card (so a sample can answer it); the pacing question is a `Question`; the overview a `Narrative`; the wrap-up a `Receipt` | the loop keeps working with the least throwaway work; part 5 redesigns the cards |
| Spawn's model answer at tier 4 | **tier 4 always stops in 3b**; `ModelResolver` kept, unwired, for a later Tier-4 answers fork | nothing that works is lost but a test-era toggle |
| Sessions from before 3b | **dropped**: no migration of old nodes, no shims for old proposal kinds or stored shapes | not even the MVP yet (operator); the journal says to clear the dev database's authoring sessions once |
| Keep | **unchanged**: the draft's Keep (`POST /drafts/{id}/keep`); `wrap` rests | one fewer moving part |
| The Dev setting | `dev.mode`, a toggle, off, in a new **Developer** section | §12.4 |

### 13.2 The flow

```
card ─that's right→ resolve ──stored──→ overview ──→ ◇ Pacing?
                       └─can't build→ failed           ├ together → together ───────────┐
                                                       ├ stop_where_needed → quiet ─────┤ records the pacing
                                                       └ ask → pace_q ─ChoosePacing→ chosen
                                                                                        ↓
     step ─placed→ step            a step that does not wait: placed with its brief, straight on
     step ─held→ continue? ─Continue→ step
     step ─needs a fact→ fact ─AnswerFact→ reresolve → step
     step ─needs a choice→ choice ─Choose→ step
     step ─a registry gap→ ◇ Dev mode?  ├ on → gap ─Continue→ step
                                         └ off → route_around → step
     step ─none left→ wrap              (Keep is the draft's, as today)
     wrap ─that's right (goal changed)→ resolve
```

| Node | Kind | What happens |
|---|---|---|
| resolve | acting, waits | resolve the blueprint (the shell), store it; outcomes as today |
| overview | acting | posts a `Narrative`: *Eleven steps; two need you.* |
| ◇ Pacing? | fork | on `building.pacing` |
| together, quiet | acting | record the pacing on the session |
| pace_q | showing, waits | the pacing `Question`; `ChoosePacing` carries the answer |
| chosen | acting | records the chosen pacing |
| step | acting | the next step by `cursor` in the blueprint's order: gap first (if not seen), then need, then `waits` |
| continue? | showing, waits | the step's `StepProposal`; `Continue` places it |
| fact | showing, waits | the gap card (`Question`, upload offered); answered as gathering records a fact |
| reresolve | acting | re-resolve, rebuild the plan, keep the cursor |
| choice | showing, waits | the `StepProposal` with the resolver's candidates; `Choose` places the choice |
| ◇ Dev mode? | fork | on `dev.mode` |
| gap | showing, waits | a marked card naming what is missing and the file to fix; `Continue` |
| route_around | acting | records the gap as seen |
| wrap | acting, waits | posts the wrap-up as a `Receipt` |

**Corrected while building (3b run 2):** the need is decided before the gaps (a step that needs a
fact stops on it whatever Dev mode says), and `route_around` hides the gap, not the step — it
applies the pacing (`held` under *together*, `placed` otherwise), so the protocol draws both arrows.

**Removed:** `offer`, `step_settled`, `step_rule`, `step_choice`, `done`; `Mode` and the Build/Spawn
toggle (API and browser); `services/spawn.py`; `alternatives` and `proposal` in
`services/blueprint.py`; the old step proposal flow.

### 13.3 Stored and computed

- **Session row** (one migration): `mode` dropped; `pacing` added (nullable string); `cursor` is
  the walk's position (index of the next step in `blueprint.order`); `gaps_seen` added (a list of
  step ids).
- **`gaps_of(step, pipeline, declared)`** (pure, `mendel-authoring`), a `gaps` field on each
  planned step; each gap names what is missing and the file to fix:
  - a tier-4 setting with no declared domain (its decision's candidates are `[null]`) →
    `registry/tools/<module key>/contract.yml`;
  - a tool with no description → `registry/tools/<tool id>/tool.yml`;
  - a contract in the pipeline's `registry.unverified` → its `contract.yml`.
- **`need_of` no longer counts a no-domain setting as a choice**: it is a gap, and the wrap-up
  already lists it as left to the run (#252).
- **The snapshot**: the dispatcher (`services/session.py`) resolves, through
  `comeni_core.settings.resolve`, each key `PROTOCOL.fork_keys()` names, so a `.env` lock, a
  designed option and a stale stored value are all handled, and passes it to `interpret.run`.
- **The Dev setting**'s help: *Show registry gaps in the build — missing descriptions, settings
  with no list of values, unverified contracts — as cards naming the file to fix.* **Pacing** stops
  being greyed as designed.

### 13.4 Testing

- The protocol loads with its two forks covering every option; the diagram regenerates.
- Pure: `gaps_of` per kind; `need_of` leaves a no-domain setting out; `fork_keys()`.
- The interpreter over the real protocol with a fake `enter`: each Pacing case reaches `step`; Dev
  on rests on `gap`, off passes `route_around`; a fact runs through `reresolve` to `step`; none
  left reaches `wrap`.
- The shell (Postgres): scenario 1 without a read length rests on the fact, and answering it
  places the aligner at tier 3; with one, *stop where needed* places everything and reaches
  `wrap`; *together* rests at every step.
- The snapshot: a `.env`-locked Pacing wins over a stored one; a designed option falls back to the
  default.
- The binding test over the new acting nodes.
- Removal: `Mode`, `spawn.py`, `alternatives` and `proposal` gone; no Build/Spawn in the browser;
  `make client`, `npx vitest run`, `npx tsc -b`.
- The walk: scenario 1 both ways in the browser, looked at.

### 13.5 Not in 3b

Ask anything (part 4); the designed cards and the walk with a model (part 5); the Tier-4 answers
fork; STAR's `seq_platform` domain (a registry change, landed right after 3b).

### 13.6 Amended while planning (2026-10-06), against the code

Each found reading the code the plan is written against; each makes the flow smaller.

- **The step handler places every step that does not wait, in one entry**, and leaves only on a
  stop (`held`, `needs_fact`, `needs_choice`, `a_gap`) or `none_left`. A `placed → step` loop
  would pass the interpreter once per step and be refused after 64 nodes (its cycle limit) on a
  large pipeline.
- **No `gap` node and no `gaps_seen`.** Dev on: `show_gap` offers the step's card with its gaps
  marked and rests on `continue?`, so *Continue* places it and the cursor moves on. Dev off:
  `route_around` places the step quietly. Either way the cursor passing the step is what makes a
  gap raised once.
- **The pacing question**: the fork's `ask` case goes to `ask_pacing` (acting: posts the
  `Question`), which rests on `pace_q`; `ChoosePacing` records the answer and goes on to `step`.
  No `chosen` node.
- **A fact is answered by typing or choosing, not by a sample, in 3b.** A sample upload is a
  section entered from gathering's question and leaving to gathering's nodes; reusing it from
  stage ④ is its own design (part 5). The fact card is the gap card with *upload* left out; it is
  answered through `AnswerGap` (arrow `answer_gap` out of `fact`). A fact answered *not sure* is
  recorded open, and the step then asks as a choice, so the walk never asks for the same fact
  twice.
- **`continue?` and `choice` are answered by the existing `SettleStep`**, whose arrow is
  `continue` or `choose` by where the session rests; rejecting a step still skips it.
- **A choice offers tools**: its candidates are the producer decision's. A tier-4 setting that
  has a declared domain is shown on the card and kept at its value; a value picker for settings is
  part 5.
- **The session row**: `mode` dropped, `pacing` added; `cursor` is the walk's position. No
  `gaps_seen`.

## 14. The blueprint decides, the walk reviews (14.7.8.3c)

**Decided** by the operator on 2026-10-06, after the review of 3b's second run (issues 253–259).
Where it differs from §13, this section wins; §13's forks, pacing, gaps, overview and wrap-up stay.

### 14.1 Why

3b's walk **built** the draft: each step was appended as the walk passed it, and a fact answered
mid-walk re-resolved the blueprint under a draft already half-built from the old one. Answering
*read length 50* switched STAR to HISAT2 with STAR's index left orphaned and HISAT2's never
offered (253); choosing HISAT2 on STAR's card kept STAR's index wired in (257); the kept draft
lost the fact (254); the wrap-up credited the resolver for the person's choice (256). Each is one
cause: three copies of "what has been decided" — the session's facts, its cursor, the draft —
drifting apart.

### 14.2 The decisions

| Decision | Choice | Why |
|---|---|---|
| Where a decision lives | **in the goal, and only there.** A person's answer is an `Amendment` applied to the goal; the blueprint is `resolve(goal)`; the draft is a projection of the blueprint | same goal in → same pipeline out, with every decision included; nothing drifts because nothing is held twice |
| What a person can change on a step | **its tool, for any compatible tool** — the router's own candidates at that step's site — whether or not a rule covers it; and, where a rule lacks a fact, the fact | the engine is a guide, not a gate (operator); the candidate list keeps it inside what can be built |
| How a change is shown | **as a whole pipeline**: each alternative is `resolve(goal + amendment)`, shown as its difference from the current blueprint | nobody computes by hand what a swap drags with it |
| A person's tool against the engine's | **tier 4, source person**, with the engine's own reason kept beside it: *the rule picks STAR for reads ≥ 100 bp; you chose HISAT2*. A pin naming the tool the engine would pick anyway changes nothing | the step is no longer proven from the data, and the reader sees who decided (invariant 6) |
| Structural hand edits (add, remove, rewire) | **after the walk**, on the kept draft, as today; refused during the walk with a sentence saying so | a projection has nowhere to keep them; the walk stays simple |
| Settings (a value for a tier-4 setting) | **part 5**, with the value picker; the amendment type is designed for it here and not built | no setting has a declared domain to pick from until the registry fix |
| The AI as guide | **part 4**, proposing only these amendments, by id, previewed like any other | a model touches the pipeline only through the typed questions |

### 14.3 The pieces

**The goal gains producer pins** (`comeni-core`, pure). `Constraints.producers: list[ProducerPin]`,
`ProducerPin(type_id, states, contract)`: at the router's site producing `type_id` with `states`,
take `contract` if it is a candidate there. **Honoured in `router._choose` before rules.** If it is
the tool the router would have chosen, the step is recorded exactly as without the pin; otherwise
it is tier 4 with source `HUMAN` and a reason naming the engine's pick and its reason. A pin whose
contract cannot reach its inputs raises `UnroutablePinError`, as a rule pin does. A pin that
matches no site is inert and is listed in the wrap-up as *no longer applies*. **Serialised only
when non-empty**, so an existing goal emits byte-identical output (invariant 10).

**Amendments** (`mendel-authoring`, pure), each a frozen value with `apply(goal) -> Goal`:

- `ChooseTool(type_id, states, contract)` adds or replaces the pin at that site;
- `SetFact(measurement, value)` adds a measured entry to `goal.profile`, built through
  `profile_of` (the construction guard; invariant 15);
- `SetSetting(...)`: the type is named; it is part 5's.

A person's answer, a swap on a card and (part 4) a model's proposal are all amendments; the shell
records each as a turn (who, what, the difference it made) and stores only the amended goal.

**The site** of each step: the blueprint carries, per step, the `type_id` and `states` it was
chosen to produce and the router's candidate list there (after cycles and absent roles are
removed). Carried on the `Blueprint` (`mendel-authoring`), not on `pipeline.yml`: the artifact is
unchanged.

**Alternatives** (`alternatives_of(blueprint, node, resolve) -> list[Alternative]`, pure, with
`resolve` a port): for each other candidate at the step's site, the amendment, the blueprint it
gives, and its difference — steps added, removed and kept, by id — or the reason it cannot be
built (`UnroutablePinError`'s sentence), shown and not offered. Computed when the step's card is
offered, so the card's options are fixed when the person reads it.

**The draft is a projection** (`drafted(blueprint, reviewed) -> (DraftGraph, DraftProvenance)`,
pure): the blueprint's steps the person has reviewed, with their edges, and each node's
provenance read from its step's source. It replaces appending through `committed`; it is
recomputed after every amendment and every review. The goal and the graph's profile are written
to the draft with it (254).

**The walk's place** is a set of reviewed step ids, not a cursor: the next step is the first in
the blueprint's order not yet reviewed. After a swap, the chosen tool's step is reviewed (the
person just decided it) and any step the swap added before it — HISAT2's index — comes next,
marked *added by your choice*. A reviewed step the new blueprint no longer has simply leaves the
set.

### 14.4 The flow

```
card ─that's right→ resolve ──stored──→ overview → ◇ Pacing? (as §13) → ◇ Dev mode?
                                                             ├ on → show_gaps ──┐  records whether
                                                             └ off → hide_gaps ─┤  gaps stop the walk
                                                                                ↓
     step ─held→ card ─Continue→ step
                      └─Amend→ amend ─→ step         (a swap, or a fact)
     step ─needs you→ choice ─Continue (keep, flagged)→ step
                             └─Amend→ amend ─→ step
     amend ─can't build→ failed
     step ─none left→ wrap
```

- **The Dev fork moves before the walk**, beside Pacing, and is recorded on the session like the
  pacing. The `step` handler then places every step that does not stop — routed-around gaps
  included — in one entry, so a pipeline of any size passes the interpreter in a fixed number of
  nodes (258). `route_around` and `show_gap` go; a gap shown under Dev on is a marked card at
  `held`.
- **`step` stops** on: a tier-4 step (`choice`), a gap under Dev on (`held`, marked), or every
  step under *together* (`held`). Under *stop where needed* nothing else stops.
- **The card** (`held` or `choice`) offers *Continue* and its alternatives, each with its
  difference; a step whose rule lacked a fact also offers *tell me* for that fact. *Continue* on a
  tier-4 step keeps the engine's pick, flagged.
- **`amend`** (acting) applies the amendment, re-resolves, stores the blueprint, the goal and the
  projected draft, and goes to `step`. A blueprint that cannot be built goes to `failed`, as
  `resolve` does (259).
- **Removed:** `fact`, `reresolve`, `show_gap`, `route_around`; `AnswerGap` in stage ④;
  `with_facts`; the session's `cursor`; `committed`; rejecting a step (the projection has no
  hole to leave; removing a step is a structural edit, after the walk).

### 14.5 Commands

- **`SettleStep(proposal, takes: continue)`** is *Continue* only: keep this step as it is. It loses
  its option and its *choose* arrow; rejecting is gone (§14.4).
- **`Amend(proposal, option, value=None)`** picks one of the amendments the card offered, **by
  id**: an alternative (`alt_1` → its `ChooseTool`) or a fact (`fact:read_length`, with the
  `value`, checked by the measurement registry). Nothing outside the card's offered set can be
  sent, which is the door part 4's model will use too.
- Both, and `ChoosePacing`, refuse a proposal that is not pending (MI0203) or is of the wrong kind
  (259).
- `RecordEdit` during the walk is refused with a coded sentence: *editing opens when the walk is
  done* (255); after `wrap`, unchanged.

### 14.6 Stored

- **Session row:** `reviewed` (list of step ids) replaces `cursor`; `show_gaps` (bool, nullable)
  beside `pacing`; `facts` stays gathering's and is not read in stage ④. One migration; old
  sessions are dropped, as in 3b.
- **The goal row** is the amended goal; the draft's `goal` and graph `profile` follow it.

### 14.7 The wrap-up

Read from the final blueprint, which now carries the person's choices as `HUMAN` (256), plus any
inert pin. Unchanged otherwise.

### 14.8 Testing

- Pure: `ProducerPin` honoured before a rule; a pin equal to the engine's pick changes nothing;
  a pin against it is tier 4 `HUMAN` with both reasons; an empty `producers` serialises to the
  same bytes as before (a golden). `ChooseTool` and `SetFact` `apply`. `alternatives_of` on
  STAR: HISAT2's difference adds `hisat2_build`, removes `star_genomegenerate`.
  `drafted` from a reviewed set; a step the blueprint lost leaves it.
- The interpreter: each Pacing × Dev case reaches `step`; a card's `Amend` passes `amend` to
  `step`; a large fake plan of 100 gap steps under *stop where needed*, Dev off, reaches `wrap`
  within the node limit (258).
- The shell (Postgres): scenario 1 without a read length stops at STAR as a choice; *tell me 50*
  re-resolves to HISAT2 **with its index and without STAR's** (253); swapping STAR for HISAT2 on
  the card does the same (257); the kept draft's goal has the fact (254); the wrap-up credits the
  person (256); a `RecordEdit` mid-walk is refused (255); a replayed pacing proposal is refused
  (259).
- The browser: a card shows its alternatives with their differences; the canvas shows the steps a
  swap added, marked. `make client`, vitest, `tsc -b`.
- **Walk it** in the browser: scenario 1 both ways, a swap, each Pacing, Dev on.

### 14.9 Not here

Settings' values (part 5, with the picker); the AI as guide (part 4); structural edits during the
walk; pins keyed other than by site.

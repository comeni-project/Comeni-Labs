# The consultant build, and the diagram that runs the engine — design

**Issue:** #136 (step 14.7.8, under #126), with #117 (pacing) and #174 (the fact-first card).
**Decided** by the operator on 2026-10-04, in the brainstorm this spec records. It replaces the
*knowingly optimistic* stage ④ of `2026-09-28-the-consultant-design.md` §8, and rules 8–14 of
`docs/design/authoring-protocol.md`, where they differ.

The operator's framing: *this is getting so complex that, if we don't start using good patterns
and having the diagram as the source of truth, we will burn ourselves later.* Build and Spawn
were made for testing the early MVP, and nothing here is designed around them.

## 1. What a person gets

After *that's right* on the goal card, the build opens with its shape, in stages a researcher
recognises, counted by the engine:

```
Five stages, eleven steps; two need you.
  the reads, cleaned · the reference, prepared · reads placed on the genome ·
  reads per gene · the quality report
Go through it together, or set it up and stop only where I need you?
```

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
| Overview stages | **the family of what each step makes**, with an optional `stage` label on a family | nothing new to declare per tool; scales to thousands of tools |
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

`plan_of(blueprint, registry, facts) → BuildPlan`. Same input, same plan.

- **Stages:** steps grouped, in reveal order, by the family of what they make. The title is the
  family's optional `stage` label, else its description. Marked **curated**.
- **A step's brief:**

  | Field | From | Mark |
  |---|---|---|
  | does | the tool's declared description | curated |
  | why | the rule and its citation (tier 3), the convention (tier 2), *the only tool that makes this* (tier 1), *no rule could decide* (tier 4) | engine |
  | makes | its output types, in their families' words | curated |
  | check | tier 3: the premise and its source (*read length 150 · measured*); tier 4: the open choice; tiers 1–2: nothing | engine |

- **What a step needs:** nothing; **a fact**, when a rule would decide it and its premise is
  unknown (#174, decided 2026-09-28); or **a choice** (tier 4), from the resolver's declared
  candidates with their descriptions.
- **The overview:** stages, steps, and how many need the person, counted from the plan.
- **Pacing:** `waits(plan, pacing)`. *Together*: every step. *Only where needed*: the steps that
  need a fact or a choice; the rest are placed at once, their briefs on the canvas.
- **A fact answered** is recorded as gathering records one, the blueprint is re-resolved, and
  the plan is rebuilt from that step on. Steps are revealed in order, so only steps after the
  stop can change, and what the person accepted stays. *Choose a tool instead* turns a fact
  into a choice: tier 4, *you chose*.
- **The wrap-up:**
  - what you'll get (the wanted outputs);
  - what you need to run it (the inputs and settings left to the run);
  - who decided what (counts by tier and source: engine, rule, you, AI).

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
| overview | showing | the stages and counts, curated and engine |
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
- **Goldens:** the plan, the overview and the wrap-up from scenario 1's blueprint, with read
  length known and unknown.
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
2. **14.7.8.2 The build plan:** the pure core of §4.
3. **14.7.8.3 Stage ④:**
   - the handlers of §5;
   - `Mode`, Build/Spawn and the old step proposals removed;
   - the Pacing setting made live.
4. **14.7.8.4 Ask anything:** §6, and the AI / engine / curated marks on every message.
5. **14.7.8.5 The cards and the walk:** artboards first, approved by the operator; the cards;
   the walk.

The `comeni-core` version bump (a family's optional `stage` label), and `mendel-authoring`'s first
release, are judged at release time.

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

# The builder agent: a chat that builds, teaches and guides

Part of #463. Replaces the design questions of #497 (the chat) and #493 (the first screen), and
settles how the AI and the engine share the work. Decided with the operator on 2026-11-14, after
the QUAST and RNA-seq walks (#494, #496).

## Why

The walks showed a builder that behaves like a form. The engine drives a fixed script —
understand the goal, confirm a goal card, answer a gap question at a time, then accept one
proposed step at a time — and the model only fills fields inside it. The chat stacks engine
cards, repeats them, explains nothing in its own words ("Why it's here: uncontested — nothing
else in this stack fills bam_sorting"), and shows "Working on it" while it thinks.

The operator wants it to feel like talking to an agent: one that shows what it is doing, builds
the pipeline itself, explains why, answers questions about anything, and teaches and guides. In
their words: the engine was given too much responsibility; let the AI breathe and become a
fully fledged agent.

## Goals

- The builder's AI is an **agent in a loop**: it reads, thinks, calls tools, and talks to the
  person in ordinary chat while it works.
- It **builds the pipeline itself** and then talks the person through what it built. The person
  can ask about anything — a step, a value, a rule, their data — and get a real answer.
- It **acts and tells**: it adds steps, chooses tools, sets values and answers the engine's open
  questions itself; each act is recorded as the AI's and marked for the person to review.
- While it works, the chat shows a **live trail** of what it is doing, the way agents show their
  tool calls.
- The engine's operations are **one typed tool layer**, used in-process by the builder agent and
  exposed through an **MCP server** in this same build, so other agents (Claude Code, any MCP
  client) can build Comeni pipelines with the same tools.
- **Registry rules are advice.** When a rule fires, its result, reason and citation reach the
  agent as context. The agent may follow it or override it, recording why.

## Non-goals

- The context menu and step cards, the pipeline file page and the canvas polish. They were
  designed in the same conversation and are **plan 2**, after this one (see the last section);
  this spec only keeps the canvas as the live picture.
- New protection levels. Level 0 is what is built; stricter levels are added later.
- Running pipelines. Wiener is unchanged.

## Anti-goals

- **The agent writes no pipeline code.** It chooses and connects tools through the engine; the
  compiler wires the modules and emits the Nextflow. A design where the model writes or patches
  Nextflow has failed, however well it works.
- **Nothing the AI did is hidden.** If a person cannot tell what the AI chose and why, from the
  chat or the saved pipeline, the design has failed.
- **No scripted walk in disguise.** The step-by-step walk goes entirely. Re-creating it as a
  fixed sequence of agent prompts would miss the point.

## What the operator decided

- Approach 2 below: one tool layer over the decision record, replacing the scripted flow.
- The step-by-step walk goes entirely. The agent builds, then talks the person through it.
- Act and tell: the agent acts; each act is recorded as the AI's and flagged for review.
- Questions to the person are a tool.
- Every tool call is validated as a person's click is.
- No code: modules wire themselves through the compiler.
- Registry rules are advice: they reach the agent as context when they fire; it may override.
- MCP is part of this build.
- Data exposure follows the protection level. At level 0 the agent's tools may return what the
  job needs, sample names included. Stricter levels filter later.
- Earlier design rules may go where they stand in the way. Replay determinism is no longer a
  design goal of its own (recorded decisions still reproduce the pipeline, because they are the
  input the engine builds from).
- The canvas stays the live picture of the pipeline.
- A contract may carry a one-line `does:`; it is context for the agent, never shown in the chat
  as written.

## Approaches considered

1. **The agent drives today's session commands.** Tools wrap the existing commands (answer a
   gap, decide a proposal, change a decision) and the phase machine stays, minus the walk. Least
   deletion, but it fights the architecture: the machine assumes one pending card at a time and
   fixed phases, so a free agent keeps meeting "not in this phase" and "a proposal is pending".
2. **One tool layer over the decision record, replacing the scripted flow. Chosen.** Tools read
   and change the draft's decision record through the one writer that exists
   (`services.changes.apply` with a `DecisionChange`), resolve with the engine, read views and
   compile. The conversation is an agent thread. The phase machine, proposals, gap and step
   walks and the goal card retire. MCP is a thin adapter over the same tools.
3. **Like 2, with every agent going through MCP, the builder included.** One path guarantees
   parity, at the cost of a network hop and authentication on every internal call and debugging
   across two processes. Approach 2 gets parity by sharing one tool layer.

## The design

### The tool layer

A new module in `mendel-api` (the builder's tool layer) defines each engine operation once: a
name, a typed input, a typed output, and a function. The builder agent calls these functions
directly; the MCP server registers the same definitions. Every write goes through
`services.changes.apply`, so a tool's change is checked and refused exactly as a click is
(`MI0204` for an undeclared type, tool or setting, `MI0208` for a value a measurement refuses).

The tools, grouped:

- **Read:** the goal and decision record; the pipeline as built (steps, wiring, settings, open
  values); one step in full (its contract, `does:`, tool description, every setting with its
  reason, tier and citation, the rules that fired for it); the registry (types, tools that
  make or read a type, a tool's contract); the rules for a role, with conditions and citations;
  the person's facts and samples.
- **Change:** say what is wanted and with which states; say what the person has; set a fact;
  choose a tool for a site (`pin_producer`), exclude one, switch a role off; switch an optional
  input; set a setting; keep a step whole; retract any of these. Each is a `DecisionChange`.
- **Build:** resolve the decision record into a pipeline and return what changed, what is still
  open, and what the rules decided; compile to Nextflow and return the files or the coded
  refusal.
- **Ask the person:** a question, with an optional typed answer shape (a closed list of
  options, a number, yes/no, a file to upload). The tool call ends the agent's turn; the
  person's answer, typed or clicked, starts the next.

Tool results are typed views built for a model to read: names in words alongside ids, reasons
in sentences, citations attached. They are not database rows.

### Rules as advice

When the engine resolves, every rule that fired is reported with its result, its reason, its
citation and the facts it read. The agent sees this in the build tool's result. It may leave it,
or override it with a change tool — choosing another tool for the site, or setting the value —
giving a reason. The resolver already ranks a recorded choice above a rule (a pinned tool wraps
the rule's result, a set value replaces it), so no new resolution mechanism is needed.

What is needed is attribution. A pin or a setting in the goal does not say who made it. The
decision record does (`actor_kind`), so the agent's decisions carry `actor_kind = model`, the
reason it gave, and the turn that made them, and the saved pipeline's reason for that value says
"the AI chose this over the rule because …", with the rule's own result kept beside it.

### What an AI choice is, and review

The value source `model` already exists (`comeni_core.review.answer.ValueSource.MODEL`). The
agent's decisions carry it all the way to the IR and `pipeline.yml`; they are never folded into
the goal as if a person had made them (today a pin in the goal reads as "no choice existed",
which would make the AI's choice look like settled intent).

- **Tier.** A choice where no rule decided keeps tier 4, source `model`, and stays flagged for
  review, as CLAUDE.md's invariant requires. A choice that overrides a rule is tier 4, source
  `model`, with the rule's own result kept beside it in a new field on the reason (the rule, its
  value, its citation), so the saved pipeline shows both. This is a `comeni-core` artifact and IR
  change, with a stored-shape bump and a migration.
- **Review never blocks** (operator's call, on the recommendation "never block, always show").
  Compile, Run, keep and publish all work with unreviewed AI choices. `pipeline.yml` records
  each AI choice and whether a person reviewed it. Keep and publish show a summary ("3 choices by
  the AI, not reviewed") with one *Looks right* for all, as a nudge, never a gate.
- **The tier-4 resolution AI point** (`comeni_core.egress.resolution`) retires: the agent answers
  open questions itself through the change tools.
- **Rule learning (#462)** learns only from answers a person gave or reviewed; the AI's
  unreviewed decisions are not evidence, so rules cannot learn from the AI's own choices.

### The agent loop

The loop runs as a job on the AI worker, one job per person's message: build the context, call
the model with the tool definitions, run each tool call it makes, feed the results back, and
repeat until it replies without a tool call or asks the person. A turn has a step limit and a
token limit; reaching either ends the turn with a message saying so.

The context the model starts from: the conversation so far, the decision record, the pipeline as
built, the protection level, and a system prompt written for this role — an agent that builds
bioinformatics pipelines with this engine, explains its choices, teaches as it goes, and never
claims a value it did not get from a tool.

Model access, recording and refusal follow what exists: the builder's model setting and AI point,
an `ai_invocation` row per model call, coded failures. A turn that fails says so in the chat and
offers to retry; it never leaves "Working on it" standing (#493).

### What the person sees

- **The chat is the agent's thread.** The person's messages, the agent's messages, and between
  them a compact line per tool call ("Read the alignment rule", "Chose STAR for alignment",
  "Resolved the pipeline: 7 steps, 1 value open"). While a turn runs, the lines appear as the
  calls happen; when the agent replies, they fold into one "How I got here" line that can be
  opened. Progress reaches the page through the session read it already polls.
- **A question from the agent** shows as a message with its answer shape as controls (option
  buttons, a number field, an upload). Typing an answer in the composer works as well.
- **What the AI did** is marked where it shows: on the canvas node ("chosen by the AI — review"),
  in the agent's message that did it, and in the pipeline file. Reviewing is the person saying
  so, or changing it.
- **The canvas** updates as the agent works. The first screen is the same chat: the agent's
  trail shows what it is doing from the first message.

### The MCP server

Mounted in the Mendel API with the Python MCP SDK, serving the tool layer's definitions. Mendel
has no accounts, and in production the API is public behind nginx, so **the MCP endpoint
requires a bearer token** from `.env` (`MENDEL_MCP_TOKEN`) in every environment, and the
production overlay refuses to start it without one. A client may create a draft or open an
existing one, and works on one draft per session. Its decisions are recorded with the client's
name as the actor, `actor_kind = model`. The ask-the-person tool, called by an MCP client,
returns the question to that client: its own user answers.

### Working alongside the agent

- **What the person keeps until plan 2:** the canvas (selecting, moving, removing a step, the
  existing step sheet with its settings, optional inputs and swap), *What was understood* with
  its fact corrections, and sample upload as an answer shape of the ask tool. These write
  through the same change writer, recorded as the person's. The retired stage cards go.
- **While a turn runs,** a person's message waits behind it, as messages do today, and a
  person's edit on the canvas applies at once. Every write carries the draft's decision revision;
  a write against a revision that moved is refused, and the agent re-reads and continues. The
  same check keeps the in-app agent and an MCP client from overwriting each other on one draft.

### Characterisation and where tools run

The agent may ask for a sample to be characterised, as a tool: the person uploads through the
ask tool's upload shape, and the characterisation model call (door 6) runs as it does today,
inside the agent's turn. The agent loop runs on the AI worker; its tool calls (resolve, compile,
characterise) run there in-process, each with its own timeout, and the worker's docstring is
updated to say so.

### Data and the protection level

The agent's tool results going to a model are **one new egress door**, declared in
`comeni_core.egress` and walked by `tests/guards/test_egress.py` like the others. Its payload is
a union of the tools' typed views, so the guards still see every shape. Where a view needs what
the guards forbid today (free text, a sample's name, a returned Nextflow file), the guard is
loosened for this door only, as a recorded level-0 loosening, the way characterisation's door 6
was: the invariant documents and `tests/fixtures/guard-ledger.md` say what was loosened and why.
A new crossing in `services.protection` (the agent reading lab data) is allowed at level 0.
Stricter levels filter tool results; none is built here.

### `does:` on a contract

A contract may declare a one-line `does:` describing what this step does, as opposed to the
tool's description of the whole suite (SAMTOOLS_FAIDX and SAMTOOLS_SORT both read as "samtools"
today). It is optional, validated as prose, carried in the step tool's result, and never shown
in the chat as written. The forge drafts it. The engine accepts the optional field in this build; the
registry fills it in its own repository after the `ENGINE_REF` bump, and the agent works without
it until then.

### What retires

The scripted flow: the authoring phases and their state diagram, the goal card, gap questions,
step proposals and the walk, pacing, wrap-up receipts, and the frontend's cards and stages built
for them. In code: `mendel_api/stages/` (describe, gathering, goal, building, correcting,
samples), the authoring protocol and its commands in `mendel-authoring`, the authoring jobs and
the builder prompts they use, and the matching frontend blocks. Anything still needed — the
decision record, the change writer, gap and need computation as a read tool, sample upload and
characterisation, review applicability as "what the AI did that you have not looked at" — is
kept and reused by the tools. `comeni-flow` stays: the forge uses it.

The design documents and CLAUDE.md lines that describe the scripted flow are updated in the same
work: the boundary "the engine decides, models answer typed questions" becomes "the engine
validates, routes, applies rules as advice and emits; the agent chooses, recorded as the AI's".

## Where it is built

On a new branch from `main`, after PR #491 (#463 parts 5–6 and the walk fixes) merges: the
scripted-flow code this deletes is what that PR last changed.

## Constraints

- Pure packages stay pure: the tool layer, the agent loop and the MCP server live in
  `mendel-api` and `comeni-ai`, not in `mendel-resolver` or `mendel-compiler`.
- Tests never call a live model. The agent loop is tested with recorded, scripted model
  responses (a fake transport returning tool calls).
- Generated clients are rebuilt with `make client`.
- No backward compatibility before v0.1.0: retired code and stored shapes are deleted, with a
  migration for stored rows, not aliased.

## Left to the builder

- The tool names, their exact input and output shapes, and how they are grouped in the module.
- The system prompt's wording, within the role described above.
- The agent turn's step and token limits.
- How the trail lines are worded and stored, as long as each names one tool call.
- How the thread is stored (a table of messages and tool calls per session, or extending the
  existing turns).
- The order of the work, with one exception: the first task checks, live on the dev stack, that
  tool calling works through LiteLLM's `chatgpt/` subscription route. If it does not, the loop
  uses a JSON action protocol instead (the model returns one typed action per call), which every
  provider supports; the tool layer and everything above it do not change.

## Plan 2, after this one

Designed with the operator on 2026-11-14 and kept here so they are not lost. Each gets its own
short spec and plan once the agent ships, written against the agent's chat rather than today's.

- **The right-click menu on a step, and its cards.** Right-click a step (a long press or `⋯` on
  a phone, the menu key from the keyboard): *Ask about this step* (the chat, with the step
  named), *Settings…*, *Inputs…*, *Swap tool…*, *Show in pipeline file*, *Keep whole* (only
  where a step can be split), *Remove step*. No *Why is it here?*: that is asked in the chat.
  Each option opens its card beside the node, one at a time; the chat stays where it is, Esc
  closes. Settings: what needs the person, then optional values, then measured and settled ones,
  each opening its reason in place. Inputs: each optional input off, optional or required, with
  what it adds. Swap: the alternatives, each previewed on the canvas. An input node offers its
  name, whether it is one file for the run or one per sample, and lanes; empty canvas offers Add
  step, Fit and Tidy.
- **The pipeline file page: direction A with the AI panel (C).** Canvas:
  https://claude.ai/artifact/8RFVyhMU7NNWSy7hU56UwN (direction B was rejected as AI bloat). An
  outline beside the file (goal, what you gave, facts, steps with their state, decisions, checks,
  and the settled/measured/optional counts); real file tabs (`pipeline.yml`, `main.nf`,
  `nextflow.config`); folded sections; clicking a value opens its reason, tier and citation
  beneath it with *Ask the AI* and *Change*; selecting any text offers *Explain this*, *Ask about
  it…*, *Copy*. The AI panel on the right is the same conversation as the builder's chat, folds
  away, and labels its answers as the AI's with links to the lines and citations they used. The
  empty "click a value" column goes (#495).
- **Canvas polish.** A step with many ports labels its outputs as its inputs are labelled and
  grows to fit them, nothing stacked off its edge; each wire meets its own port's row, not a
  bundle (#494). The chat keeps a fixed height and scrolls; a new message animates in without
  moving what is above it; the canvas never re-zooms by itself, fitting only when its tab opens
  or Fit is pressed (#494, #496).

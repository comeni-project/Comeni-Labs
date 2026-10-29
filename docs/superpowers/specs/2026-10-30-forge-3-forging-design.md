# Forge MVP 3 — forging: proposals, approvals and chat

**Issue:** #364 (parent #360). **Status:** written for review (2026-10-30).
**Numbering:** GitHub's (*Forge MVP N*), by the operator's choice; the forge MVP design's
"part" numbers are one lower from MVP 3 on.
**Design:** [the forge MVP design](2026-10-19-forge-mvp-design.md), story step 3.
**Board:** canvas *Forge MVP pages* (claude.ai artifact `8T3V69ZSUr9wLydNUHrKhS`), board
*3 · Forging a tool* (`Forge.dc.html`).
**Builds on:** [Forge MVP 1](2026-10-29-forge-1-catalogue-design.md) (catalogue, tool page,
`mendel-forge`).

*(operator)* marks a choice made in chat on 2026-10-29/30; *(spec)* marks this document's own
call.

## Why

The registry grows only by hand today. MVP 3 is the step that turns an nf-core module the
registry does not hold into a registry tool: the AI drafts each piece, the person approves,
changes or rejects it, and the result is a set of real registry files proven to load. The forge
is not meant to be fully usable until about MVP 6 *(operator)*; what matters now is that the
code each later part builds on is the right code. Tests (MVP 4) run against this part's output,
and pull requests (MVP 5) publish it.

## Goals

1. **A shared flow engine** *(operator: "move the engine out, it's a good refactor")*. The
   builder's declarative protocol engine moves out of `mendel-authoring` into a new pure package
   and becomes generic; the builder and forging both declare their flows on it.
2. **Forging**: an *adaptation* per module version with five pieces — Questions, Contract,
   Parameters, Vocabulary, Rules — each drafted by the AI and approved, changed or rejected by a
   person, with a chat beside it.
3. **A draft layer that loads** *(operator agreed)*: once every piece is approved, the engine
   writes real registry files into a working folder over the registry and proves they load and
   the contract conforms to the module's source.
4. **Any model through LiteLLM** *(operator)*: forging uses the existing `comeni-ai` transport
   and the Settings purpose *forge*, so a local model (Ollama) or an API model both work.
5. **Measured**: quast is forged end to end with the local gemma3:12b and with an API model, and
   the result is recorded *(spec, acceptance)*.

## Non-goals

- Tests (MVP 4, #365), pull requests and the changelog (MVP 5, #366), releases (MVP 6, #367).
  Their steps appear on the page as later parts, disabled.
- Writing anything into the registry or the `registry/` submodule. The draft layer stays in a
  working folder.
- pegi3s, subworkflows, lab layers.

## Anti-goals

- The AI's proposal recorded or counted as the person's choice.
- The AI approving anything.
- A proposal stored with an id that does not exist (or is not proposed as new), or a contract
  whose ports disagree with the module's `main.nf`, presented as valid.
- A draft that has not loaded and conformed shown as finished.
- An adaptation seeing another's unapproved work.

## Constraints

From `CLAUDE.md` and the invariants: pure packages stay pure (the new engine package included);
model calls go through a declared egress boundary with a typed payload, and every reply is
validated where it arrives; registry changes need human approval (here, every piece's approval;
publishing is MVP 5); decisions record who, why and the supplying layer; diagnostics are coded
(`MF05xx`; the engine's own refusals get a code of the shared package's band — see §1).

## The design

### 1. The shared flow engine *(operator chose sharing; shape is the spec's)*

**What moves.** `mendel-authoring` holds a declarative engine: `Stage`, `Node`, `Edge`,
`Protocol` with construction-time validation (`protocol.py`), the interpreter `run`/`follow`
(`interpret.py`, ~120 lines), forks over a snapshot (`forks.py`), and the transition table and
diagram derivation. It is generic in all but four places: it imports the builder's `Phase`, its
forks read the builder's settings, its refusal carries `MI0216`, and `protocol.py` declares the
builder's `Command`/`Event` beside the generic parts.

**Where to.** A new pure package, **`packages/comeni-flow/`** *(spec: `comeni-` because it is
shared across Mendel's two flows and not Mendel-specific)*, on the purity guard's closed list. It
holds:

| `comeni-flow` | stays with each flow |
|---|---|
| `Stage`, `Node`, `Edge`, `Protocol[P]` and their construction checks | the flow's `Phase` enum, commands and events |
| `run`, `follow`, the cycle limit; a refusal whose code the flow supplies | the protocol declaration and the node handlers |
| forks over a generic snapshot of subjects; transition table; diagram export | what a fork's subjects are (builder: settings; forging: facts) |

**Patterns** *(spec)*: the protocol is data run by one interpreter (Interpreter); the core is
generic in the flow's phase type (`Protocol[P]`); the caller supplies what an acting node does
through `enter(node) -> outcome` (Strategy), so the core touches no row, queue or model; forks
read a snapshot the caller builds (ports and adapters).

**Guard.** The extraction changes no builder behaviour: the whole existing suite passes
unchanged, and the builder's generated diagram (`docs/explanation/diagrams/`) is byte-for-byte
identical before and after. This is the first block of work and may land as its own pull
request *(spec)*.

### 2. The forging flow

An **adaptation** is one module at one tool version: `(source, path, version)`, started from the
catalogue. Several may be open at once *(operator)*, each **isolated**: its draft layer sits on
the registry, never on another adaptation's work.

**Pieces, in order:** Questions → Contract → Parameters → Vocabulary → Rules. Tests is shown
after them as MVP 4, disabled.

- **Questions** *(operator agreed)*: what nf-core's files cannot say about fitting *this*
  registry — the role it fills (a registry role or a new one), the registry type of each port
  (an existing type or a new one), whether it competes with a tool already holding that role (so
  a rule is needed), and an optional sentence on what it is being forged for. The AI asks only
  what it cannot settle, as typed questions whose options are real registry ids (plus "something
  new"), each with its reason. A choice it is confident in is not asked but is shown and approved
  with its piece. Answers are recorded as the person's.
- **Contract**: ports with registry types and states, `nf_process`, `nf_include`, the
  `nf_inputs` wiring, roles, container, priority and their reasons.
- **Parameters**: each param with default or *asks the person*, domain, how it is passed
  (`via`, key, template) and its `because`; fixed `ext_args` with theirs.
- **Vocabulary**: new types, states and measurements the contract needs, if any.
- **Rules**: new decisions or edits to an existing role's rule (adding a tool beside STAR in
  `alignment` must not leave routing tied), or "none needed" when nothing competes.

**Revisions, never overwrites** *(operator agreed: typed commands, append-only revisions)*. Each
item a piece holds keeps its history: drafted by the AI, revised by the AI at the person's
request, changed by the person. Every revision records its actor, reason, and the model
invocation that produced it if any. **Commands** move the flow: the AI may issue `draft`,
`revise`, `add` and `propose_removal`, each a **proposal** that waits for approval; only a person
may issue `answer`, `write`, `approve`, `change`, `reject` and `remove`, each a **decision** that
counts at once *(operator: the AI may propose writing, changing or removing anything; only
approval makes it count)*. An approved removal takes the item out, recorded with the AI's
reason and the person's approval. The engine refuses an approval from the AI (an `MF05xx` refusal, guarded by a test).

**Who drafts is the person's choice** *(operator)*. Each piece opens with two ways in: **Draft
with the AI**, or **Write it myself**, which opens the piece empty (or, for a re-forge, as the
registry has it) for the person to fill in. The person can switch at any point: start by hand and
ask the AI to fill the rest, or take an AI draft and rewrite it. An item the person writes is
recorded as theirs and counts as their decision; it still passes the same checks as an AI
draft (§3's validation now, load and conformance at assembly).

**Drafting order** *(spec, after the builder check)*: strictly piece by piece. The AI drafts a
piece only once the piece before it is approved, so each draft is grounded on approved work and
validated against it; that is one AI job per piece, waiting on the person between them, as board
3 shows (Parameters proposed while Contract is done). *Approve the rest* approves the remaining
items of the current piece.

**Re-opening.** Changing an approved item re-opens the items that depend on it (a port's type →
the parameters wired to it, the vocabulary it needs). A re-opened item **keeps its value and
loses its approval**; nothing is re-drafted unasked. Dependencies are declared **per piece** in
the forging protocol (in `mendel-forge`), and which items they touch is matched at run time;
`comeni-flow` needs no notion of items *(spec, after the builder check)*.

**Reject opens a conversation about the item** *(operator: "we should choose what we change …
more like a chat")*. Rejecting never re-drafts on its own. It marks the item rejected and opens
the chat on that item, asking what is wrong; the person then chooses: write the new value
themselves (`change`), or tell the AI what to change, and the AI answers with a `revise` whose
new revision waits for approval. A rejected item blocks its piece until it is changed, revised
and approved, or (for an optional item, such as a param) removed by the person.

**The chat runs through the whole of drafting** *(operator: "so I can say, why not have this
rule")*. The person can ask anything, about the tool, a piece or one item (a message can be
attached to an item, so the AI knows what it is about), and it is open whether the AI or the
person is drafting. The AI's reply may carry commands: `revise` an existing item, `add` a new
one (a rule, a param, a state) the person asked for or the AI suggests, or `propose_removal` of
one that should not be there, each waiting for approval. The AI may also answer that something does not fit and say why, with no
command. The chat never approves.

**Assembly.** When every piece is approved the engine writes the draft layer (§4). A failure
there re-opens the piece it blames (a conformance mismatch → Contract; a load error naming a
type → Vocabulary).

**The forging protocol** is declared on `comeni-flow`: phases such as `asking`, `drafting`,
`reviewing`, `assembling`, `assembled`, `failed`; acting nodes for the AI (draft, revise) and
for the engine (assemble); waiting nodes for the person. Its diagram is generated like the
builder's.

### 3. The AI

- **Transport and model** *(operator)*: `comeni-ai`'s LiteLLM transport and the existing
  Settings purpose `forge` (*Adapting tools*); no new plumbing. Jobs run on the existing AI
  worker queue *(operator: "queue")*, so drafting for several adaptations waits its turn; the
  page shows *drafting…* while a job is queued or running.
- **Egress** *(spec)*: a new declared boundary, `forge_drafting`, in the `FORGE` flow
  (`comeni_core/egress/boundaries.py` already reserves it), with a typed payload: the module's
  public nf-core files and catalogue entry, the registry's ids (roles, types, states,
  measurements, competing contracts) and the adaptation's answers and approved items. No lab
  data reaches it; the egress guard holds the payload to that.
- **Typed replies, validated on arrival**: each step's reply is a declared Pydantic model
  (questions, a contract draft, parameter drafts, vocabulary drafts, rule edits, a chat reply
  with optional `revise` commands). Before anything is stored: every id names a registry entry,
  vocabulary proposed in this adaptation, or *pending* vocabulary (§5); ports and inputs agree
  with the module's `main.nf` (`ModuleSpec`); a param's route names a real input or ext key.
  An invalid reply is a coded refusal recorded on the invocation and returned to the AI once
  with the reason; a second failure is shown to the person. It is never stored as a proposal.
- **Recorded**: every call is an `ai_invocation` row (agent `forge`), as the builder's are.
  Prompts are versioned files beside the builder's (location left to the builder).
- **Measurement** *(spec)*: the plan forges quast with gemma3:12b and with an API model and
  records, in the journal, whether each reached a draft that loads and conforms and how many
  revisions it took. The default model is not changed by code; if the local model fails, the
  page says so and the operator picks an API model in Settings.

### 4. The draft layer

- A folder per adaptation under the forge cache (`MENDEL_FORGE_CACHE/drafts/<id>`, *spec*)
  holding a layer: the module's source vendored with `comeni_vendor.ops.add` at the catalogue's
  snapshot commit, `module.yml`, `contract.yml`, new vocabulary files, and copies of shared files
  it edits (rule tables, a role's alternatives).
- **Proven** with existing code: `mendel_resolver.layers.load([registry, *pending, draft])`
  loads it (so `MD0025` and every loading check apply), and `mendel_compiler.conformance.check`
  holds the contract to its module. The page shows each file and the result.
- **The base is the registry the app loads** (`MENDEL_REGISTRY_ROOT`) *(spec, after the builder
  check)*. The MVP design's answer 1 starts forging from `comeni-registry` main; in development
  the app's registry is a clone that follows main, and fetching main on its own is MVP 5's job,
  which needs a working clone of `comeni-registry` to open pull requests from anyway. The
  adaptation records the base's commit (or layer digest). **A moved base is re-checked, not
  rebased**: assembling always loads over the current base, so an adaptation drafted against an
  older registry is re-validated and, if something it relied on changed, the blamed piece
  re-opens.

### 5. Pending vocabulary *(operator)*

A later adaptation may use vocabulary from an adaptation that is **assembled** (all approved,
loads and conforms), tagged `pending` and shown as "from bwa/index's approved draft, not in the
registry yet". The later adaptation records that it **depends on** the earlier one; its draft
loads with **the earlier draft layer whole** stacked beneath it (vocabulary, contract and any
rule edits), so a later rule edit is made on top of the earlier one rather than beside it
*(spec, after the builder check)*. Two open adaptations that edit the same shared file without
depending on each other are allowed; assembling the second says which other adaptation edits
that file, and MVP 5, which publishes one pull request at a time, resolves the order. If the earlier adaptation
re-opens or is abandoned, the later one is marked *depends on a draft that changed* and the
items using that vocabulary re-open. MVP 5 will publish in dependency order. Drafts still in
progress are never visible to another adaptation.

### 6. Storage and API *(spec, shape left to the builder within these rules)*

- Tables in `mendel-api`: adaptations (module, version, base commit, phase, depends-on, who
  started it, when), items with append-only revisions (piece, key, value as JSON, actor,
  reason, invocation, at) and decisions (approve/change/reject, who, when), and chat messages.
  JSON columns are registered shapes (`shapes.py`), as MVP 1's were.
- Routes under `/forge/adaptations`: start, read, the person's commands, chat, assemble, and
  abandon. Refusals are coded `MF05xx`. Clients regenerated with `make client`.

### 7. The pages (board 3) *(operator: as drawn)*

- **Catalogue**: *Forge \<name\>* becomes active for a module not imported; *Update to X*
  starts an adaptation for the new version that begins from the registry's current contract
  *(spec; cut first if time runs short)*. A module with an open adaptation links to it.
- **Forging tab**: the open adaptations, each with its progress, and its phase.
- **Adaptation page** `/registry/forging/<id>`: pieces on the left (done, waiting for you, not
  yet), the current piece's items in the middle with value, route, reason and who proposed it,
  **Approve / Change / Reject** and **Approve the rest**, the chat on the right, "N of M
  approved" in the header. When assembled: the files and the load/conformance result.
- **Wording** *(operator: GitHub numbering)*: the disabled actions MVP 1 drew say *Tests come in
  MVP 4*, *Pull requests come in MVP 5*, *Releases come in MVP 6*.

## Testing

- **Engine extraction**: the builder's suite unchanged and green; its diagram byte-identical;
  `comeni-flow` tested on its own with a small declared flow; on the purity guard's closed list.
- **Forging flow, pure**: each command's legality by actor (the AI cannot approve), re-opening
  by declared dependency, assembly failure re-opening the blamed piece, pending-vocabulary
  dependency marking.
- **AI boundary**: recorded replies (no live model in tests), including invalid ones: an unknown
  type id, a port `main.nf` lacks, a param routed to nothing — each refused and never stored.
- **Draft layer**: assembling a recorded quast adaptation into a temp folder that loads and
  conforms; a deliberately wrong contract that fails conformance and re-opens Contract.
- **API** through the test database; **pages** with Vitest and in a browser against board 3 at
  1440 and 390 px, light and dark.
- **Live**: quast forged with gemma3:12b and an API model, recorded in the journal.

## Left to the builder

- The tables' exact columns; the routes' exact shapes.
- Prompt wording and location; how drafting is split into calls (per piece or batched).
- How the forging protocol's phases and nodes are named, within §2.
- The draft folder's layout beyond §4.

## Order of work

1. Extract `comeni-flow`; the builder declares its flow on it, unchanged.
2. The forging protocol, commands, revisions and re-opening (pure, in `mendel-forge`).
3. Tables and the API.
4. The AI: egress boundary, typed replies, validation, prompts, jobs.
5. The draft layer: vendoring, files, load and conformance.
6. Pending vocabulary and dependencies.
7. The pages: Forge action, Forging tab, adaptation page; the MVP wording.
8. Docs; the live quast forging with both models.

Cut first if time runs short: *Update to X* (re-forging an imported tool), then pending
vocabulary (an adaptation waits for the earlier tool to reach the registry instead).

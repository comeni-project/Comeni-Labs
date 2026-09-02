# The builder is a builder, not a visualiser

> **VERIFIED against the code on 2026-08-23.** The first draft (2026-08-19) carried a NOT
> VERIFIED header because its `validate()` signature was a proposal written against files that
> had been read but not exercised. Every type named below has now been opened. **Three things
> the first draft got wrong are corrected in place and marked §C1–§C4**, and the decisions the
> operator took on 2026-08-23 are recorded in §7, §8 and §9. What has *not* been exercised is the
> frontend work: §10 is an inventory of what 3C shipped, not a measurement of what it costs to
> change.

## 1. What is wrong

Plan 3C built a **viewer**. A goal goes in, the resolver searches for a graph, and the canvas
draws what it found. Nothing on that canvas can be changed, and the affordances that suggested
otherwise — a `draggable` module row, a crosshair cursor on a port — were removed in the same
session they were noticed, because a control that moves under your hand and does nothing is worse
than one plainly not offered.

**Galaxy is the other thing.** You assemble a workflow by hand, and the tool checks it: this
output can feed that input, this one cannot, this required input has nothing behind it.

The operator's framing, which is the whole spec in one sentence:

> it should check that your pipeline is also valid AND give you the resolved one, basically the
> AI can "use" the builder, such as a human would

## 2. The insight: it is the same knowledge from a different route

**`resolve()` searches. A builder checks.** Opposite directions through facts that already exist:

| what a check needs | where it already is |
|---|---|
| what a port emits | `OutputPort.type_id`, `OutputPort.state` |
| what a port demands | `InputPort.type_id`, `.state_required`, `.accepts`, `.cardinality` |
| which contracts can feed a type | `registry.producers_of` |
| whether a contract matches its module | `conformance.check` |
| what a value means and where it goes | `Setting.via`, `Why` |
| that a person chose this module | `ProducerDecision.human_override: ContractId \| None` |
| that a person chose this edge | `SourceDecision.human_override: EdgeRef \| None` |
| that a person set this value | `ParamDecision.human_override` |

**Nothing new needs declaring.** What is missing is a verb, not data — and the operator named
exactly why it is a separate one: *it needs the whole "where" and "to"*. The resolver is handed a
goal and asked to find edges; a builder is handed edges and asked whether they hold.

**The last three rows are the strongest fact in this spec and the first draft did not know them.**
A builder lets you do exactly three things — pick a module, draw an edge, set a value — and all
three already have a declared slot saying a human did it, shipped in Plan 1.10. `mendel upgrade`
already replays them so that only what you touched can move. This is a screen for machinery that
exists, not new machinery.

## 3. `validate(graph, stack) -> Verdict`

In `mendel-resolver`, pure, no network, golden-testable.

**Per edge**, given `(from_node, from_port) → (to_node, to_port)`:

- the source port exists on that contract, and is an **output**
- the target port exists, and is an **input**
- `source.type_id` satisfies `target.type_id` — or matches an entry in `target.accepts`,
  each an `Alternative` carrying its own `type_id` and `states`
- `target.state_required ⊆ source.state`
- **the arity is legal** — `target.cardinality` against how many wires reach it.
  **See §C4: nothing has ever read this field.**

**Per node:** every `consumes` port either has a wire or is met by an entry channel. That second
half is not optional: `star_align.gtf` arrives from `params.gtf` and has no incoming edge, and a
check that looked only at edges drew a hollow *unmet* dot on a satisfied input — the one defect
of this kind that 3C shipped and caught.

**Per graph:** no cycles. Routing already forbids them by construction (`producers_of` excludes
the node itself); a hand-drawn graph has no such protection, which is precisely the difference
between searching and checking.

### §C1 — the diagnostic band is `MD0500`, not `MD04xx`

The first draft said "`MD04xx` or wherever the next band is". **`MD0400`–`MD0499` is already
allocated** — `diagnostics.yml:16` declares it for *gates and emission*. It is empty today, and
that is not an invitation: the file's own header says **a code is never renumbered**, because a
published code is something a laboratory runbook can cite, so borrowing an allocated band is a
decision that cannot be undone cheaply.

Validation takes a new declared band, added to the header comment:

```
MD0500-MD0599  validating a hand-built graph
```

### §C2 — a verdict has three levels, because `InputPort` has three kinds of requirement

The first draft's checks read `state_required` and stopped. `InputPort` also declares
**`state_required_conventional`**, **`state_preferred`** and **`prefer`**. An edge can therefore
be *legal* and still be something the resolver would never have chosen, and a check that returns
a boolean cannot say so.

`Verdict` is a list of coded findings at three levels:

| level | means | example |
|---|---|---|
| `illegal` | the graph cannot be emitted | a BAM port wired into a FASTQ input |
| `unmet` | something required has nothing behind it | an input with no wire and no entry channel |
| `advisory` | legal, but not what convention or a rule would pick | an unsorted BAM where `state_preferred` is `coordinate_sorted` |

### §C3 — there is no untyped input port, and `alternatives()` already exists

The first draft said `InputPort.type_id` defaults to `""` and needed an explicit rule for an
untyped port. **It cannot happen.** `contract.py`'s `_one_form` validator refuses a port
declaring neither `type_id` nor `accepts`, and refuses one declaring both. The default is a
default, not a reachable state, and the rule the first draft proposed would have been dead code.

**What is there instead is better.** `InputPort.alternatives()` already returns the exact list
`validate` needs — the conventional form first, the structural form as fallback — and its
docstring states the semantics: *"a BAM, or failing that a CRAM", first-match-wins*. The router's
`_satisfy_port` walks it and collects failures for its message.

**So `validate` reuses `alternatives()` rather than re-deriving the comparison.** The three kinds
of requirement in §C2 are already folded into it: the first alternative carries
`state_required | state_required_conventional` and the second carries `state_required` alone. An
edge satisfying only the second is `advisory` — legal, and not the conventional form. That is
§C2's third level falling out of a method that already shipped, rather than a rule invented here.

`state_preferred` / `prefer` stays outside `alternatives()` and is checked separately, because it
is a preference between *sources*, not between kinds of input.

### §C4 — `cardinality` is declared and read by nothing

`InputPort.cardinality: str = "1"` has no consumer anywhere in `packages/`. `MD0505` would be its
**first reader**, which means the field has never been exercised: no contract's value for it has
ever been checked against reality, and the corpus may well contain a wrong one. The arity check
is therefore written last of the edge checks, and Task 3 includes reading every landed contract's
declared cardinality before trusting it.

### It reports; it does not refuse

**`validate` returns every finding, not the first.** The precedent is the forge's `verify`
ladder, which reports, and the reason is the same: three problems visible at once is one pass
through the screen, and three refusals is three.

Refusal stays where it already lives — `mendel emit` and the gates. A graph with an `illegal`
finding cannot be kept as a `pipeline.yml`; that is §9's boundary, not `validate`'s.

## 4. The endpoints, and the AI is a client of them

```
POST /api/pipeline/validate        a graph          -> Verdict
POST /api/pipeline/compare         a graph + a goal -> Comparison
POST /api/pipeline/drafts          a draft          -> DraftId
GET  /api/pipeline/drafts/{id}     -> a draft
POST /api/pipeline/drafts/{id}/keep -> writes pipeline.yml
GET  /api/pipeline/compatibility   -> the index of §8
```

`POST /api/pipeline` (resolve a goal) and `GET /api/pipeline/modules` already exist and do not
change.

**The AI is not a special path.** `CLAUDE.md` already says the AI is the engine's primary
operator and that `pipeline.yml` is the save file it *"sets down, picks up, tunes and re-emits"*.
This makes that literally true: a model drafting a pipeline calls the same verbs a person's
clicks call, and neither can do anything the other cannot.

**That is also the strongest argument for validation being a server verb.** A check implemented
in the browser would be a check the AI cannot run, and then there would be two answers to *is this
legal*. §8 gets the browser its instant feedback **without** creating that second answer.

## 5. Two pipelines on one canvas — one call, not two

The screen shows **what you drew** and **what Mendel resolves**, and where they differ.

**`compare` is a single endpoint** taking both the graph and the goal, running `validate` on the
first and `resolve` on the second, and returning both plus a per-step alignment: `same`,
`yours-only`, `mendel-only`, `differs`. Two separate calls stitched together in the browser would
put the alignment — which is a judgement about *what counts as the same step* — in the one place
the AI cannot reach.

From an alignment row you can:

- **adopt** the resolver's choice for a step, which rewrites your graph client-side
- **keep** yours, which is an override and writes a `ProducerDecision` or `SourceDecision`
  with a required reason, and gets a `DecisionRecord` like every other (invariant 9)
- see **why** they differ — a tier-3 rule fired on a measurement you did not account for

**`mendel upgrade` is already this machinery.** It re-resolves against the current registry and
replays every recorded decision so that *only what you touched can move*. A builder is that, with
the diff on screen rather than in a report.

## 6. What this changes about `Goal`

**Nothing, and that is the point.** 3C concluded a `Goal` cannot pin a module — `have`, `want`,
`constraints{required_states, params}`, `profile` — and treated that as a blocker. It is not: **a
builder does not edit a goal, it edits a pipeline.** `pipeline.yml` is the artifact with steps,
channels and settings in it, and `mendel emit` already rebuilds Nextflow from one with no registry
and no network.

A producer-pin field on `Goal` was considered and is **not** the answer here. It would put "which
tool" into the *question* when it belongs in the *answer*, and every pipeline anybody had already
built would still need editing some other way.

## 7. Who overrode: a human, or a model

**Decided 2026-08-23.** `human_override` keeps its meaning. A choice made by a model writes a
sibling field carrying `ValueSource.MODEL` and the model id, on all three decision kinds.

The reason is A130 arriving from the other direction. `decision.py:152` calls `human_override`
*"the one field in the system that is by design a person's answer"*, and the moment an agent
driving the API writes there, that sentence is false and a pipeline the AI assembled is
indistinguishable from one a person drew by hand. That distinction is the product. `ValueSource.MODEL`
already exists precisely so a model has somewhere truthful to write; this is the same argument
that put it there.

**This is a `SCHEMA_VERSION` bump on `comeni-core`, which is a break** under
`docs/guides/releasing.md`. It wants to be one deliberate change at the start of the work, not
something discovered halfway through.

**It does not weaken invariant 3.** A model drawing a graph is a *user* of the engine, not a
point inside it — `CLAUDE.md` states this directly: *an agent driving the CLI is a user of it,
outside the engine, and invariant 3 constrains what Mendel calls rather than who calls Mendel.*
The review rail gains a third state so a reviewer can see which edges the AI guessed.

## 8. The network design

**The budget is the operator's, recorded in the performance audit:** *"max like half a second for
normal stuff doing in the browser. it's a tool, not a server."*

**What the measurements say.** After Plan 3A phase 7, `layers.load` is cached on the registry
digest and a registry-touching request is **~10ms warm**. The audit's flat conclusion was that
*the resolver is not where the time goes, at any size* — at 500 contracts, 4.3s of a 5.09s
`mendel build` was `layers.load`. `validate` and `compare` therefore land at **10–25ms warm**,
inside the budget by a factor of twenty. Every route handler is a sync `def`, so FastAPI runs it
in a threadpool and nothing blocks the event loop.

**So the design is not laggy. The risk is that it is chatty, and there is one lag source that a
round trip cannot fix.**

### 8.1 The client edits locally

Drag, connect, delete, move — **none of these touch the network.** The working graph lives in the
browser. Three explicit calls exist: `validate`, `compare`, `save`. Nothing fires per keystroke
and nothing fires per frame.

### 8.2 The compatibility index — instant feedback without a second implementation

A wire should turn green while the mouse is still moving, and 10ms of network is not the problem:
a round trip per drag frame is. But a compatibility check written in TypeScript is precisely the
drift this repository keeps paying for — the tier vocabulary hardcoded in a React file, the
`Standing` union declared in two places — and §4 is right that it would be a check the AI cannot
run.

**The server computes the answer; the client looks it up.** Served alongside the module list:

```
GET /api/pipeline/compatibility  ->  { (type_id, states) : [input types it satisfies] }
```

A pure function of the registry, cached on the digest like everything else. The client indexes
into it. It never decides.

**Keyed on type, never on port pairs.** Port-pair keying is ~24M entries at 2000 contracts;
type keying is bounded by the vocabulary, which is closed (invariant 7).

**Held by a golden test:** generate the index, run server `validate` over every pair it covers,
and assert they agree. One rule, one answer, and a divergence fails rather than misleads.

### 8.3 `validate` on drop, `compare` on demand

`validate` fires when a wire is dropped or a node is placed — a gesture, not a frame. `compare`
runs a full resolve and is a **button**. That matters most for the AI, which is the client most
likely to call it in a loop.

### 8.4 `ETag: <registry-digest>`

On `/modules` and `/compatibility`, both pure functions of a digest the server already computes
as its cache key. A reload becomes a 304 rather than the whole contract list. It reuses machinery
rather than adding any.

### 8.5 Saving

Explicit save, plus a long idle debounce of about five seconds. One draft is one JSON document,
one row, one write. Nothing streams.

### 8.6 A known cliff, named rather than built for

`GET /api/pipeline/modules` returns **every** landed contract. At the twelve that exist this is
nothing. [Issue #77](https://github.com/comeni-project/Comeni-Labs/issues/77) puts the real number
at **~1,600** once nf-core and pegi3s are ingested, and at that point the picker needs
server-side search and the index needs to ship incrementally. Building pagination for twelve rows
now would be the worst-case-scenario engineering the performance audit was commissioned to look
for and did not find.

Also recorded: `digest_of_directory` costs **4.6ms per request** as the cache key. That is the
real per-request floor and it grows with registry size. Fine today; named so it is not
rediscovered.

### 8.7 What is rejected

**No WebSocket and no live sync.** One user, local edits, three calls. A socket would be
infrastructure serving nothing, and it would make the AI's path structurally different from the
browser's — which is the one property this entire design exists to preserve.

## 9. Where a pipeline lives between edits

**Decided 2026-08-23: a draft is a Postgres row under an opaque, server-generated id. Keeping it
writes the `pipeline.yml`.**

**The first draft of this spec preferred a path, and the API had already ruled that out in
writing.** `routes/build.py:8`: *"Invariant 15 is why the body is a `Goal` and not a path: no
input here accepts a sample identifier, a filename or a path."* A path arriving over HTTP
collides with a stated invariant whatever it happens to point at. An opaque id is not a filename.

**On the files-not-database rule — it is narrower than it reads.** `CLAUDE.md` says
"***Declared* data is files, and a database is a design error**", and
`docs/design/declared-data.md` argues it for contracts, rules, vocabularies and measurements, on
the ground that those need diff, blame, review, signature and merge — the five things a cited
registry sells. **A half-drawn draft needs none of those until it is landed.** The rule does not
need repealing; its scope needs saying out loud, which is what this paragraph is for. The
existing tables are the precedent and they point the same way: `queue_visit` and `source_check`
hold operational state, not artifacts.

One Alembic migration. `POST /drafts/{id}/keep` is where a draft stops being state and becomes an
artifact — it runs the gate, refuses on any `illegal` finding, and writes the file.

## 10. What already works and should not be rebuilt

Verified during 3C: the canvas, the deterministic layout, the ports, the tier rails, the
provenance bar, the settings card, the rail. **They render a pipeline, and a hand-built pipeline
is still a pipeline.** What has to change is where that pipeline comes from and whether the screen
can write one back.

## 11. Testing

- **Golden files for `validate`** — one legal graph, and one graph per finding code, so a code
  that stops firing fails rather than goes quiet.
- **The index agrees with the verb** — §8.2's generated-vs-computed test.
- **Round trip** — `save → keep → mendel emit` produces byte-identical Nextflow against the
  same registry. That is invariant 10 applied to the hand-built path.
- **`make verify`, not `make check`.** This touches `resolve.py`'s neighbours and
  `comeni_core/artifact/pipeline.py`, both on `CLAUDE.md`'s named list.
- **jsdom has no layout engine.** 3C's journal records this: canvas geometry is not something
  these tests can be wrong about, and a guard asserting a class name is worth what testing a CSS
  string is worth. Drag behaviour needs its state tested, not its pixels.

## 12. Size, and the cut line

**Five deliverables**: a resolver verb with a diagnostic band, a schema break, the endpoints with
persistence, the compatibility index, and a canvas that edits. The estimate is two long sessions,
and the operator's standing note is that estimates on this project run about **10x** over.

**The cut line, agreed in advance, is `compare`.** Everything else stands without it. It is also
the piece the operator identified as the point of the whole screen, which is exactly why it is
written down here rather than taken quietly if the work runs long — `CLAUDE.md`'s *stop and speak
when the estimate breaks* exists because that decision was once taken silently at 1am.

## 13. What is still open

- **What `keep` does when a draft has `advisory` findings only.** Writing the file is probably
  right — advisory is not illegal — but it should ask once rather than decide silently.
- **Whether `compare` needs the worker.** At 10–25ms it does not. Issue #77's precedent — the
  catalogue total is *"the worker's job, not the request's"* — is what to reach for if the
  registry grows past the budget, not before.
- **Alignment tuning on the canvas**, deferred by the operator after 3C and still deferred.
- **The forge.** The operator is rethinking its design separately (2026-08-23). Nothing in this
  spec touches `mendel-forge`, and the two can proceed in parallel.

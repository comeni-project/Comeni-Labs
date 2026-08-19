# The builder is a builder, not a visualiser

> **NOT VERIFIED.** Written 2026-08-19 from the operator's reframing, against types that were
> read but not exercised. Nothing here has been built, and the `validate()` signature below is a
> proposal rather than a discovery. **Read the code before executing any of it** — this
> repository's own rule, and the last two plans each got a signature wrong writing against a
> file they had only skimmed.

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
| what a port emits | `produces[].type_id`, `produces[].state` |
| what a port demands | `consumes[].type_id`, `.state_required`, `.accepts`, `.cardinality` |
| which contracts can feed a type | `registry.producers_of` |
| whether a contract matches its module | `conformance.check` |
| what a value means and where it goes | `Setting.via`, `Why` |

**Nothing new needs declaring.** What is missing is a verb, not data — and the operator named
exactly why it is a separate one: *it needs the whole "where" and "to"*. The resolver is handed a
goal and asked to find edges; a builder is handed edges and asked whether they hold.

## 3. `validate(graph, stack) -> Verdict`

In `mendel-resolver`, pure, no network, golden-testable.

**Per edge**, given `(from_node, from_port) → (to_node, to_port)`:

- the source port exists on that contract, and is an **output**
- the target port exists, and is an **input**
- `source.type_id` satisfies `target.type_id` — or is listed in `target.accepts`
- `target.state_required ⊆ source.state`
- **the arity is legal** — `target.cardinality` against how many wires reach it

**Per node:** every `consumes` port either has a wire or is met by an entry channel. That second
half is not optional: `star_align.gtf` arrives from `params.gtf` and has no incoming edge, and a
check that looked only at edges drew a hollow *unmet* dot on a satisfied input — the one defect
of this kind that 3C shipped and caught.

**Per graph:** no cycles. Routing already forbids them by construction (`producers_of` excludes
the node itself); a hand-drawn graph has no such protection, which is precisely the difference
between searching and checking.

**Coded diagnostics**, in `diagnostics.yml`, `MD04xx` or wherever the next band is — never a
string composed at the call site.

## 4. Three endpoints, and the AI is a client of them

```
POST /api/pipeline/validate   a graph  -> Verdict          is what I drew legal
POST /api/pipeline/resolve    a goal   -> BuiltPipeline    what would Mendel build
POST /api/pipeline/emit       a graph  -> Nextflow         give me the files
```

**The AI is not a special path.** `CLAUDE.md` already says the AI is the engine's primary
operator and that `pipeline.yml` is the save file it *"sets down, picks up, tunes and re-emits"*.
This makes that literally true: a model drafting a pipeline calls the same three verbs a person's
clicks call, and neither can do anything the other cannot.

**That is also the strongest argument for validation being a server verb.** A check implemented
in the browser would be a check the AI cannot run, and then there would be two answers to *is this
legal*.

## 5. Two pipelines on one canvas

The screen shows **what you drew** and **what Mendel resolves**, and where they differ.

- adopt the resolver's choice for a step
- keep yours, which is an override and gets a `DecisionRecord` like every other (invariant 9)
- see *why* they differ — a tier-3 rule fired on a measurement you did not account for

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

## 7. What already works and should not be rebuilt

Verified during 3C: the canvas, the deterministic layout, the ports, the tier rails, the
provenance bar, the settings card, the rail. **They render a pipeline, and a hand-built pipeline
is still a pipeline.** What has to change is where that pipeline comes from and whether the screen
can write one back.

## 8. Open questions, none of them decided

- **Where does a hand-built pipeline live between edits?** `pipeline.yml` is the save file and
  nothing in the API stores one. A path, a database row, or the browser — the first is most
  consistent with everything else and the least like a web application.
- **Does drag-to-connect come before or after validation?** Validation is useful without it (you
  can already see unmet inputs); dragging without validation is a way to draw something wrong
  faster.
- **What does the AI actually send?** A whole pipeline each time, or operations? Whole-artifact
  is simpler and matches `pipeline.yml`; operations make a diff cheap.
- **Does `validate` refuse or report?** Refusing is a boundary; reporting lets a person see three
  problems rather than the first one. The forge's `verify` ladder reports, and that is probably
  the precedent.

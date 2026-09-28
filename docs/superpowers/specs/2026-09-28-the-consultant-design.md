# The consultant: gathering what an analysis needs, then building it with the researcher

**Date:** 2026-09-28 · **Status:** design, awaiting the operator's review
**Phase:** Living Pipeline Plan 2 (the walk), round 1
**Issues:** #105 (no place for *paired-end*), #114 (nobody asked for the genome), #113 (*New
pipeline*), #117 (settings, deferred), #78 (contracts have no description), #71 (protection
profiles)
**The protocol itself:** [`docs/design/authoring-protocol.md`](../../design/authoring-protocol.md),
the living diagram and its rules. This spec says what to build so the code behaves that way; the
protocol page says what the behaviour is. Where the two disagree, the protocol page wins and this
spec is corrected.

---

## 1. Why

The first browser walk with a real model (`gemma3:12b`, local) could not finish scenario 1,
*paired-end RNA-seq to gene counts*, for two reasons that are one design fault:

- **The model was asked to fill `goal.have` and had nowhere legal to put what it knew.** *Paired-end*
  is a measurement in this registry, not a state, so the model wrote the nearest legal state
  (`deduplicated`) and repeated it after being corrected (#105).
- **Nobody asked for the genome.** The goal was confirmed with reads only, and resolving died on
  `nothing produces genome.fasta` (#114).

**The engine already knew both answers.** It can walk back from the want to every input and every
measurement the pipeline will read, which is what the product claims to do: *build what it can
prove, and hand out what is left as typed questions.* The opening did not use it. It asked a
model to guess the whole `have` at once.

And stage ④ was written for a pipeline engineer (process names, tier numbers, a button per step)
when the person is a researcher who knows their experiment and not necessarily what a BAM is.

## 2. What success looks like

With `gemma3:12b` locally and the stack from `make dev`:

1. *Paired-end RNA-seq to gene counts*, plus one uploaded FASTQ pair, produces a goal holding
   reads, a genome and an annotation (asked for, answered) with `paired` and `read_length`
   **measured**, and no invented state.
2. Without an upload, the same request asks about the genome, the annotation, read length and
   pairing. *Not sure* asks for a file, and *can't share it* leaves a measurement **open**. An
   open `read_length` makes the aligner choice a **tier-4** question in the build, not a failure.
3. *I don't have a genome* is an honest stop naming what is missing.
4. The build opens with the plan in stages, asks the pacing question, stops only at tier 4 (or at
   every step, going through together), explains any step from its sources, and ends with a
   wrap-up.
5. The diagram in `authoring-protocol.md` is generated from code, and a test fails if the running
   state machine and the diagram disagree.

**Scenario 1 of the walk is the acceptance test.** The unit and route tests below are necessary
and not sufficient: the walk has already shown that a green suite says nothing about a model.

## 3. Decisions (operator, 2026-09-28)

| Decision | Recorded in |
|---|---|
| The engine decides what is missing, and a model never judges sufficiency | protocol rule 1 |
| **Nothing is guessed.** A fact comes from the person or a file; *don't know* asks for a file | rule 5 |
| An unknown **measurement** stays open and falls to **tier 4** where it is read | rule 6 |
| A missing **input** cannot be left open: *have it, won't upload* → person-said; *don't have it* → stop | rule 7 |
| A rule may decide on a model-read fact: **tier 3**, premise marked *read by AI* | tier table |
| Characterisers: an inspector per type where one exists, the AI where not, never a refusal | rule 4 |
| Protection level **0** for the MVP: samples upload and a model may read them | *Loosenings* |
| Invariant 15 does not hold at level 0; invariant 3 gains a fourth point, characterisation | *Loosenings* |
| The typed payload stays: every agent answers in a declared shape | *Loosenings* |
| The build is a consultant: overview, pacing asked at the start, stops by tier, wrap-up | rules 8–14 |
| Pacing is **asked, not a setting**; the settings menu is deferred | #117 |
| The protocol becomes code that generates its own diagram | *The protocol is code* |

## 4. Scope

**In the MVP**
- the protocol object, the generated diagram, and the state-machine test;
- the `gathering` phase and the gap engine;
- gap questions in the conversation, and reading answers back into typed facts;
- sample upload at level 0, and a FASTQ inspector;
- the characteriser for types without an inspector;
- the consultant build: plan, pacing, four things per step, tier-paced stops, wrap-up;
- explanations only from sources, with a starter set of descriptions for the RNA-seq spine's
  tools (the rest of #78 through the forge later).

**Not in the MVP**
- a settings menu (#117);
- protection levels above 0 as working modes. The variable exists and every crossing asks it, but
  only level 0's row is implemented;
- inspectors beyond FASTQ;
- per-sample measurements that differ between files (asked about, not modelled; open question);
- deleting the manual builder.

## 5. The protocol as code

`packages/mendel-api/src/mendel_api/authoring/protocol.py` holds one frozen, declarative object:

```python
class Actor(StrEnum):   YOU, ENGINE, AI, SAFETY
class Tier(StrEnum):    NONE, T12, T3, T4          # the border
class Stage(...):       id, title                   # ① … ④
class Node(...):        id, stage, actor, label, tier=NONE, shape
class Edge(...):        source, target, label, event: st.Event | None
PROTOCOL = Protocol(stages=..., nodes=..., edges=...)
```

- **`to_mermaid(PROTOCOL) -> str`** renders the diagram: fill by actor, border by tier, and a key
  generated from the enums, so a new actor cannot appear without a key entry.
- **`tools/generate_protocol_doc.py`** writes it between `<!-- protocol:begin -->` and
  `<!-- protocol:end -->` in `authoring-protocol.md`. `make docs` runs it with `--check` and fails
  when the page is stale, like `diagnostics.md`.
- **`test_the_state_machine_is_the_protocol`**: every `(phase, event) → phase` in
  `state.TRANSITIONS` is an edge carrying that event between the nodes that stand for those
  phases, and every event-carrying edge is a transition. Both directions are asserted, and the
  collection is asserted non-empty first (a loop is not an assertion).
- The rules' prose stays hand-written in the protocol page. The object holds the structure, not
  the argument.

## 6. Stage ②: gathering

### Phases

`understanding → gathering → goal_review → resolving → building → complete`, with `failed` as
today. New transitions: `(UNDERSTANDING, WANT_RETURNED) → GATHERING`,
`(GATHERING, FACT_ADDED) → GATHERING`, `(GATHERING, NOTHING_MISSING) → GOAL_REVIEW`,
`(GATHERING, INPUT_UNAVAILABLE) → STOPPED`. `stopped` is a new terminal phase that is not a failure:
the protocol ended honestly. Every one of these is an edge in `PROTOCOL`.

### The goal call becomes a want call

`builder.goal.v3` asks for the **want only**: the target type ids, any constraint the person
stated, and a one-sentence summary. It no longer asks for `have`, which is what produced #105.
`v2` joins `prompts.RETIRED`. The reply shape `WantUnderstanding` has `want`, `constraints`,
`summary`, and `questions` (for an ambiguous want).

### The gap engine

`services/gaps.py`, deterministic, no model:

```python
def gaps(want, facts: list[Fact], stack) -> list[Gap]
```

It walks back from `want` through the registry the way the router does, and collects:
- **inputs**: every leaf type the walk reaches that nothing produces and no fact covers
  (`genome.fasta`, `annotation.gtf`, `fastq.reads`);
- **measurements**: every measurement a rule's `when` or a contract's `meta` reads on the reached
  contracts (`read_length`, `strandedness`, `paired`), not already known or left open.

Gaps are ordered **inputs first, then measurements**, each in `dag-core` rank order, so the
questions follow the pipeline's shape. The walk has to be a *superset* of what the resolver will
route: a gap asked for and then not needed costs a question, and a gap missed costs the build.

### Facts

```python
class FactSource(StrEnum): MEASURED, MODEL_READ, PERSON_SAID, OPEN
class Fact(_Shape):  kind: input | measurement;  type_id | measurement;  value | None;
                     states: list[State];  source: FactSource;  sample: SampleId | None
```

Facts live on the session (a JSON column, like `goal`) and are folded into the `Goal` when the
card is confirmed: inputs into `goal.have`, measurements into `goal.profile` with the source
carried into `Measured.source`. `PERSON_SAID` maps to `ValueSource.HUMAN` and `MODEL_READ` to
`ValueSource.MODEL`, both of which exist. `MEASURED` has no spelling yet: `ValueSource` gains
`INSPECTED`, with `Measured.by` naming the inspector (a `comeni-core` feature). **An `OPEN` measurement is omitted from the profile**, which is what makes a rule not
match and the decision fall to tier 4, with no new mechanism.

### Gap questions

The engine emits one `Question` block per gap, with ids it mints and closed options:
- an input: *I have it, and will upload it* / *I have it, but can't share it* / *I don't have one*;
- a measurement: its declared values where closed (`paired`: yes / no), a typed field where open
  (`read_length`), plus *not sure* and *can't share it*.

**The AI's only job here** is `builder.gap.v1`: turn the engine's question into one plain sentence
for this person, and read a free-text reply back into one of that question's option ids or a typed
value (admitted against the question, exactly as `chose` is today, MI0205). Clicking an option
needs no model call at all.

### Samples and inspectors

- `POST /api/pipeline/authoring/{id}/samples` (multipart): stored under
  `workspace/samples/<session>/<sample id>`, **capped at 4 MB, only the head kept**, deleted with
  the session. At level 0 this is allowed; the route asks the protection level and refuses above 0
  with a declared code.
- `services/inspect/`: `INSPECTORS: dict[TypeId, Inspector]`, with a `fastq` inspector first.
  Bytes in, facts out: `fastq.reads` (gzip or not), `paired` (from `_R1`/`_R2`, `_1`/`_2`, or two
  files with matching read names), `read_length` (the modal length of the first N records), and
  quality encoding. Pure over bytes, unit-tested on fixture heads.
- **Which types have an inspector is exposed** by the vocabulary endpoint and shown on the card,
  so the lost flexibility is visible (rule 4). It lives in code for the MVP; moving it into the
  registry as declared data is later, and recorded here as a deviation.

### The characteriser: the fourth AI point

- `AiPoint.CHARACTERISE` joins the enum, and `tests/artifact/test_ai_provenance.py` is updated to
  say so out loud, which is what that test exists for.
- **A sixth door**, `DoorPath.PIPELINE`, payload `CharacteriseRequest`: the sample head (a new
  `Mark.SAMPLE` field, the first field that may hold data from a person's files), the file's
  declared-extension type candidates, and the closed vocabulary. `FREE_TEXT_FIELDS` and the egress
  guard gain it explicitly. At level 0 the door is open; above it the door refuses before
  composing.
- `builder.characterise.v1`: *which declared type is this, and which declared facts can you read
  from it?* The reply is `CharacteriseReply: type_id, states, measurements`, every id admitted
  against the vocabulary, and every fact marked `MODEL_READ`.

### The protection level

`ProtectionLevel` is a setting on the installation (`COMENI_PROTECTION_LEVEL`, default **0** for
the MVP) carried on every session. Upload, characterisation and door 6 each call
`level.allows(Crossing.X)`. Only level 0's row is implemented; the others refuse with a declared
code, not silently. This closes nothing in #71, and makes it a set of rows to fill in.

## 7. Stage ③: the goal card

Every fact is shown with its source: *measured* (from `sample.fastq`), *read by AI*, *you said*,
or *left open, you'll choose during the build*. Open measurements are listed under their own
heading, so what will turn into tier-4 questions is visible before confirming. Everything built in
round 1 (states per input, *before your edit*) carries over.

## 8. Stage ④: the consultant build

### Plan and pacing

After the blueprint resolves, the engine composes an **overview** from it: steps grouped into
stages by role (*clean reads*, *align*, *count*, *report*), each stage with how many steps need
the person. A new block, `plan_overview`, is phrased by the AI (`builder.consult.v1`) from that
typed structure. Then the **pacing question** is posed as a `Question` with two options: *go
through it together* / *set it up, stop only where you need me*. The answer sets
`session.pacing`, which replaces the Build/Spawn `mode`.

**One consequence to confirm in review:** under rules 5 and 10, **tier 4 always stops for the
person** in both paces. Today's Spawn lets a model answer tier 4 (door 2). The MVP consultant does
not; door 2 stays declared and unused until a setting (#117) asks for it.

### Each step

A step block carries **four things**, all from the engine:

| Thing | Source |
|---|---|
| what it does | the tool's declared description (a new `description:` on the contract or its role, #78) |
| why it's here | the tier, the rule, its citation, and the premise with its source |
| what it makes | output types, in the glossary's words |
| what to check | tier 3: the fact it rests on; tier 4: the trade-off |

The AI phrases them for the researcher in `builder.consult.v1`, **only from those fields**.

### Pacing by tier

| Tier | Stop-only-where-needed | Together |
|---|---|---|
| 1–2 | placed at once, reason one tap away | waits for *continue* |
| 3 | placed at once, fact shown (yellow border) | waits for *continue* |
| 4 | **stops**: options with trade-offs (red border, blue fill) | stops |

The canvas animates each placement as it does today.

### Explanations from sources

*Why?*, *what if?* and *what's a BAM?* go to `builder.explain.v1`, which is handed exactly: the
step's contract description, its rule and citation, the glossary entries it touches, and the
draft's structure. The reply is `Explanation: text, cites: list[SourceId]`, **each cited id
admitted against what was handed** (the MI0205 check again). No sources yields a reply that says
so, never an answer from memory. Structural questions (*what feeds STAR?*) are answered by the
engine and only phrased by the AI.

**A starter set of descriptions** for the RNA-seq spine's tools is written by hand and approved in
`comeni-registry`. The forge drafts the rest of #78 later.

### Wrap-up

When nothing is left, a `wrap_up` block: what you'll get (output types, in words), what you need
to run it (inputs, profile, where), and who decided what (counts by tier and by source, linking to
the log).

## 9. Errors

| Situation | Behaviour |
|---|---|
| a gap reply the AI cannot map to an option | re-asks once, then shows the options to click, never a guess |
| an inspector cannot read a file | a notice with a declared code; the gap stays open, and the person may upload another |
| the characteriser's reply names an undeclared id | refused (MI0204/MI0205 family), and the gap stays open |
| a resolve still fails after gathering | MI0207 as today. It now means the gap engine missed something, and is a bug to file |
| upload above level 0 | refused with a declared code naming the level |

## 10. Testing

- **Protocol:** generated diagram fresh (`make docs`); state machine ⇔ protocol, both directions.
- **Gap engine:** the RNA-seq want with empty facts yields exactly reads, genome, annotation,
  read length, pairing and strandedness, in rank order. Each fact removes its gap. An `OPEN`
  measurement is not asked twice.
- **Inspector:** fixture heads for paired and single, gzipped and plain, 50 bp and 150 bp.
- **Characteriser, gap and consult prompts:** recorded transports only (no live model in tests,
  as `test_no_live_model.py` enforces), and admission refusing ids never offered.
- **Tier 4 from an open fact:** an open `read_length` makes the aligner decision tier 4, and a
  measured one makes it tier 3 with the premise's source recorded in `pipeline.yml`.
- **Egress:** door 6 declared, `Mark.SAMPLE` in `FREE_TEXT_FIELDS`, and the guard watched failing
  with the field unmarked.
- **The walk:** scenario 1 with and without an upload, then round 2 of Plan 2.

## 11. Build order

Each phase leaves the loop working and is walked before the next begins.

1. **Protocol object, generated diagram, state-machine test.** No behaviour change; the current
   protocol is encoded first, then edited as each later phase lands.
2. **Gathering without files:** want-only goal prompt, gap engine, gap questions, facts, the card.
   Scenario 1 by answering questions.
3. **Samples and the FASTQ inspector, at level 0.** Scenario 1 by uploading.
4. **The characteriser, door 6, the fourth AI point.**
5. **The consultant build:** plan, pacing, four things per step, tier pacing, wrap-up, starter
   descriptions, explanations from sources.

Phases 1–3 finish scenario 1; 4 and 5 are what make it a consultant.

## 12. Open questions

- **#113:** should *New pipeline* open the consultant (a sentence first), with *draw it yourself*
  as the way to the manual canvas? The recommendation is yes; it is the operator's call.
- A fact that differs between samples (two read lengths): ask which is right, or a per-sample
  measurement?
- Sample retention beyond the session: none for the MVP. Worth a line in the protection table
  before level 1.
- `comeni-core` version: MI0207, `AiPoint.CHARACTERISE` and the new door are features, and door 6
  changes an invariant. The bump is judged at release time (`docs/guides/releasing.md`).

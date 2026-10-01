# The consultant: gathering what an analysis needs, then building it with the researcher

**Date:** 2026-09-28 · **Status:** design, awaiting the operator's review
**Where this sits:** Task 14 of the living pipeline (Living Pipeline Plan 2, the walk), step 14.7.
This spec is substeps **14.7.2–14.7.8**; 14.7.1 was round 1 of the walk. Renumbered on 2026-09-28: 14.7.4 (the consultant's words, fast and cheap) and 14.7.5 (the settings menu) were inserted, and samples, the characteriser, the consultant build and the nine-scenario walk became 14.7.6–14.7.9. On 2026-10-01 a tuning substep became 14.7.9 (#210), and the nine-scenario walk 14.7.10.
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
5. The diagram of the protocol is generated from code, and the running state machine is derived
   from the same object, so the two cannot disagree. What is designed and not yet built is drawn
   dashed.

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
| A model may read the person's words into a **candidate** that pre-fills a gap; only the person's click makes it a fact (#170, #171) | §6 |
| An absent premise on a declared rule is **tier 4**, never a fall-through to priority; the card asks for the fact first (#174) | §8 |
| The state machine is **derived** from the protocol object; retry uses return edges and is refused outside them; planned parts live in the object, drawn dashed | §5 of this spec |

## 4. Scope

**In the MVP**
- the protocol object, the state machine derived from it, and the generated diagram;
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

Brainstormed again before building (operator, 2026-09-28): **the protocol object is the only
definition, and the state machine is derived from it.** The designed protocol lives in the same
object, marked planned.

`packages/mendel-api/src/mendel_api/authoring/protocol.py` holds one frozen, declarative object:

```python
class Actor(StrEnum):   YOU, ENGINE, AI, SAFETY, STOP      # the fill
class Border(StrEnum):  NONE, TIER12, TIER3, TIER4        # the border
class Shape(StrEnum):   BOX, ROUND, CHOICE, GATE
class Stage(...):       id, title
class Node(...):        id, stage, actor, label, phase: Phase | None, border, shape, built
class Edge(...):        source, target, label, event: Event | None, returns: bool, built
PROTOCOL = Protocol(stages=..., nodes=..., edges=...)
```

### One definition: the machine is derived

- **`state.TRANSITIONS` is computed**, not written: every *built* edge that carries an event
  contributes `(source.phase, event) → target.phase`. A step inside a phase is an edge with no
  event and contributes nothing.
- **`state.RETRY_TARGETS` is computed** from the built edges marked `returns`: the phases a retry
  out of `failed` may resume. Today that is `understanding` and `resolving`.
- **`advance()` refuses a retry into a phase outside `RETRY_TARGETS`.** A **tightening**: before
  this, any recorded `failed_from` was accepted. Nothing uses the hole it closes.
- Rejected: keeping `TRANSITIONS` hand-written and testing it against the object (two edits per
  change); deriving and also keeping a frozen snapshot (a third file per change); splitting
  `failed` per stage so retry is an ordinary edge (a migration, and a new failed phase per stage).

### Checked when it loads

`PROTOCOL` refuses to construct, so the module refuses to import, when:

- an edge names a node that is not declared, or a node names a stage that is not declared;
- a **built** node has no `phase`, or a **built** edge touches a planned node;
- two built edges give the same `(phase, event)` different targets (a return edge is exempt,
  since its target is chosen by `failed_from`);
- a `returns` edge does not leave a node in `failed`.

Because a drawing mistake is now a behaviour mistake, these checks and the existing `advance()`
tests are what stand between them.

### Designed and built, in one object

- **Every node and edge carries `built`.** 14.7.2 encodes today's loop as built, and the designed
  consultant (gathering, gaps, uploads, the characteriser, the paced build, the stops), transcribed
  from the hand-drawn diagram, as **planned**. A planned node may have `phase=None`, since
  `gathering` and `stopped` do not exist until 14.7.3.
- **Each later substep flips `built`** on its part and gives its nodes their phases. The picture
  turns solid as the work lands; there is never a second diagram to keep in step.
- Rejected: a generated *as built* diagram beside the hand-drawn design (two pictures, and the
  design still hand-drawn); generating only what is built (the design disappears while it is
  being built).

### The diagram

- **`to_mermaid(PROTOCOL) -> str`** renders it: fill by actor, border by tier, planned parts
  **dashed and grey**, and a key generated from the enums plus *dashed · designed, not built*, so
  nothing can be drawn without the key saying what it means.
- **`tools/generate_protocol_doc.py`** writes a **whole generated file**,
  `docs/design/authoring-protocol-diagram.md`, and the hand-written protocol page links to it in
  place of its hand-drawn diagram. `make docs` runs it with `--check` and fails when it is stale.
  Not a block spliced between markers: `generate_diagnostics_doc.py` records why this repository
  stopped doing that (*`--check` could only ever see the block*).
- The rules' prose stays hand-written in the protocol page. The object holds the structure, not
  the argument.

## 6. Stage ②: gathering

### Phases

`understanding → gathering → goal_review → resolving → building → complete`, with `failed` as
today. New transitions: `(UNDERSTANDING, WANT_RETURNED) → GATHERING`,
`(GATHERING, FACT_ADDED) → GATHERING`, `(GATHERING, NOTHING_MISSING) → GOAL_REVIEW`,
`(GATHERING, INPUT_UNAVAILABLE) → STOPPED`. `stopped` is a new terminal phase that is not a failure:
the protocol ended honestly. Every one of these is an edge in `PROTOCOL`, planned since 14.7.2;
14.7.3 adds the phases and flips them to built, and `TRANSITIONS` follows by derivation.

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
carried into `Measured.source`. `PERSON_SAID` maps to `ValueSource.GOAL` (*asserted in the goal*,
which is what it is; `HUMAN` means answering a flagged ambiguity **after** resolution, and is not
this), and `MODEL_READ` to `ValueSource.MODEL`. `MEASURED` has no spelling yet: `ValueSource` gains
`INSPECTED`, with `Measured.by` naming the inspector (a `comeni-core` feature, in 14.7.6).

**A profile with mixed sources needs one new constructor.** `MeasurementRegistry.profile()` stamps
one source on every entry, and `tests/guards/test_construction.py` forbids building a
`DataProfile` anywhere else. So `comeni-core` gains `MeasurementRegistry.profile_of(entries)`,
which validates each entry the same way and carries each one's own source. **An `OPEN` measurement is omitted from the profile**, which is what makes a rule not
match and the decision fall to tier 4, with no new mechanism.

### Gap questions

Each gap is offered as a **proposal of kind `gap`**, not a bare `Question` block. A `Question`
is display-only today, and a proposal is what the page already knows how to answer with a click
(`decide` with an option id), with no model call. Its block is a `Question` carrying ids the
engine mints and closed options:
- an input: *I have it, and will upload it* / *I have it, but can't share it* / *I don't have one*;
- a measurement: its declared values where closed (`paired`: yes / no), a typed field where open
  (`read_length`), plus *not sure* and *can't share it*.

A typed value (`read_length: 150`) travels on `DecideProposal.value`, a new optional field held
to the measurement's declaration by `MeasurementRegistry.check`.

**The AI's only job here** is `builder.gap.v1`: turn the engine's question into one plain sentence
for this person, and read a free-text reply back into one of that question's option ids or a typed
value (admitted against the question, exactly as `chose` is today, MI0205). Clicking an option
needs no model call at all.

### The model reads, the person confirms (#170, #171)

**Found by the 14.7.3 walk.** The person wrote *paired-end RNA-seq to gene counts* and was then
asked *was the library paired-end?* (#170): v3 drops what the person states, so a model cannot
guess. And a typed reply read by `builder.gap.v1` was recorded *you said* while the log said
*read by AI* (#171). Decided with the operator (2026-09-28): **one rule for both — a model may
read the person's words; only the person's click makes a fact.**

**Stated facts become candidates** (`builder.goal.v4`; v3 joins `RETIRED`). The want call may
return `stated`: each an input the person said they have (a declared type id) or a measurement
they stated (a declared id and a value its declaration allows). Admission holds each to the
registry exactly as `want` is held (MI0204, `MeasurementRegistry.check`); a candidate that fails
is dropped from `stated` and never refuses the call, since the want is still good. Candidates
are stored on the session beside the want, never in `facts`.

**A candidate pre-fills its gap; it never answers it.** When the gap engine offers a gap that
has a candidate, the question block marks the matching option `recommended` with a note (*you
mentioned it*), or, for a typed value, carries the value to pre-fill the field. The card draws
the suggestion; the person's click is `answer_gap`, settled by the person, fact source
`PERSON_SAID`. The other options stay: *No*, *not sure*, *can't share it*.

**A typed reply is read into a candidate the same way.** `read_gap_reply` no longer calls
`answer_gap`: an admitted reading pre-fills the pending gap (*I read that as **Yes** — confirm
above*), and `unsure` re-offers it as today. A reading that names a value the declaration
refuses is shown as a notice (MI0208) and pre-fills nothing. The model call stays recorded
(`ai_invocation`), so the log can still say the reading was a model's; the fact is the person's.

**Spawn** confirms nothing on the person's behalf: a pre-filled gap waits for the click, as any
gap does.

**What this changes in the protocol object:** `read_goal` gains a planned-now-built edge to
`next_gap` carrying candidates (no event); `ask → reply` is unchanged. The loosening, recorded:
v3's *do not write inputs, states or measurements* becomes *you may report what was stated, as a
candidate*; rule 5 (*nothing is guessed*) is unchanged, because a candidate is not a fact.

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

> **Knowingly optimistic.** Stages ② and ③ answer defects the walk found; this stage was
> designed before any model walked it. It is the first draft to be tested, and substep 14.7.8
> should expect to be revised by what the walk finds, more than the substeps before it. Build the smallest version that can be walked, not the whole section at once.

### Plan and pacing

After the blueprint resolves, the engine composes an **overview** from it: steps grouped into
stages by role (*clean reads*, *align*, *count*, *report*), each stage with how many steps need
the person. A new block, `plan_overview`, is phrased by the AI (`builder.consult.v1`) from that
typed structure. Then the **pacing question** is posed as a `Question` with two options: *go
through it together* / *set it up, stop only where you need me*. The answer sets
`session.pacing`, which replaces the Build/Spawn `mode`.

**Pacing is a setting since 14.7.5** (`comeni_core.settings.catalogue.PACING`, declared
`Designed` until this substep). 14.7.8 removes its `unavailable=`, reads
`installation().get(PACING)` at the start of a build, asks the question only when it is `ask`,
and flips `test_pacing_says_designed_even_when_env_and_a_stored_value_are_set` to assert the
stored value wins. `TIER4_ANSWERS` stays designed.

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

### An open premise at build time (#174)

**Found by the 14.7.3 walk.** With read length answered *can't share it*, `star_align` was placed
at **tier 2**, *registry priority 10, over hisat2*. The alignment rule (`read_length >= 70` → STAR,
`< 70` → HISAT2) had no row it could evaluate, and the router fell through to priority as if no
rule existed. The person's deferred decision was taken for them, silently. Decided with the
operator (2026-09-28): **A, tightened, with a fact-first card.**

**The rule.** Where a declared decision chooses the implementation for a role and **no row can
be evaluated because a premise is absent**, the choice is **tier 4**. Invariant 4 (*a tier-3 rule
miss demotes to tier 4*) read as covering an absent premise; protocol rule 6 made true. It holds
for every path to a goal (gathering, the manual builder, the CLI): a goal that never states a
read length gets the question too, which is the flag the invariants promise.

**What the tier-4 question holds** (the probe on 2026-09-28 is where each of these came from):
- **Only the candidates the rule chooses between**: the contracts its rows' `then` name, among
  the candidates at this site. Tying every candidate put minimap2 in the aligner question.
- **Provisionally placed by registry priority**, flagged tier 4 and review required, as today's
  tie is. The flag-only resolver's id order would have swapped the default pipeline to HISAT2.
- **`why_open` names the rule and the missing premise** (*the alignment rule reads read_length,
  and nobody knows it*); its evidence is the rule's rows with their `because` and `cite`.
- **A recorded human answer still wins on replay** (`ReplayResolver`): the probe showed a backed
  override losing its human source.

**The fact-first card** (stage ④, built with 14.7.8). The step card leads with the fact the rule
reads, not the tools: *your read length decides the aligner: 70 bp or longer, STAR; shorter,
HISAT2 (Dobin et al. 2013)*. What it offers follows why the fact is open:

| The fact is open because | The card offers |
|---|---|
| *not sure* | upload a file (the inspector measures it), type it, or choose a tool |
| *can't share it* | type it, or choose a tool; **no upload**, the person already declined |
| nobody asked (a CLI or manual goal) | type it, or choose a tool |

Answering the fact adds it to the session's facts and re-resolves the step: **tier 3**, the
premise marked *measured* or *you said*. Choosing a tool keeps **tier 4**, *you chose*. Until
14.7.8, the card shows the rule's rows as the reason and the two tools as options.

**Tests that change on purpose** (the probe's fallout, 5 beyond the base failures):
`test_a_priority_resolved_choice_is_convention` and `test_a128_…` assert a priority win on a
role a rule decides, and move to a role no rule decides; `test_a125_…` and
`test_a_presence_absent_rule_removes_the_step_…` are checked against the candidate restriction
above; `test_a_replayed_override_backed_by_its_record_is_still_honoured` must pass unchanged.
Touches `router.py`: `make verify`.

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

- **Protocol:** each load-time check watched refusing a bad object; the derived `TRANSITIONS`
  equals today's hand-written table (captured before it is deleted); a retry into `building` is
  refused and into `resolving` accepted; the diagram is deterministic, keys every actor, border
  and *planned*, and draws planned parts dashed; the generated file is fresh (`make docs`).
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

## 11. Build order: substeps 14.7.2–14.7.9

Each substep leaves the loop working and is walked before the next begins.

- **14.7.2 Protocol object, derived state machine, generated diagram.** One behaviour change, the
   retry tightening. Today's loop is encoded as built and the design as planned; each later substep
   flips its part to built.
- **14.7.3 Gathering without files:** want-only goal prompt, gap engine, gap questions, facts, the card.
   Scenario 1 by answering questions. **Plus stated and typed facts as confirmed candidates**
   (#170, #171; §6), **and the resolver half of #174**: an absent premise on a
   declared rule is tier 4 (§8, *An open premise at build time*).
- **14.7.4 The consultant's words, fast and cheap:** record what the model answered; prompts as a
   fixed system message plus a dynamic one, `keep_alive`, prefix reuse; then the consultant's prose
   (#167, #176) with prefetching. Spec amended when its brainstorm is written up.
- **14.7.5 The settings menu:** pacing, protection level, a model per purpose, lane; then which
   local models fit an 8 GiB card.
- **14.7.6 Samples and the FASTQ inspector, at level 0.** Scenario 1 by uploading. *Not sure*
   in gathering asks for the file, closing the protocol's planned upload branch.
- **14.7.7 The characteriser, door 6, the fourth AI point.**
- **14.7.8 The consultant build:** plan, pacing, four things per step, tier pacing, wrap-up, starter
   descriptions, explanations from sources, and the fact-first card for an open premise (#174).

14.7.2–14.7.6 finish scenario 1; 14.7.7 and 14.7.8 are what make it a consultant. After them,
**14.7.9** walks all nine scenarios again, round by round.

## 12. Open questions

- **#113:** should *New pipeline* open the consultant (a sentence first), with *draw it yourself*
  as the way to the manual canvas? The recommendation is yes; it is the operator's call.
- A fact that differs between samples (two read lengths): ask which is right, or a per-sample
  measurement?
- Sample retention beyond the session: none for the MVP. Worth a line in the protection table
  before level 1.
- `comeni-core` version: MI0207, `AiPoint.CHARACTERISE` and the new door are features, and door 6
  changes an invariant. The bump is judged at release time (`docs/guides/releasing.md`).

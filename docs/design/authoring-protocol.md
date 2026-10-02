# The authoring protocol — from a sentence to a goal that builds

**A living document.** It grows as the walk finds what the protocol gets wrong, and every change
names the issue that caused it. It describes the *protocol* (who asks what, in what order, and
what is allowed to cross) rather than the code. The code follows it, and where the two disagree,
this page is what gets argued about.

Started 2026-09-28 from #105 and #114, during Living Pipeline Plan 2.

---

## The loop

**The diagram is [generated from the code](diagrams/authoring-protocol.md)**: solid is built,
dashed is designed and not built yet. The same object is where the running state machine comes
from, so the picture and the machine cannot disagree. Detailed diagrams, beginning with
[Inspecting a sample](diagrams/inspecting-a-sample.md), are listed in
[the diagrams folder](diagrams/README.md).

**Fill is who acts, border is the tier**, and every colour is named in the diagram's key. Red
*fill* means only one thing (a stop); a tier-4 choice is the person's, so it is blue with a red
*border*. In the rules below, *engine* means
deterministic code, *AI* means a model answering in a typed shape, and the safety level is the
protection profile. The facts' labels in the diagram (*you said*, *measured*, *read by AI*) are
`PERSON-SAID`, `MEASURED` and `MODEL-READ` below.

## The rules the diagram encodes

1. **The engine decides what is missing, never a model.** The gap list is computed: every leaf
   **input** the resolver reaches walking back from the want, and every **measurement** a rule
   or a module's `meta` reads on the way. A model judging sufficiency would sometimes say *yes*
   with the genome missing, which is what #114 was.
2. **A model phrases questions and reads answers; it never decides what is asked.** The gaps come
   from the engine, and the agent turns each into words and the reply back into a typed fact.
3. **Every fact carries its source:** `MEASURED` (an inspector), `MODEL-READ` (the characteriser),
   `PERSON-SAID` (an answer). The goal card shows all three.
4. **No data type is refused for lacking an inspector.** It gets the characteriser, and a weaker
   label. Which types have an inspector is declared, so the lost flexibility is visible; the
   vocabulary lists, for every measurement, what measures it and where that runs.
5. **Nothing is guessed. A fact comes from the person or from a file** (decided 2026-09-28).
   *Don't know* is always answered by asking for a file, never by a model proposing a likely
   value. There is no setting for this in the MVP.
6. **An unknown measurement stays open, and the tiers carry it** (decided 2026-09-28). It is not a
   failure: a rule that reads an open fact does not match, so the decision falls to **tier 4**,
   always flagged, answered by a person when the build reaches it (invariants 4 and 6, unchanged).
   The loop never blocks on a measurement.
7. **A missing input is different, because nothing can be left open.** No genome means nothing
   aligns. *I have it but won't upload it* records it as `PERSON-SAID`; *I don't have one* is an
   honest stop naming the input, never a pipeline built around the gap.

## The build, as a consultant (stage ④)

> **Provisional, and knowingly optimistic** (operator, 2026-09-28). Stage ② came from what the
> walk actually broke; stage ④ was designed before a model has walked it. Expect it to expand
> and change more than any other part of this page, and treat every rule below as a first guess
> to be tested, not a settled one.

The person is a researcher, not a pipeline engineer. They know their experiment and not
necessarily what a BAM is. Stage ④ is written for them.

8. **Overview before detail.** The engine resolves the whole pipeline before offering anything,
   so the build opens with its shape **in stages, not tools**: *clean the reads, line them up
   against the genome, count reads per gene, a quality report. Four stages; two need you.*
9. **Then the pacing question, asked, not set** (decided 2026-09-28): *go through it together, or
   set it up and stop only where I need you?* A settings menu for this is deferred (#117), so
   the MVP gets no extra UI.
10. **Stops are paced by tier.** Tiers 1–2 are placed with their reason one tap away. Tier 3 is
    placed with the fact it rests on shown (yellow border). **Tier 4 always stops** (red border, the
    person's own blue) and is posed as a
    choice with trade-offs in biology terms. Going through together, every step waits for
    *continue*.
11. **Every step carries four things:** what it does, why it is here, what it makes, and what to
    check. The engine supplies the facts (tier, rule, citation, inputs and outputs), and the AI
    only puts them in the researcher's words.
12. **The AI explains only from sources it is handed**: the tool's declared description, the rule's
    citation, a glossary entry. It shows the source, and it says *I don't have a source for that*
    rather than answering from memory. That needs declared descriptions per tool or role (#78):
    the forge drafts them and a person approves (invariant 2, unchanged).
13. **Ask anything, any time.** *Why? What if? What's a BAM?* A structural question (*what feeds
    what*) is answered by the engine; the AI phrases it.
14. **It ends with a wrap-up**: what you'll get, what you need to run it, and who decided what.

## How a fact's source reaches the tiers

The four tiers are unchanged. What this protocol adds is **where the premise came from**, which
the tier-3 colour already asks a reader to check.

| The fact a rule reads | Tier of the decision | What the reader sees |
|---|---|---|
| `MEASURED`: an inspector read the file | 3, data-profiled | yellow border: check the premise (a measurement) |
| `PERSON-SAID`: the person stated it | 3, data-profiled | yellow border, premise marked *asserted* |
| `MODEL-READ`: the characteriser read it | 3, data-profiled | yellow border, premise marked *read by AI* (decided 2026-09-28) |
| open: nobody knows | **4**, ambiguous | red border: always flagged, a person answers |
| no rule reads it | 1 or 2 as today | — |

## Where each measurer runs

Every measurer declares where it runs (`runs:`), so moving one is a change to that field and a
runner, never a redesign. A protection level can refuse anything that runs on this server.

| Measurer | Reads | Runs on | What crosses | Allowed at |
|---|---|---|---|---|
| **Inspector** (a format and its measures) | the first 4 MB of one uploaded sample, a file or a pair | **this server**, in its own process, with time, memory and size limits | the sample's head reaches this server, and only the head leaves the browser; nothing is stored. The facts go into the goal | level 0 only |
| **Profiler** (a tool used to measure) | all the data | **the lab's machine**, inside the pipeline the lab runs | nothing reaches this server; the lab reads the profile back in | every level |
| **Characteriser** (a model; designed, 14.7.7) | the sample's head | a model, through a declared door | the head reaches the model | level 0 only |
| *Later:* an inspector in **the browser** | the head | the person's browser | only the facts | designed for `guarded` |

**At level 0 a sample's head reaches this server.** That is the loosening recorded below; the
other levels are written so that tightening is filling in a row. The vocabulary lists, for every
measurement, what measures it and where that runs.

## The protocol is code

The diagram is **generated, not drawn** (14.7.2). One declarative object in the code
(`mendel_api/authoring/protocol.py`) holds the stages, every node (who acts: *you*, *engine*,
*AI*, *safety*, *stop*; its tier border; its session phase) and every edge (its label and, where
it moves the session, its event). The design lives in the same object, marked planned. From it:

- **the state machine is derived**: `state.TRANSITIONS` is computed from the built edges that
  carry events, and a retry out of `failed` may resume only where a return edge is drawn
  (anything else is refused, MI0212). The object refuses to load when it is inconsistent;
- **the diagram is generated**, as a whole file, with `make docs` failing when it is stale;
- later, **the agents' wiring**: which prompt a node sends and what evidence it receives, per
  protection level, read from the same object instead of scattered through services.

**To change the protocol, edit `PROTOCOL`**, never the state machine: a substep that builds a
planned part gives its nodes phases and flips `built`.

## Protection profiles: what may cross, per node

The profile is a variable the engine carries through the whole loop. **Level 0 is the MVP**, and
everything is open. The other rows are recorded so the loop is built with the switch in place, and
tightening is filling in a row, not rewiring.

| Node | **0 (MVP)** | `guarded` (later) | `sealed` (later) |
|---|---|---|---|
| files | uploaded, stored with the session | read in the browser, facts only | none |
| characteriser receives | the sample's head | derived facts, after confirmation | not run |
| main agent receives | typed facts + the conversation | same | typed goal only |
| a fact's sample reaches a provider | yes | no | no |
| a model's reply is stored (`ai_invocation.response`) | yes, whole | decided with the level | decided with the level |

## Loosenings, recorded (2026-09-28, operator's decision)

- **Invariant 15, *Mendel does not receive patient data*, does not hold at level 0.** A sample
  file is uploaded and a model may read it. It holds at `guarded` and `sealed`. Safety is added
  as levels *after* the loop works, not before.
- **Invariant 3, *three runtime AI points*, gains a fourth: characterisation.** It is declared,
  typed and recorded like the others (an `AiPoint`, a door, a prompt file, an `ai_invocation` row).
- **A model's reply is stored, whole** (`ai_invocation.response`, #182, 2026-09-29). A reply can
  echo the person's words, so this is a new free-text store at level 0. It is stored, never sent,
  so it crosses no door; each later level decides whether replies are kept.
- **Phrasing and the read-back are prose inside the authoring AI point** (#167, #176,
  2026-09-29): `builder.ask.v1` rewrites a question and `builder.readback.v1` reads the goal
  back, both in the person's register. They author no value — the options, the facts and the
  goal stay the engine's, and anything a model hears is a suggestion the person confirms — so no
  new `AiPoint` is declared. Written here for the operator to reject.
- **The type is chosen in two calls** (#194, 2026-09-29): `builder.family.v2` picks the families
  what the person wants belongs to, from a short described list, and `builder.goal.v7` is shown
  every type of those families, whole. Both choose declared ids inside goal extraction, so no new
  `AiPoint` is declared; a request no family fits becomes a question to the person, never the
  nearest family. The family call answers whether anything fits before it lists families, and
  anything but yes is a question (#202). It narrows what the goal call is shown to whole families, never to a
  hand-picked subset. Written here for the operator to reject, and **kept only if the benchmark
  (#198) says it is worth its extra call**.
- **The typed payload stays.** Every agent answers in a declared shape. What loosens is *what the
  input may contain*, never the output's type.

## Open questions

- Where do uploaded samples live, how big may one be, and when are they deleted?
- Does a per-sample fact (`read_length` differs between two files) become a per-sample measurement
  or a question?
- #113: should *New pipeline* open this loop rather than the manual canvas?

## Changelog

| Date | Change | Why |
|---|---|---|
| 2026-09-28 | first version | #105 (no place for *paired-end*), #114 (nobody asked for the genome) |
| 2026-09-28 | stage ④ marked provisional and optimistic | operator: *during testing the protocol will probably expand and change* |
| 2026-09-28 | a rule may decide on a model-read fact: tier 3, premise marked *read by AI* | operator: *that is why we have tier 3* |
| 2026-09-28 | fill is who acts, border is the tier; every colour labelled in the key | operator: red meant both *stop* and *tier 4* |
| 2026-09-28 | stage ④ as a consultant: overview, pacing asked at the start, stops by tier, grounded explanations, wrap-up; the protocol to become code that generates this diagram | operator: *the builder is a consultant guiding a biology researcher*; settings deferred to #117 |
| 2026-09-28 | diagram reorganised into four stages with plain-language labels and a key | operator: *make the text more intuitive, and the organisation* |
| 2026-09-28 | nothing is guessed; an open measurement falls to tier 4 rather than blocking; inputs and measurements split; the tier table | operator, during the #105/#114 brainstorm: *the model can keep that param open as a tier-4 question* |
| 2026-09-28 | the diagram is generated from `protocol.py`, and the state machine is derived from the same object; the design is drawn dashed until built; a retry may resume only where a return edge is drawn | 14.7.2 (#132), second brainstorm with the operator |
| 2026-09-29 | model replies stored whole at level 0, and the session's tokens shown | 14.7.4 (#182, #191), operator's brainstorm |
| 2026-09-29 | the consultant's words: an acknowledgement, each question phrased by a model, a read-back from the composed goal, the model's constraints as suggestions | 14.7.4 (#167, #176, #186), operator's brainstorm |
| 2026-09-29 | the type chosen by family first: a *family* step before the goal call; a revision and a retry re-run both; replies enforced in shape by the model server where it can | 14.7.4 (#194), operator's brainstorm: *we aim to have hundreds if not thousands of tools* |
| 2026-09-30 | a request nothing fits asks, never fails: the family call's verdict first; a want nothing can make returns to the person | 14.7.4 (#202), operator's decision |

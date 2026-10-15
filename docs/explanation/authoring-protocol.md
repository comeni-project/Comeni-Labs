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
from, so the picture and the machine cannot disagree. It is **one diagram, with sections**: the
steps inside reading a sample are section ②a, drawn beside the questions it answers.

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
   label: a model reads its first 8 KB of text, chooses a family and then a type from the closed
   vocabulary, and may name only the declared states and measurements a line of the file states,
   quoting that line. The engine checks each quote is in the file. When the model cannot tell,
   the question stays and the person answers. A type an inspector reads goes back to that
   inspector, which measures it. Which types have an inspector is declared, so the lost
   flexibility is visible; the
   vocabulary endpoint (`GET /api/pipeline/authoring/vocabulary`, its `measurers`) lists, for
   every measurement, what measures it and where that runs.
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
8. **A sample says what it is as well as what it measures.** A sample uploaded on a measurement's
   gap is a file of some type; once a format confirms it, that type is recorded as an input the
   person has (`MEASURED`), unless they already said so, so the reads question is not asked
   after the person has shown the reads (decided 2026-10-03, issue 226).

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
    the forge drafts them and a person approves (invariant 2, unchanged). Its tone is
    `docs/explanation/product-language.md`.
13. **Ask anything, any time.** *Why? What if? What's a BAM?* A structural question (*what feeds
    what*) is answered by the engine; the AI phrases it.
14. **It ends with a wrap-up**: what you'll get, what you need to run it, and who decided what.

**As built (14.7.8.3c).** Where the rules above and the build differ, the build is
`docs/superpowers/specs/2026-10-04-the-consultant-build-design.md` §14. **The blueprint decides,
the walk reviews.** Every decision is written into the goal: a tool chosen for a step is a pin
there, a fact told is a measurement in its profile. The pipeline is resolved again from the goal,
and the draft is always the resolved pipeline's reviewed steps. A change that brings steps with it
(HISAT2's index in, STAR's out) leaves nothing behind. The overview is a count (*eleven steps;
two need you*). Pacing (*together*, *stop only where needed*, or *ask me every time*) and Dev mode
are both decided before the walk. The walk goes in the blueprint's order: a step stops when it is
tier 4, or has a registry gap Dev mode shows (a tool with no description, an unverified contract,
a setting with no declared values), or always under *together*. Otherwise it is placed quietly. A
tier-4 setting with no declared values is a gap, not a stop, so with Dev mode off it is placed and
left to the run. A step's card offers *Continue*, each compatible tool as the whole pipeline it
gives (*adds hisat2_build; removes star_genomegenerate*), and, where a rule lacked a fact, *tell
me*. A tool you choose over the engine's is tier 4 and yours, with the engine's pick kept beside
it. Hand edits open once the walk is done. The cards are the existing ones; part 5 designs them.

**As built (Part I.0, #307).** A model hands over **changes**, never a goal: the want, the
inputs and facts it heard, a state on what is wanted, a tool or a setting, what was asked for
that nothing here can make, or the retraction of one. A change that **quotes the person** — the
quote found in one of their own turns — is *heard*, and recorded while the goal is still being
checked; one that does not is *suggested* and waits for their click. Once the goal is confirmed,
every model change waits for a click: an amendment is shown before it moves anything. Rule 5
becomes **nothing is recorded from a model unless it quotes you**. Every conversational prompt is
told what is known, from the record, and the record wins where the conversation seems to
disagree. The goal card shows the words each fact was heard in, which is where a misreading
(*"not paired-end"*) is caught.

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
| **Characteriser** (a model, 14.7.7) | at most 8 KB of the sample's text, from the start of its decoded head | a model, through door 6, on the AI worker | the excerpt reaches the model; nothing about it is stored by us beyond the model's reply | level 0 only |
| *Later:* an inspector in **the browser** | the head | the person's browser | only the facts | designed for `guarded` |

**At level 0 a sample's head reaches this server.** That is the loosening recorded below; the
other levels are written so that tightening is filling in a row.

## The protocol is code

The diagram is **generated, not drawn** (14.7.2). One declarative object in the code
(`mendel_authoring/protocol.py`, in its own pure package) holds the stages, every node (who acts: *you*, *engine*,
*AI*, *safety*, *stop*; its tier border; its session phase) and every edge (its label and, where
it moves the session, its event). The design lives in the same object, marked planned. From it:

- **the session moves by it**: a session stores the node it rests on (`at`). Everything a person
  or a job does is a command naming an arrow out of that node, refused (MI0216) where none is
  drawn; a retry out of `failed` takes the return arrow back to the phase that failed. Entering an
  acting node runs its handler (`mendel_api/stages/`), whose outcome names the next arrow. The
  phase is read off the node a session reaches, and `services/session.py` is the only code that
  writes either. A section within a request (reading a sample) is one step: its entry node's
  outcome names the section's way out. **Every action is a typed command**
  (`mendel_authoring.commands`), performed in one transaction through `services/session.py`;
  an exception rolls all of it back, and the jobs it asked for (a model's reading, a question's
  phrasing) are queued only after it commits. Nothing that calls a model runs inside one. The
  object refuses to load when it is inconsistent;
- **a path a setting chooses is drawn**: a *fork* is a node whose arrows are the cases of a
  subject (a setting today; a parameter or a fact later), and the interpreter takes the arrow for
  the case the shell's snapshot is in. No handler runs and no `if` decides it. The object refuses
  to load when a fork misses one of its subject's options, or switches on an open value with no
  default arrow;
- **the diagram is generated**, as a whole file, with `make docs` failing when it is stale;
- later, **the agents' wiring**: which prompt a node sends and what evidence it receives, per
  protection level, read from the same object instead of scattered through services.

**To change the protocol, edit `PROTOCOL`**, never the state machine: a substep that builds a
planned part gives its nodes phases and flips `built`, and an acting node needs a handler, which
the binding test demands.

## Protection profiles: what may cross, per node

The profile is a variable the engine carries through the whole loop. **Level 0 is the MVP**, and
everything is open. The other rows are recorded so the loop is built with the switch in place, and
tightening is filling in a row, not rewiring.

| Node | **0 (MVP)** | `guarded` (later) | `sealed` (later) |
|---|---|---|---|
| files | uploaded; each file's first 4 MB held in memory, never stored | read in the browser, facts only | none |
| characteriser receives | at most 8 KB of the sample's text, which may reach disk in Redis's snapshot | derived facts, after confirmation | not run |
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
- **A model reads part of a person's file** (14.7.7, 2026-10-04). When nothing here reads a sample's
  type, up to 8 KB of its text crosses door 6 to the configured model, which may be outside this
  server. **The excerpt waits in Redis** inside the AI job's arguments until the worker takes it,
  and no longer than the card waits (the job expires with the reading). The job keeps no result. One
  path keeps it longer: a job ARQ fails after its retries is kept for the worker's default hour
  (#242). **Either can reach disk**: Redis snapshots its data to a persistent volume, so a snapshot
  taken while a job waits writes the excerpt into it, with no expiry tied to the card. Level 0
  allows this (#281, operator, 2026-10-07: *for 0 we can leave it be written*); a later level that
  keeps excerpts off disk turns the queue's snapshots off. The excerpt is never logged (its `repr`
  is sealed). **What the model quotes as evidence is kept**, whole, in its reply
  (`ai_invocation.response`), with `unmatched` and refused replies (#238, operator, 2026-10-04:
  *level 0 is not really protected, but the easiest to work with*). Each later level decides whether
  a reading happens at all, and what of its reply is kept.

## Open questions

- When several samples are allowed (#218), are they inspected one by one or as a set? One sample
  is built: its first 4 MB per file, held in memory, never stored.
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
| 2026-10-04 | the diagram moves the session: `at`, a command per arrow, a handler per acting node; redrawn where an arrow was a hand-off (*your answer*, *not quite* back to you, a sample's two ways out) | 14.7.8.1 (#136), operator: *updating the flow means updating the diagram* |
| 2026-10-04 | the characteriser built: door 6, a fourth AI point, *read by AI*; each property quotes the line that states it and the engine checks the quote; a type an inspector reads goes back to it | 14.7.7 (#135, #244), operator's brainstorm and decision |
| 2026-10-05 | the stage modules behind one facade: each action a typed command in one transaction, its jobs queued after the commit; the steps that only queue a model's work (`family`, `ask`, `suggest`, `readback`) act, and pass straight on | 14.7.8.1c (#136), spec §11, operator's brainstorm |
| 2026-10-06 | forks: a node whose arrows are the cases of a pluggable subject, taken by the interpreter from a snapshot; every option covered, checked when the protocol loads | 14.7.8.3a (#136, #252), operator's brainstorm |
| 2026-10-06 | stage ④ built: overview count, the Pacing and Dev forks, the walk on the build plan (fact first, asked once; choices from the resolver's tools; tier 4 stops; gaps shown or routed around), the wrap-up; Build/Spawn and `Mode` retired | 14.7.8.3b (#136, #117, #252), operator's brainstorm |
| 2026-10-07 | the blueprint decides, the walk reviews: every decision an amendment to the goal (a tool pinned at its site, a fact in the profile), the draft a projection of the resolved blueprint, any step swappable for a compatible tool shown as a whole pipeline; one step card and one `amend` node; Dev decided before the walk; edits after the walk | 14.7.8.3c (#136, #253–#259), operator's brainstorm |
| 2026-10-07 | level 0 lets a waiting sample excerpt reach disk in Redis's snapshot; a later level turns the queue's snapshots off | 14.7.8.3d (#281), operator's decision: *for 0 we can leave it be written* |

| 2026-10-11 | retained decisions compose the goal; conflicting evidence asks an explicit choice; corrections cascade semantic reviews; manual work forks; history now and undo later | 14.7.8.3d Part F (#290), operator decisions in the approved spec |

## Corrections and retained decisions (14.7.8.3d Part F)

The draft owns the current selections and their retained revisions. The session retains the
workflow node, extraction presentation and pacing; its historical migration archive never
supplies current decisions. The goal is composed from selected input, want, measurement,
producer and parameter rows. The graph carries the decision revision it projects.

An observation never replaces a known answer automatically. At a waiting boundary the engine
asks which answer to keep, showing both values and their sources. Keep, use the observation,
correct and return to unknown are explicit choices. Delayed observations remain evidence and
cannot settle a newer question. The chooser's typed role is independent of the fact's origin.

Corrections use the drawn correcting path: record truth, resolve, cascade semantic review
status, then resume the applicable gathering or review boundary. A missing input or incompatible
pin leaves truth selected and the projection outdated; keep and materialisation refuse it.
Manual graphs take the fork path and remain unchanged in the linked original draft.

Fact history is inspectable now. Undo is deferred to
[issue 302](https://github.com/comeni-project/Comeni-Labs/issues/302): restoring a historical
answer must make a new attributed decision and run the same cascade and version checks.

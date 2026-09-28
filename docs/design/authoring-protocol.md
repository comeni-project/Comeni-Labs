# The authoring protocol — from a sentence to a goal that builds

**A living document.** It grows as the walk finds what the protocol gets wrong, and every change
names the issue that caused it. It describes the *protocol* (who asks what, in what order, and
what is allowed to cross) rather than the code. The code follows it, and where the two disagree,
this page is what gets argued about.

Started 2026-09-28 from #105 and #114, during Living Pipeline Plan 2.

---

## The loop

```mermaid
flowchart TD
    classDef person fill:#1f3a5f,stroke:#6fa8dc,color:#fff
    classDef engine fill:#1e3d2f,stroke:#6fbf8f,color:#fff
    classDef model fill:#4a2f1f,stroke:#e0a060,color:#fff
    classDef gate fill:#3a1f3a,stroke:#c080c0,color:#fff
    classDef stop fill:#4a1f1f,stroke:#e06060,color:#fff
    classDef t3 fill:#4a4a1f,stroke:#e0d060,color:#fff
    classDef t4 fill:#5a1f1f,stroke:#ff6060,color:#fff

    START(["Person: what they want<br/>(+ optional files)"]):::person
    WANT["Main agent: sentence → typed want<br/>goal.want"]:::model
    NEEDS["Engine: walk back from the want<br/>→ required INPUTS + MEASUREMENTS rules read"]:::engine
    FILES{"Files dropped?"}:::engine
    PROFILE{{"Protection profile:<br/>what may cross"}}:::gate
    INSPECT["Declared inspector for this type<br/>→ facts marked MEASURED"]:::engine
    CHARM["Characteriser agent (no inspector)<br/>→ typed facts, closed vocabulary<br/>marked MODEL-READ"]:::model
    GAPS{"Engine: next gap?"}:::engine
    ASK["Main agent: gap → typed question<br/>in the person's words"]:::model
    ANSWER{"Person answers"}:::person
    FACT["Fact recorded<br/>marked PERSON-SAID"]:::engine
    UPLOAD(["Ask for a file"]):::person
    OPEN["Measurement left OPEN<br/>(nobody knows, nothing guessed)"]:::engine
    STOP(["Honest stop:<br/>names the missing INPUT"]):::stop
    CARD["Goal card: every fact with its source<br/>open measurements listed"]:::person
    RESOLVE["Resolve: the four-tier ladder"]:::engine
    T3["Tier 3 — a rule matched a fact<br/>yellow: check the premise"]:::t3
    T4["Tier 4 — no rule matched, or its fact is open<br/>red: always flagged, a person answers"]:::t4
    BUILD(["Build step by step"]):::engine

    START --> WANT --> NEEDS --> FILES
    FILES -- yes --> PROFILE
    FILES -- no --> GAPS
    PROFILE -- "type has an inspector" --> INSPECT --> GAPS
    PROFILE -- "no inspector" --> CHARM --> GAPS
    GAPS -- "none left" --> CARD
    GAPS -- "a gap" --> ASK --> ANSWER
    ANSWER -- "states it" --> FACT --> GAPS
    ANSWER -- "doesn't know" --> UPLOAD
    UPLOAD -- "uploads" --> PROFILE
    UPLOAD -- "can't / won't, MEASUREMENT" --> OPEN --> GAPS
    UPLOAD -- "can't / won't, INPUT they have" --> FACT
    ANSWER -- "doesn't have the INPUT" --> STOP
    CARD --> RESOLVE
    RESOLVE -- "fact known" --> T3 --> BUILD
    RESOLVE -- "fact open" --> T4 --> BUILD
```

**Colour is authorship.** Green is deterministic (the engine proves it, and the same inputs give
the same answer). Orange is a model (typed output, closed vocabulary, always marked). Blue is the
person. Purple is the protection profile deciding what crosses.

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
   label. Which types have an inspector is declared, so the lost flexibility is visible.
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

## How a fact's source reaches the tiers

The four tiers are unchanged. What this protocol adds is **where the premise came from**, which
the tier-3 colour already asks a reader to check.

| The fact a rule reads | Tier of the decision | What the reader sees |
|---|---|---|
| `MEASURED`: an inspector read the file | 3, data-profiled | yellow: check the premise (a measurement) |
| `PERSON-SAID`: the person stated it | 3, data-profiled | yellow, premise marked *asserted* |
| `MODEL-READ`: the characteriser read it | *open question, see below* | — |
| open: nobody knows | **4**, ambiguous | red: always flagged, a person answers |
| no rule reads it | 1 or 2 as today | — |

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

## Loosenings, recorded (2026-09-28, operator's decision)

- **Invariant 15, *Mendel does not receive patient data*, does not hold at level 0.** A sample
  file is uploaded and a model may read it. It holds at `guarded` and `sealed`. Safety is added
  as levels *after* the loop works, not before.
- **Invariant 3, *three runtime AI points*, gains a fourth: characterisation.** It is declared,
  typed and recorded like the others (an `AiPoint`, a door, a prompt file, an `ai_invocation` row).
- **The typed payload stays.** Every agent answers in a declared shape. What loosens is *what the
  input may contain*, never the output's type.

## Open questions

- **Can a tier-3 decision rest on a `MODEL-READ` fact?** Tier 3 means a declared rule matched a
  fact. If a model supplied the fact, the rule is deterministic but its premise is not.
  Either it stays tier 3 with the premise marked *model-read*, or it is demoted to tier 4
  (invariant 6: anything a model touched is flagged).
- Where do uploaded samples live, how big may one be, and when are they deleted?
- Does a per-sample fact (`read_length` differs between two files) become a per-sample measurement
  or a question?
- #113: should *New pipeline* open this loop rather than the manual canvas?

## Changelog

| Date | Change | Why |
|---|---|---|
| 2026-09-28 | first version | #105 (no place for *paired-end*), #114 (nobody asked for the genome) |
| 2026-09-28 | nothing is guessed; an open measurement falls to tier 4 rather than blocking; inputs and measurements split; the tier table | operator, during the #105/#114 brainstorm: *the model can keep that param open as a tier-4 question* |

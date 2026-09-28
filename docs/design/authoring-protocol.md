# The authoring protocol — from a sentence to a goal that builds

**A living document.** It grows as the walk finds what the protocol gets wrong, and every change
names the issue that caused it. It describes the *protocol* (who asks what, in what order, and
what is allowed to cross) rather than the code. The code follows it, and where the two disagree,
this page is what gets argued about.

Started 2026-09-28 from #105 and #114, during Living Pipeline Plan 2.

---

## The loop

```mermaid
flowchart LR
    classDef you fill:#1f3a5f,stroke:#6fa8dc,color:#fff
    classDef engine fill:#1e3d2f,stroke:#6fbf8f,color:#fff
    classDef ai fill:#4a2f1f,stroke:#e0a060,color:#fff
    classDef safety fill:#3a1f3a,stroke:#c080c0,color:#fff
    classDef stop fill:#4a1f1f,stroke:#e06060,color:#fff
    classDef yellow fill:#4a4a1f,stroke:#e0d060,color:#fff
    classDef red fill:#5a1f1f,stroke:#ff6060,color:#fff

    subgraph S1 ["① You describe it"]
        direction TB
        SAY(["You: “gene counts from my<br/>paired-end RNA-seq”<br/>(files optional)"]):::you
        TARGET["AI turns it into a target:<br/>a gene-counts table"]:::ai
        SAY --> TARGET
    end

    subgraph S2 ["② The engine gathers what it needs"]
        direction TB
        NEEDS["Engine lists what the target needs<br/>inputs: reads, genome, annotation<br/>facts: read length, paired or not"]:::engine
        MISSING{"Anything on the<br/>list still unknown?"}:::engine
        ASK["AI asks you about it,<br/>in plain words"]:::ai
        REPLY{"You answer"}:::you
        FILE(["You upload a file"]):::you
        SAFETY{{"Safety level decides<br/>what the AI may see"}}:::safety
        READ_ENGINE["Engine reads it exactly<br/>(FASTQ, …)<br/>→ “measured”"]:::engine
        READ_AI["AI reads it<br/>(types the engine can't)<br/>→ “read by AI”"]:::ai
        SAID["→ “you said”"]:::engine
        OPEN["Left open → you'll choose<br/>during the build"]:::engine
        STOP(["Stop: can't build without it<br/>(e.g. no genome)"]):::stop
        TICK["Added to the list"]:::engine

        NEEDS --> MISSING
        MISSING -- "yes" --> ASK --> REPLY
        REPLY -- "I know it" --> SAID
        REPLY -- "not sure" --> FILE
        REPLY -- "I don't have that input" --> STOP
        FILE -- "uploaded" --> SAFETY
        SAFETY -- "engine knows the type" --> READ_ENGINE
        SAFETY -- "it doesn't" --> READ_AI
        FILE -- "can't share it" --> OPEN
        SAID --> TICK
        READ_ENGINE --> TICK
        READ_AI --> TICK
        OPEN --> TICK
        TICK --> MISSING
    end

    subgraph S3 ["③ You check the goal"]
        direction TB
        CARD["Goal card: every fact<br/>and where it came from"]:::you
    end

    subgraph S4 ["④ It's built step by step"]
        direction TB
        DECIDE{"For each choice: is the<br/>fact it depends on known?"}:::engine
        RULE["Chosen by a rule<br/>yellow: check the fact behind it"]:::yellow
        CHOOSE["No rule could decide<br/>red: you choose"]:::red
        STEPS(["Each step offered to you"]):::you
        DECIDE -- "known" --> RULE --> STEPS
        DECIDE -- "left open" --> CHOOSE --> STEPS
    end

    TARGET --> NEEDS
    MISSING -- "no, all known<br/>or left open" --> CARD
    CARD -- "that's right" --> DECIDE

    subgraph KEY ["Who acts"]
        direction TB
        K1(["You"]):::you
        K2["Engine: same input, same answer"]:::engine
        K3["AI: typed answers only, always marked"]:::ai
        K4{{"Safety level"}}:::safety
    end

    style S1 fill:transparent,stroke:#555
    style S2 fill:transparent,stroke:#555
    style S3 fill:transparent,stroke:#555
    style S4 fill:transparent,stroke:#555
    style KEY fill:transparent,stroke:#333
```

**Colour is who acts**, and the key is in the diagram. In the rules below, *engine* means
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
| 2026-09-28 | diagram reorganised into four stages with plain-language labels and a key | operator: *make the text more intuitive, and the organisation* |
| 2026-09-28 | nothing is guessed; an open measurement falls to tier 4 rather than blocking; inputs and measurements split; the tier table | operator, during the #105/#114 brainstorm: *the model can keep that param open as a tier-4 question* |

# Intent, facts and steps (14.7.8.3d Part I.0) — design

**Status: written for review (2026-10-13).**
Each choice in §2 was made by the operator in the brainstorm of 2026-10-13 and is recorded on
[307](https://github.com/comeni-project/Comeni-Labs/issues/307). Choices this spec makes on its
own are marked **(spec)** so a reviewer can find them.

Scope: [307](https://github.com/comeni-project/Comeni-Labs/issues/307), before Part I.2 of
[293](https://github.com/comeni-project/Comeni-Labs/issues/293). Code baseline: `13e2564c`, after
Part I.1, with the operator's `comeni-core` audit (`11689084`) in progress beside it: the
`artifact/` files this spec changes are the ones that audit is editing, so Plan B starts only
once that pass has landed.

## 1. What a researcher gets

The conversation remembers what is known and uses it. It never asks for something they already
said, and it never records that they said something they did not: every fact taken from their
words carries the words, checked against what they typed. The model's own ideas are offered,
marked as its own, and count only when they click. They can add, change or remove a fact or
what they want at any point, by saying so, and the build follows.

The saved `pipeline.yml` says what they wanted, what is known about their data and where each
fact came from, and how the pipeline is built; with the compiler and the registry it rebuilds
the same pipeline anywhere, and it says where to fetch that registry.

## 2. Choices agreed with the operator

| Question | Choice |
|---|---|
| The data structures | **Intent, facts and steps.** Intent: what is wanted, constraints, tools pinned. Facts: inputs and measurements, each with its source. Steps: as today. `Goal` remains only as the resolver's input, projected from intent and facts. |
| What the model returns | **Commands with a reader**, never a blob: each one changes intent or facts, and each has consumers (§5.2). A command nothing reads is not a command. |
| Trust | **Heard or suggested.** *Heard*: quotes the person's words and the quote checks; recorded. *Suggested*: the model's own idea, or a quote that fails; recorded only on the person's click. The goal card's *That's right* is the one confirmation before anything is built. |
| The model's own ideas | **Kept** ("we don't want to kill the flexibility"), as suggestions. |
| What was asked but is not offered | **Reported by the model, quoting the person** (A only); no registry vocabulary added for it. |
| Memory | **What is known is handed to every conversational prompt**, from the store, not re-read from the transcript. |
| The save file | **One file**, `pipeline.yml`: intent and facts **at the top**, then registry, then steps. |
| The person's words in the save file | **No.** Each fact says its source (*said*, *measured*, *read by AI*, *open*); quotes stay in the database. |
| The registry in the save file | **Locator and integrity, kept apart** (the Nix model): each layer keeps its `digest` and gains `source` and `commit` (and whether it had uncommitted edits). |
| Database and file | **Both.** The tables are the working record (every revision, who, when, the quotes); the file is what is kept and shared (the current state). |
| Run-time pins | Containers by digest and the Nextflow version are **not here**; their own issue. |

## 3. What is already right, and what is not

Research on the codebase (2026-10-13) found the store already has the split this design names:

- `services/decisions.py` keeps six families of retained revisions with one current pointer each
  — `input`, `want`, `fact` (backed by immutable observations), `producer` (a tool pinned for a
  site), `parameter`, `review` — with history, forks and attribution (`ActorKind.MODEL` exists).
  `mendel_authoring.decisions.Decisions` is their pure value, and `Decisions.goal()` already
  projects the `Goal`. **Intent** is `want` + `producer` + `parameter`; **facts** are `input` +
  `fact`. Nothing here changes shape except §6.1's additions.
- `CorrectFact` already changes a fact at any waiting node, and the diagram routes the
  consequence (`correct_fact` → gather again, check the goal again, re-resolve and re-review, or
  stop).

What is wrong is at the two edges:

- **The model's boundary.** `builder.goal.v7` returns `WantUnderstanding` (`want`,
  `constraints`, `stated`, `questions`), stored whole as `session.extraction` and special-cased
  three ways: `want` becomes the card, `constraints` become *suggested* chips, `stated` becomes a
  pre-fill. `builder.chat.v2` returns an `AuthoringIntent` that changes nothing: `chose`,
  `setting` and `proceed` are only narrated (`authoring_jobs._block_for`), and `revise` works only
  at goal review ("not available in this version" otherwise). `builder.gap.v2` reads a typed
  answer into a pre-fill. Three shapes, none writing through the store.
- **Memory.** Only `builder.ask.v1` is shown what is known (`{{facts}}`); `family.v3`, `goal.v7`
  and `chat.v2` see the raw conversation and re-derive it.
- **The save file.** `goal:` mixes intent and facts, and its measurements read
  `source: goal`; `registry.layers` records a digest and nowhere to fetch it.

## 4. Two plans

**Plan A, the conversation** (§5–§7): commands, heard and suggested, memory, the reply shapes,
the prompts. **Plan B, the save file** (§8): version 7, its upgrader, the registry locator, and
opening a saved file. A lands first; B starts after the operator's `artifact/` pass.

## 5. Commands

### 5.1 One family, every caller

Five commands change intent or facts. The person's clicks and edits, the chat model's reply,
and the diagram's own handlers all issue them; they write through `services/decisions.py` and
continue through the diagram as `CorrectFact` does.

| Command | Changes | Store call | Read by |
|---|---|---|---|
| `Want(type)` | what to build | `want` family | resolver, gap engine, goal card, wrap-up, memory |
| `Fact(subject, value)` — an input held (`subject` a type, no value) or a measurement | facts | `set_input` / `observe` + select | gap engine (its question is not asked), resolver (tier-3 premises, `meta`), goal card, memory |
| `Constrain(...)` — a required state on a wanted output, a tool pinned for a site, a parameter value | intent | `want.states` / `producer` / `parameter` | resolver, goal card, step cards, memory |
| `Retract(subject)` | removes one of the above | `withdraw_input`, `set_fact(None)`, want `present: false`, `release_producer`, `release_parameter` | the readers of what is removed: a gap reopens, a pin is released |
| `NotOffered(phrase)` | the record of what was asked and cannot be made | new `asked` family (§6.1) | goal card, wrap-up (I.2), memory, so the chat never promises it |

Each carries: **who** (person, or model with its invocation), **heard or suggested** (§5.3),
and for heard, **the quote** and the turn it came from. A command whose subject is not declared
(a type, a measurement, a step, a tool, a parameter) is refused by the same admission that holds
the vocabulary today (`MI0204`), never recorded.

`CorrectFact`, `AnswerGap`'s fact-writing half, `ReleaseProducer` and `DecideGoal(edited)`
become thin callers of this family **(spec)**: their routes and diagram edges stay; what they
write goes through one path. The diagram gains no new node: the commands enter at the existing
waiting nodes (`reply`, `card`, `step_card`, `wrap`, `stopped`) on the existing
`correction_requested` edges, and the correction section's handlers decide what follows.

### 5.2 A command must have a reader

`NotOffered` was the one without one; I.2's goal card and wrap-up read it, and the memory reads
it from this part on. A test lists, for each command, the readers named above and asserts each
reads it (§10).

### 5.3 Heard or suggested

**Heard** when the command carries a quote that **checks**: at least 3 characters, found in one
of the person's own turns in this session after case-folding and collapsing whitespace **(spec)**.
The quote is recorded with the turn's `seq`. **Suggested** otherwise: no quote, or a quote that
does not check, or the model's own inference.

| | Before the goal is confirmed | After (building, wrap-up) |
|---|---|---|
| **Heard** | recorded; its question is not asked; listed on the goal card with its source, correctable there | **previewed, then applied on one click** **(spec)**: a change mid-build re-resolves the pipeline, and the consultant build decided that a model's amendment is shown before it moves anything ([consultant build design](2026-10-04-the-consultant-build-design.md) §14: *the AI as guide* proposes amendments, *previewed like any other*) |
| **Suggested** | a pre-filled question, or a chip to keep or dismiss, marked *suggested by AI* | the same, as a card |

`NotOffered` is heard only: a phrase the person did not say is dropped, never suggested.

### 5.4 What a heard command is not

A quote proves the person said the words, not that the model read them right: *"not
paired-end"* contains *"paired-end"*. So a heard fact is still shown on the goal card with its
quote, and a tier-3 step it decides still carries *check the premise*. The quote rule removes
invented evidence; the card removes misreadings.

## 6. The store

### 6.1 Additions

- **`heard`** (text, nullable) and **`heard_seq`** (int, nullable) on `pipeline_observation` and
  on the `input`, `want`, `producer` and `parameter` revisions: the quote and the turn it came
  from. Plain columns, no JSON shape change. Retention keeps them as it keeps the person's turns;
  deleting a draft deletes them (Part H).
- **The `asked` family** (`pipeline_asked`, `pipeline_asked_revision`): one subject per phrase
  the person asked for that cannot be made, with `heard`, `heard_seq` and `present`. Not part of
  `Goal`: nothing the resolver reads.
- **`suggested`** proposals: a suggestion waiting for a click is a proposal row of a new kind,
  `suggestion`, carrying the command it would issue; accepting it issues that command as the
  person (`ActorKind.PERSON`), with the model named in the revision's `proposal_id`.
- `session.extraction` is **retired**: the want, the constraints and the stated candidates are
  commands now. A session whose `extraction` is set is converted by its migration: `want` →
  `Want` (unquoted, so it waits on the card as today), `constraints` → suggestions, `stated` →
  suggestions (they were candidates, never facts).

### 6.2 The memory

A pure function in `mendel-authoring`, `memory.render(decisions, asked, pending, open_gaps,
names) -> str`, writes *what is known* from the current revisions: the wants, the constraints,
what was asked and not offered, each input and fact with its source and, when heard, its quote,
the suggestions still waiting, and the questions still open. Names come from Part I.1
(`explain.name_of`). Same decisions in, same text out; golden-tested.

It is inserted into every conversational prompt: `family`, `goal`, `ask`, `chat`, `readback`.
The transcript stays in the prompt as context; the memory is the record **(spec)**: a prompt
says the memory wins where they disagree.

## 7. What a model returns

### 7.1 One item shape per command, no unions

`AuthoringIntent`'s docstring records why this repository's reply shapes are one level deep
with exclusive fields: a local model that cannot reliably pick a variant tag can still fill a
field. So the commands are **lists of flat items**, one list per command, never a tagged union
**(spec)**:

```json
{
  "say": "…",
  "wants":       [{"type": "counts.matrix", "quote": "gene counts"}],
  "inputs":      [{"type": "genome.fasta", "quote": "the human genome"}],
  "facts":       [{"subject": "paired", "value": true, "quote": "paired-end"}],
  "requires":    [{"type": "counts.matrix", "states": ["gene_level"], "quote": "gene-level"}],
  "pins":        [{"type": "alignment.bam", "tool": "nf-core/hisat2/align@2.2.2", "quote": "use HISAT2"}],
  "parameters":  [{"name": "seq_platform", "value": "ILLUMINA", "quote": "Illumina"}],
  "retract":     [{"subject": "read_length", "quote": "forget the read length"}],
  "not_offered": [{"quote": "differential expression"}],
  "questions":   [ … AskedQuestion … ],
  "proceed": false
}
```

`quote` is optional on every item but `not_offered`. `say` is what the person reads: an
acknowledgement, an explanation, or nothing. Each call's reply format carries only the lists that
call may fill (§7.2), so no call is asked to leave half a shape null — the configuration the
forge measured a local model doing worst on.

### 7.2 The calls

| Call | Becomes | May fill |
|---|---|---|
| `family.v3` | unchanged in shape; gains the memory | — |
| `goal.v7` | **`goal.v8`** | `say`, `wants`, `inputs`, `facts`, `requires`, `not_offered`, `questions` |
| `chat.v2` and `gap.v2` | **`chat.v3`**, one call for typed words anywhere after the want is read; the memory says which question is open, so a typed answer is a `fact` like any other | every list, `say`, `proceed` |
| `ask.v1` | **`ask.v2`**: words only; `already_option` / `already_value` go, since recognising what was said is the reading calls' job and the memory already shows it | — |
| `readback.v1` | **`readback.v2`**: the memory instead of the bare goal | — |
| `characterise.v2`, `tier4.v2` | unchanged | — |

`proceed` replaces `AuthoringIntent.proceed`, and now continues for real: it issues the waiting
node's *continue*. `explain` and `unsupported` become `say` (an unsupported request is said, and
`not_offered` records it when it is about the want). A prompt change is a new version file; each
gets recorded fixtures.

## 8. The save file (Plan B)

### 8.1 Version 7

```yaml
version: 7
intent:
  want: [counts.matrix]
  constraints:
    required_states: [{type_id: counts.matrix, states: [gene_level]}]
    params: []
    producers: []
facts:
  inputs:
  - {type_id: fastq.reads, states: []}
  - {type_id: annotation.gtf, states: []}
  - {type_id: genome.fasta, states: []}
  measurements:
  - {measurement: paired, value: true, source: said}
  - {measurement: read_length, value: 100, source: measured, by: …, pieces: [fastq@1.1.0, read_length@1.0.0]}
registry:
  layers:
  - name: comeni-registry
    digest: sha256:…
    source: https://github.com/comeni-project/comeni-registry
    commit: 396a5c6…            # the full sha
    dirty: false
  displaced: []
  unverified: []
ai: …
steps: …                        # unchanged
```

- `intent` and `facts` are `Goal`'s fields regrouped: `want` and `constraints` under intent;
  `have` (as `inputs`) and `profile.measurements` under facts. `Pipeline.goal` stays as a
  property computed from them, so every reader of a pipeline's goal is unchanged.
- **`source: goal` becomes `source: said`** — `ValueSource.GOAL` is renamed `SAID` (nine uses
  across four packages), everywhere a source is written, `why.source` included **(spec)**.
- **Nothing the person typed** is in the file: no quote, no `not_offered`. `Pipeline` is an
  egress payload and `FREE_TEXT_FIELDS` does not grow.

### 8.2 The registry locator

Each layer's locator is read where git may be run: `mendel-compiler` (already impure,
`subprocess`) gains `locate(layer_path) -> Locator` — the remote URL of the repository holding
the layer (`origin`, or none), the commit (`git rev-parse HEAD`), and `dirty` (`git status
--porcelain -- <layer>` non-empty). The callers of `Pipeline.of` (four: `mendel_compiler.
orchestrate`, and `mendel-api`'s build, drafts and canvas services) pass the locators in, so
`comeni-core` stays pure. A layer not in git records no `source` or `commit`, and the build
says the pipeline cannot be rebuilt from its file alone.

`mendel upgrade` reports, beside today's *layer changed since it was locked*, **which commit to
check out** when the locator is known.

### 8.3 The upgrader

`Pipeline._v6_to_v7`, beside `_v1_to_v2` and `_v5_to_v6`: regroups `goal` into `intent` and
`facts`, renames `source: goal` to `said` wherever it appears, and leaves the layer locators
absent (unknown, never invented). A version-6 file loads, upgrades in memory, and re-emits a
byte-identical `.nf`.

### 8.4 Opening a saved file

Importing a `pipeline.yml` into a new draft writes its intent and facts as decisions
(`import_goal`, extended to the `asked`-free v7 shape), attributed to the person importing, with
`action: import`. The steps are re-derived by resolving, and the file's decision records are
replayed, never re-asked — `mendel upgrade`'s behaviour.

## 9. When it goes wrong

| Case | What happens |
|---|---|
| a quote that does not check | the command becomes a suggestion; never recorded as heard |
| an undeclared id in a command | refused at admission (`MI0204`), nothing recorded, the person told |
| `not_offered` with no quote, or a failing one | dropped |
| a heard command at a node with no correction edge (async work in flight) | held as a suggestion until the session waits again |
| a heard change mid-build | previewed; nothing moves until the click |
| a retract of something not recorded | nothing changes; the reply says so |
| a model reply naming two contradictory facts for one subject | both become suggestions; neither is heard |
| a v6 file | upgraded in memory; locators absent |
| a layer with uncommitted edits | `dirty: true`; the build warns |

## 10. Testing

- **The quote guard:** a heard command whose quote is not in the person's turns is never
  recorded as heard. Watched failing, recorded in the guard ledger.
- **Every command has a reader:** one test per command naming its readers (§5.1).
- **The store:** each command's write and its retract; heard columns; the `asked` family; a
  suggestion accepted is the person's revision naming the model's proposal.
- **The memory:** golden texts for scenario 1 at each stage (before the goal, building, wrap-up).
- **The calls:** recorded fixtures for `goal.v8`, `chat.v3`, `ask.v2`, `readback.v2`; admission
  of every list; `proceed` continues.
- **The conversion** of sessions with an `extraction`.
- **The save file:** a golden v7 `pipeline.yml`; the v6 → v7 upgrader on the examples; same goal
  → byte-identical `.nf` across the change; `mendel upgrade` from a lone v7 file rebuilds
  identically; the locator for a clean, a dirty and an un-versioned layer.
- **Purity:** `comeni-core` and `mendel-authoring` still in both purity guards; `locate` only in
  `mendel-compiler`.
- **Egress:** `FREE_TEXT_FIELDS` and `SAMPLE_FIELDS` unchanged.
- **The walk, with a model:** scenario 1 described in one sentence that states pairing and read
  length; neither is asked; the goal card shows both with their quotes; a mid-build *"actually the
  reads are 50 bp"* previews STAR → HISAT2 and applies on one click; a saved file rebuilds.

## 11. Not here

The goal card's words for *not offered*, the undetermined-sample wording, names on the goal card
and the wrap-up (Part I.2, on top of this); the model introducing steps, ask-anything and tone
(Part I.3); containers by digest and the Nextflow version (their own issue); undo (#302).

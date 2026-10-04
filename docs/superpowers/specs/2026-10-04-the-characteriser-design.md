# The characteriser — design

**Issue:** #135 (step 14.7.7, under #126). **Decided** by the operator on 2026-10-04, in the
brainstorm this spec records. It fills in *The characteriser: the fourth AI point* in §6 of
`2026-09-28-the-consultant-design.md`, and corrects it in one place (§3). The branch it builds is
the one `2026-10-01-samples-and-inspectors-design.md` §7 left dashed: *none claims the extension →
the characteriser*.

Opened from this brainstorm, out of scope here: #236 (vocabulary proposals: a model proposes a
type, state or measurement to the forge's queue, a person approves).

## 1. What a person gets

A sample nothing reads by its extension is no longer a dead end. A model reads the start of it and
says what it is, from the closed vocabulary, and each fact it reads is marked **read by AI**:

```
alignment.bam            read by AI
coordinate_sorted        read by AI
```

When the model names a type an inspector reads (a FASTQ saved as `reads.txt`), the file goes back
to that inspector, whose content check must agree, and the facts are **measured** as usual:

```
read by AI: FASTQ reads → measured
read_length: 151        measured · fastq 1.1.0 · 8,412 reads · 97% at 151
```

Nothing is guessed (protocol rule 5): the model reads only a file the person gave, and only what its
start states. It cannot name an id the registry does not declare.

## 2. The decisions

| Decision | Choice | Why |
|---|---|---|
| What the model sees | **a decoded text excerpt**: at most 8 KB or 200 lines | the smallest thing that can leave; fits a local model; covers headers and text formats |
| Asked before it is sent? | **no, automatic at level 0** | asking belongs to the safety levels (`guarded`), not to level 0 |
| Which types it chooses from | **two calls, families then types**, under `family_step_from` | the pattern goal extraction already uses (#194); scales to hundreds of types |
| A type an inspector reads | **the inspector measures it**; the model only identifies | measured beats read by AI |
| Which facts it may read | **the chosen type's states, and measurements whose `describes:` names that type** | the registry decides; bench facts can never be offered |
| What it sees and we lack | **`unmatched`, stored only**; the queue is #236 | the vocabulary stays closed; it grows through approval |
| Where the call runs | **a job on the AI queue**, carrying the excerpt | the worker stays the only thing that calls a provider |
| The hand-back to the inspector | **the browser re-sends the files by itself** | the server dropped the head; the browser still has it |

Confirming a model-read fact before it enters the goal is, like asking before sending, a row of a
later level: at level 0 an admitted fact enters the goal directly, labelled.

## 3. A correction to the consultant spec

§6 there says door 6 carries *the file's declared-extension type candidates*. **Types declare no
extensions**; only formats do, and a file reaching the characteriser is one no format claims. Nor
should the extension decide: a piece "never decides on a file's name". So the payload carries **no
file name and no extension**, and the candidates are the declared families, then their types. §6
gains a line pointing here.

## 4. The flow

```
upload ─▶ a format claims the extension? ── yes ─▶ the inspector measures (14.7.6)
              │ no
              ▼
          level allows CHARACTERISE? ── no ─▶ nothing reads this type yet (today)
              │ yes
              ▼
          decode an excerpt ── too little text, or no model ─▶ nothing reads this type yet
              │
              ▼
          queue characterise_sample(excerpt, question) ─▶ the card: "being read by AI…"
              │                                            (the 4 MB head is dropped)
              ▼  the AI worker, through door 6
          AI: which families? ─▶ AI: which type, states, measurements?
              │
              ▼
          admit every id ── undeclared ─▶ refused (MI0204/MI0205), the question stays
              │
              ├─ no inspector reads that type ─▶ stamped MODEL_READ ─▶ back to the questions
              └─ an inspector reads it ─▶ the browser re-sends the files ─▶ the format claims
                 them by the recorded type, its content check decides ─▶ measured (14.7.6)
```

1. **The upload runs as today** until no format claims the extension
   (`services/inspect.py`, `outcome="no_inspector"`).
2. **The level is asked:** `Crossing.CHARACTERISE`, already declared in `services/protection.py`.
   Above level 0 the outcome is today's.
3. **The excerpt is decoded** in the upload request (§5). Too little text, or no model configured
   (`/health/ai`), and the outcome is today's, with nothing sent.
4. **`characterise_sample` is queued** on `arq:queue:ai`, its job id named by what it is about
   (`builder:characterise:<session>:<proposal>`), with the excerpt and the question's id. The
   request returns `outcome: "reading"`. The head is dropped as always.
5. **The worker makes two calls** through door 6 (`Crossing.DOOR_6` asked before composing):
   families, then types (§6). When `family_step_from` switches the family step off, one call shows
   every type, as goal extraction does.
6. **Admission and stamping** (§7). The job writes the result into the session, the same way an AI
   turn arrives; the card sees it when the session refreshes.
7. **The hand-back** (§8), when the type named has a format that reads it.

## 5. The excerpt

- **Gzip is recognised by its first bytes** (`1f 8b`), never by the extension: a BAM is BGZF, gzip
  inside, and named `.bam`. Multi-member gzip is read through.
- **Decompression stops at 64 KB of output**, so a bomb costs 64 KB.
- **The excerpt is the first stretch of readable text at least 200 bytes long** within those bytes
  (UTF-8, tab, newline and carriage return; anything else ends a stretch), cut at 8 KB or 200
  lines, whichever comes first, at a line boundary.
- **`binary_before`**: whether binary bytes were skipped before the stretch. A BAM begins with
  `BAM\1` and a length; without this flag a BAM header and a SAM file read the same.
- **Fewer than 200 readable bytes: nothing is sent**, and the card says *nothing reads this type
  yet*.
- For a pair, the excerpt is read from the first file only: the two are one sample of one type.

It is computed in the API, by one pure function (`excerpt(head: bytes) -> Excerpt | None`) with
golden tests. The excerpt is **never stored** by Comeni Labs: `ai_invocation` keeps a digest of the
rendered prompt, not the prompt. **It waits in Redis** inside the job's arguments until the worker
takes it; the job keeps no result. That is a level-0 loosening, recorded in the protocol (§11).

## 6. Door 6 and the AI point

- **`AiPoint.CHARACTERISE`** joins `comeni_core.artifact.pipeline.AiPoint`: the fourth runtime AI
  point. `tests/artifact/test_ai_provenance.py` is updated to say so, which is what it is for.
  Invariant 3 changes from *designed, not built* to built, at protection level 0.
- **Door 6, `"characterisation"`**: `Door(CharacteriseRequest, DoorPath.PIPELINE)` in
  `comeni_core.artifact.egress.DECLARED`. One door for both calls.
- **`CharacteriseRequest`**, and nothing else:
  - `excerpt: Annotated[str, Mark.SAMPLE]` — **a new `Mark`, the first field that may hold data
    from a person's file.** `FREE_TEXT_FIELDS` in `tests/guards/test_egress.py` names it, with why;
  - `binary_before: bool`;
  - `families: list[FamilyOffer]` (the first call): each declared family id and its description;
  - `types: list[TypeOffer]` (the second call): each type id of the chosen families, its declared
    states, and the measurements that describe it (id, kind, values or range, unit).
  No file name, no extension, no `session_id`, no question text, no conversation. A test holds the
  field set equal to this list.
- **Prompts:** `builder.characterise-family.v1` and `builder.characterise.v1`, beside the other
  builder prompts. Each says: read only what the excerpt *states*; never what would need the whole
  file (a genome's length, how typical the first reads are); answer *none* or *undetermined* when
  you cannot tell.
- **Replies:**
  - `CharacteriseFamilies`: `families: list[FamilyId]`, empty meaning *none of these*;
  - `CharacteriseReply`: `type_id: TypeId | None`, `states: list[str]` (declared state ids of that type),
    `measurements: list[{id, value}]`, `undetermined: list[MeasurementId]`,
    `unmatched: list[{kind: type|state|measurement, name, cite}]`.
- **Purposes:** `characterise_family` and `characterise` join `authoring_ai.Purpose`; each call
  writes an `ai_invocation` row, as every call does. The model for them is the builder's
  `MODEL_TALK` lane unless the plan finds a reason for a lane of its own.

## 7. Admission and what is recorded

- A family or type nothing declares: **MI0204**. A state or measurement the chosen type does not
  offer: **MI0205**. Either refuses the whole reply, with the code on the card, and the question
  stays open. A shape the reply does not fit is retried once, as the other calls are.
- A measurement's value is admitted against its declared kind and range
  (`MeasurementRegistry.check`); a value outside it is dropped, as the inspector's are.
- **`unmatched` is never admitted, never shown, never queued.** It is stored in
  `ai_invocation.response`, where #236 will read it.
- **`MODEL_READ`** is new on two enums that answer two questions: `PremiseOrigin.MODEL_READ` (how
  good it is as evidence) and the existing `ValueSource.MODEL` (who settled it). The premise reaches
  `pipeline.yml` as `origin: model_read`, so the pipeline file's shape changes: the plan bumps
  `SCHEMA_VERSION` if that test says so. `Pipeline.ai` records `AiPoint.CHARACTERISE` with the
  model, as the other points do.
- The tier is **3** with *read by AI* on the premise (protocol table, decided 2026-09-28).
- Already said by the person: **their word stands**, and the difference is shown, as for a sample.
- **The type is recorded as an input** (protocol rule 8), whether or not it answers the question.
  States go with it. The question it was uploaded for closes only if the reading answers it.

## 8. The hand-back to an inspector

When the admitted `type_id` is one a format `reads:` (FASTQ today), the session records *read by
AI: fastq.reads* on the proposal, and the card **re-sends the same files by itself**. On that
upload, a file no format claims by extension may be claimed by **the type the session recorded**,
never by anything the browser says. The format's `confirms()` still decides; the measures run; the
facts are `MEASURED`, and the type's line says *type read by AI*. If `confirms()` fails, the
outcome is *unreadable* with its reason, and the recorded type is dropped: the model was wrong, and
nothing it said stays.

If the browser no longer holds the files (the page was reloaded), the card says *looks like FASTQ
reads* and offers **Measure as FASTQ**, which asks for them again.

## 9. What the person sees

The upload card:

- The picker accepts **any file** (today: `.fastq,.fq,.gz`).
- The line beneath it becomes: *only the first 4 MB is read, on this server · if nothing here reads
  its type, about 8 KB of its text goes to the AI to read*.

| When | The card says |
|---|---|
| queued, waiting for the model | ● *being read by AI…* (pulsing, like *measuring…*) |
| read | the type, each state and measurement on a line · **read by AI**; undetermined as today |
| named a type we measure | *read by AI: FASTQ reads → measuring…*, then the measured result, *type read by AI* |
| … the files are gone | *looks like FASTQ reads*, **Measure as FASTQ** |
| the AI could not tell | *the AI couldn't tell what this file is*; the question stays |
| refused at admission | *the AI's answer named something this registry doesn't declare · nothing was recorded* |
| no answer (timeout, error) | *the AI didn't answer*, **Measure again** |
| no model, or above level 0 | *nothing reads .bam files yet*, as today |

On the goal card a model-read premise has a yellow border and *read by AI*. The states are drawn in
the design canvas before the frontend task, and the live card is compared with them in one
viewport.

## 10. When it fails

| Case | What happens |
|---|---|
| level above 0 | no excerpt, no job; today's *nothing reads this type yet* |
| door 6 asked above level 0 | refused before composing, with the declared code naming the level |
| no model configured | today's outcome, nothing sent |
| too little text | today's outcome, nothing sent |
| a gzip bomb | 64 KB decoded, then the excerpt is cut from what there is |
| the provider does not answer | the job ends as a notice with a declared code (`UNREACHABLE`'s family); *the AI didn't answer* |
| the reply does not fit its shape | one retry, then refused with its code |
| undeclared id | MI0204/MI0205, the question stays |
| a second upload while one is being read | refused while the reading is out, with a declared code the plan names; the card's other answers already wait while a sample is out |
| the hand-back's content check fails | *unreadable*, the recorded type dropped |
| a forged type from the browser | ignored: only the session's record claims |

## 11. What changes in the docs

- **Diagrams.** *Inspecting a sample* (`docs/design/diagrams/inspecting-a-sample.md`) and the
  authoring protocol's overview are generated from `mendel_api/authoring/protocol.py`. The single
  dashed node *The characteriser reads it* is replaced by §4's branch as **planned** nodes in the
  plan's first task; each later task flips `built` on its own nodes, so the picture is solid only
  where the code is.
- **`docs/design/authoring-protocol.md`:** the *Where each measurer runs* row (designed → built);
  the excerpt waiting in Redis, as a level-0 loosening; rule 4's wording.
- **Invariants 3 and 15** in `CLAUDE.md` and `docs/design/invariants.md`.
- **The glossary:** *read by AI*. The handbook's upload page: what is sent, and when.
- **`docs/notes/now.md`** when the step closes.

## 12. Testing

Model calls use recorded transports only (`test_no_live_model.py`).

- **Excerpt goldens:** a BAM's first BGZF block, a FASTA, a GTF, a gzipped FASTQ, a binary-only
  file (nothing sent), a bomb (stops at 64 KB), and a file whose text starts after 200 lines.
- **Admission:** an undeclared family, type, state, measurement; a value outside its range; an
  empty reply meaning *none*.
- **The payload:** its fields are exactly §6's; it carries no name or extension.
- **The egress guard** names `Mark.SAMPLE`; watched failing without the entry, recorded in
  `tests/fixtures/guard-ledger.md`.
- **The level:** above level 0, no job is queued and door 6 refuses before composing.
- **The hand-back:** a FASTQ named `reads.txt` is claimed by the recorded type and measured; a type
  sent by the browser claims nothing; a failed `confirms()` drops the type.
- **The job:** recorded replies through both calls into the session; a provider that does not
  answer ends as a notice.
- **The card:** each row of §9 in vitest.
- **The walk:** a real BAM, a FASTQ renamed `.txt`, and the local model, with screenshots.

## 13. Built in four parts

Each part gets its own plan.

1. **14.7.7.1 The declarations:** the planned diagram nodes, `AiPoint.CHARACTERISE`, door 6,
   `CharacteriseRequest`, `Mark.SAMPLE`, the egress guard, `PremiseOrigin.MODEL_READ`, the two
   prompts, the reply shapes and admission.
2. **14.7.7.2 The excerpt and the job:** `excerpt()`, the `reading` outcome, `characterise_sample`,
   writing the result into the session, and the hand-back's claim by recorded type.
3. **14.7.7.3 The card:** artboards first, then the card's states, the automatic re-send, and the
   goal card's label.
4. **14.7.7.4 Docs and the walk:** the docs of §11, the diagram's last nodes flipped, the live walk,
   the journal.

The `comeni-core` version bump (a new AI point, a new door, a changed invariant) is judged at
release time.

## 14. Amendment, 2026-10-04: every property the AI reads carries its evidence (#244)

**Why.** Walked live with gemma3:12b (#243, #244), the model named the right type every time
and padded the rest of its answer:
- a free-text state on a type that declares none;
- states in `undetermined`;
- on FASTQ, every offered state, none of which 8 KB can show.

§7 refused the whole reply for any of it, so a FASTA or a BAM was never read. The operator's idea
is to keep the value closed and let the reason be free, as `pipeline.yml`'s `reason:` already is.

**The rule.** The value is an id from the offered list; its evidence is free text; **the engine
checks the evidence**.

- **Reply v2** (`builder.characterise.v2`, `CharacteriseReply` v2):
  - `type_id`;
  - `states: [{id, evidence}]`;
  - `measurements: [{id, value, evidence}]`;
  - `undetermined: [id]`;
  - `unmatched: [{kind, name, cite}]`.

  `evidence` is the line of the excerpt that states the property, quoted.
- **An empty list offers nothing.** Where the shown types declare no states (or no measurements),
  the server's schema allows none: `maxItems: 0`. The model cannot invent one there.
- **Admission:**
  - A family or type nothing offered is still **MI0204**. It is the reading.
  - A state or measurement id that was not offered is still **MI0205**. The server's enum makes
    this a provider that ignored the schema.
  - **The evidence check.** Each state and measurement's `evidence` must appear in the excerpt,
    with runs of whitespace compared as one space, and must be at least 3 characters. If it does
    not, that property is **dropped, not refused**: it records nothing, and the rest stands.
  - `undetermined` ids not offered are dropped, never refused: they record nothing.
  - What the prompt says it saw but cannot place goes to `unmatched` (stored only, for #236).
- **What the check is, and is not.** It proves the quoted line is in the file. It does not prove
  the line means what the model says. That second part is what tier 3's *check the premise* and
  the label *read by AI* are for.
- **Where evidence goes.** It is checked in the job and kept only where the reply already is
  (`ai_invocation.response`, #238's question). **It never enters a fact, the session's reading,
  or `pipeline.yml`**: those keep the id and *read by AI*. Showing the quote on the card would
  store a person's file content in the session, which is a decision for #238, not made here.

This replaces options (a), (b) and (d) on #244. It is built by
`docs/superpowers/plans/2026-10-04-characteriser-5-evidence.md`, before plan 3's last task.

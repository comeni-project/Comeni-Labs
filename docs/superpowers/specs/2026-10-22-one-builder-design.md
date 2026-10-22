# One builder: the conversation and the canvas as one page

**Issues:** #395 (one builder), with #391 (Describe's questions), #392 (a conversation between
the engine's asks), #393 (a summary when a build finishes) and #394 (the pipeline file, file
first) folded in. Parent: #370. **Status:** design, awaiting the operator's approval.
**Branch:** stacked on `redesign-walk-fixes` (itself on `redesign-board-match`).

## Why

The live walk of the redesign (2026-10-22, journal entry of that date) showed a product that
works but is split in two. A pipeline built by talking lives at `/build?session=`; a pipeline
drawn by hand lives at `/build?draft=`; they are different components with different canvases,
and the moment a person edits a conversation-built pipeline by hand it stops being one: the
draft becomes `ownership = "manual"`, the conversation's frame is no longer drawn, and later
corrections fork to a linked draft. The operator's verdict: *the old session and fork is kind
of stupid*.

What building should feel like, in the operator's words: **a chat between the researcher and
the AI, where the researcher can learn and be guided** — defining things by talking, and
asking why values are the way they are. It is for **researchers first-hand**: depth stays
available; the problem is clutter, not too much information.

## Goals

1. **One builder.** One page, one canvas, one pipeline, with **every** feature of the manual
   builder and **every** feature of the conversation builder. A merge, not new features.
2. **One way to change a pipeline.** The engine and the AI change the pipeline through the same
   edit operations a person's hands use. What differs is who is recorded as deciding.
3. **No fork.** A hand edit to a conversation-built pipeline lands in that pipeline and is
   recorded in its conversation as the person's decision.
4. **The chat leads, and feels like a chat.** The engine's questions are messages with built-in
   answers. The person can say anything at any time and gets a response. Nothing elsewhere on
   the page changes without the chat saying so.
5. **Describe's questions are readable** (#391): hierarchy, not cutting.
6. **The build ends with a hand-over** (#393).
7. **The pipeline file shows the file** (#394), including the Nextflow it compiles to.

## Non-goals

- New editing capabilities, new AI points, or new kinds of model call.
- New tiers or new rules. The resolver gains only the three kinds of person intent below.
- Accounts, protection levels above 0, or the forge (#360).
- Runs, Settings and Home beyond the links that open a pipeline.

## Anti-goals (would be a failure even if it works)

- The model deciding anything the engine decides, or a model's contribution that is not
  visible and reviewable (CLAUDE.md: *a model's contribution must remain visible*).
- A change on the canvas, in *What was understood* or in the file that happens silently.
- A chat that refuses to answer because a question is pending.
- Losing any manual-builder or conversation-builder feature in the merge.
- Simplifying for its own sake: a researcher must still reach what a file is, why it is asked,
  which steps read it, the rule behind a value and its citation.

## Constraints (from the code and the invariants; verify, do not repeat blindly)

- **The engine decides; the model phrases** (`docs/design/authoring-protocol.md`). Typed words
  that would change something become offered changes the engine checks (`chat.v7`, heard vs
  offered); a tier-4 answer stays flagged for review (invariant 6).
- **Provenance is kept** for every value: why, who answered, which layer. Replays use recorded
  decisions; the same inputs and decisions give the same output.
- **A session moves only by a drawn arrow**, one command per transaction through
  `mendel_api/services/session.py`. Existing seam: `RecordEdit` (`mendel_authoring/commands.py`)
  behind `POST /api/pipeline/authoring/{id}/edits`.
- **Today's fork machinery** to retire or reuse: `draft_mutations.save_in` (MI0217 while
  authoring; `ownership = "manual"` on a semantic edit), `authoring_canvas` drawing no frame for
  a manual draft, `Command.FORK_CORRECTION`, `PipelineDraft.forked_from` and its fork columns.
  **No backward compatibility before v0.1.0**: old forked drafts need not be migrated into
  their parents; they may stay as separate pipelines.
- **Emission exists:** `GET /api/pipeline/drafts/{id}/bundle` and `/gate` produce the Nextflow;
  *Compile it* uses them rather than a new emitter. Repair changes the IR and re-emits; the
  page never edits generated Nextflow.
- Stored JSON shapes are versioned (`shape_versions.py`); a shape change needs a migration and
  every writer restarted (journal trap, 2026-10-22).

## Decided (by the operator, in this conversation)

### One builder (#395)

- `/build` is one component for every pipeline. A pipeline started by drawing simply has an
  empty conversation; the person can start talking at any time. A pipeline started by talking
  can be edited by hand at any time.
- **All manual features stay**: add a step, wire ports, swap a tool, settings, delete, drag,
  tidy, fit, minimap. **All conversation features stay**: the step line, the step on offer
  (dashed), question cards, alternatives and previews, the *Assistant* tab, motion, review
  states, the header's status and *needs you* chip.
- The AI and the engine apply their changes through the same edit operations as a person; the
  record says who (person, engine rule, model) and why.
- **A hand edit is the person's decision** in the same pipeline: recorded as theirs, not asked
  again, and what depends on it is re-checked by the engine as a correction is today. The fork
  is removed.

### Structural hand edits are intent the engine honours (operator: A, then A1)

Every hand edit is allowed at any time and **kept through every re-plan**. The operator chose
the long-term design (A1) over replaying edits as patches (A2): a structural edit is read as
**intent in the goal**, so the engine plans around it rather than re-applying a patch to a plan
that has changed shape.

| Hand edit | Read as | Mechanism |
|---|---|---|
| add a step making a new output | also want *X*, made by *Y* | `want` + `ProducerPin` (exist) |
| remove a step whose output was wanted | no longer want *X* | retract want (exists) |
| remove a step filling an optional role | no *role* here | **new**: a person's role absence, the same semantics as a rule's `presence: absent` (`resolve.py`, `absent_roles`) |
| remove a step the plan needs | not *contract* at this site | **new**: `ProducerExclusion(site, contract)`; the router takes the next candidate, or the conflict is asked |
| rewire a port, or insert a step between two | feed this port from *Y* | **new**: a person's source pin, beside the tie-only `SourceDecision` |
| swap a tool, type a value | as today | `ProducerPin`, parameter answer (exist) |
| drag, tidy, fit | layout only | no decision |

- **The reading is visible before it counts.** The chat says how an edit was read ("So you never
  want trimming here — right?"), composed by the engine, and the person confirms or corrects it;
  it is then recorded as the person's decision, at tier 4 where it overrides the engine (as a
  `ProducerPin` is), with who and when.
- **Conflicts are asked, never resolved silently**: an exclusion with no other candidate, a role
  absence a wanted output needs, a source pin whose types no longer match after a re-plan.
- **No new place to keep them**: the three new kinds live in the goal's constraints beside
  `producers`, in the decision rows like the existing families, so replay stays goal-based.
- During the walk, a structural edit is read and confirmed in the chat like any other change;
  the step on offer is re-planned against the new intent.

### The chat (#392), Describe's questions (#391) and the build's offers

- **One stream, from the first sentence to the last step** (recommended by Claude, operator
  asked for the user's best). Describe asks in the chat, and so does the build: a step on offer
  is a message ("I'd add STAR_ALIGN next — here's why") with *Add it*, *Why this one?* and the
  alternatives built in, while its dashed step highlights on the canvas. The separate *Step* and
  *Assistant* tabs go. Kept from the *Step* tab: **the step line, as a slim progress strip pinned
  above the chat** (*Step 3 of 5*, each step clickable), and **a step opened from the canvas**,
  shown over the chat with a × (its settings, questions and tools, as the *Question* board
  draws it); closing it returns to the conversation.
- **The chat leads.** The engine's questions arrive as **messages with built-in controls**: the
  question at a readable size; answer buttons, each with its one-line note (as the *Question*
  board draws them); *upload a sample* where a sample can answer it.
- **Hierarchy, not cutting.** *What is this?*, *which steps read it* and the explanation stay,
  one click away or below in a quieter style. The provenance tags (*asked by the engine*,
  *phrased for you*, *curated*, *engine*) fold into **one** quiet line.
- **The person can say anything at any time.** A question gets an answer; a statement becomes an
  offered change the engine checks; the pending question stays answerable and is never skipped
  or guessed.
- **Every change outside the chat is announced in the chat**, with a pointer to where it
  happened — a *What was understood* row, a canvas step, a value — and that place highlights
  briefly. *Other parts can update, but explicitly.*
- ***What was understood* stays as the record**: a row per fact with its source (*you said*,
  *measured*, *convention*), the board's *From "…"* line, and readable values rather than raw
  type ids. A *needs you* row, clicked, brings its question back in the chat.

### The pipeline file (#394)

- The page is for **reading the file, asking why a value is what it is, and downloading it**.
- **The file takes most of the page**; each value line carries a small mark of how it was
  decided (*you said*, *convention*, *measured*, *read by AI*, *optional*, *needs you*).
- **Clicking a line opens its reason beside it**: value, who decided, the reason in words, the
  citation small, and *Change it* / *Ask about it in the chat*.
- **The Nextflow is inspectable**: `main.nf` and `nextflow.config` beside `pipeline.yml`, behind
  a **Compile it** action with visible progress, using the existing emission.
- Counts become one strip at the top; a count filters the file. Download stays one button.
- The 2026-10-22 sketch was rough by the operator's own reading; the layout is designed in the
  browser against the identity before it is built (see *Left to the builder*).

## My calls (the operator handed these over; check while reading)

- **The hand-over message (#393)** is composed by the engine from its records, no model call:
  (1) what the pipeline is — input to output, its steps named in order; (2) how its values were
  decided — counts by evidence (#397), each count opening its values; (3) what still needs you,
  each with a button that opens it (Run stays locked, #385); (4) what next — *Run it*, *Look at
  the pipeline file*, or keep asking.
- **Announcements are engine-composed** from what was recorded ("Got it, 150 bp — added to what
  I understood"), so the engine's decision logic is unchanged; the model words questions,
  reads answers and explains, as today.
- **One written design, a plan per stage**, each written when its stage starts: (1) structural
  intent in the engine (A1, pure resolver work), (2) one builder and no fork, on top of it,
  (3) the chat as one stream and Describe, mockups first, (4) the hand-over, (5) the pipeline
  file, mockups first.
- **Old forked drafts stay separate pipelines** (no migration back into a parent).

## Left to the builder

- How the two components merge in code (which survives, what is extracted), provided no
  feature is lost — **inventory both builders' features first** and keep the list in the plan
  as a checklist each stage ticks.
- Whether the engine's changes call the draft-edit service directly or go through `RecordEdit`,
  provided every change is one recorded command with its author.
- The visual design of the chat's question messages and of the pipeline file page: mockups in
  the browser, compared with the operator at the intended viewport, before building, within
  `docs/explanation/visual-identity.md`. The *Question* board is the reference for answer rows.
- Message wording, following `docs/design/voice.md`.

## Open questions for the plan to settle (not product choices)

- Which existing tests and guards encode the fork and `ownership = "manual"`; they change with
  this design and are listed in the plan, not silently deleted.

## How we will know it worked

- A walk with a real model: describe, answer in the chat, ask an unrelated question mid-way and
  get an answer, edit a step by hand mid-build and see the chat say so, finish and read the
  hand-over, open the pipeline file, compile, read `main.nf`, download.
- The same pipeline opened from Home, from ⌘K and by URL is one page with every feature.
- Every manual-builder and conversation-builder feature on the inventory checklist still works.

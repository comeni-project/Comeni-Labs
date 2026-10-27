# One builder, plan 3: the chat as one stream, and Describe

**Issues:** #395 (one builder), with #392 (a conversation between the engine's asks), #391
(Describe's questions) and #399's three findings. Parent design:
[`2026-10-22-one-builder-design.md`](2026-10-22-one-builder-design.md), whose section *The chat
(#392), Describe's questions (#391) and the build's offers* this stage builds. **Status:** design,
awaiting the operator's approval. **Branch:** `one-builder-3`, off `main`.

**Mockups** (brainstorm fragments, drawn at desktop width; the 390 px view is on the last):
`.design/one-builder-3/one-stream.html`, `question-follows-you.html`, `describe.html`,
`step-and-phone.html`. They are content fragments, not full pages: open them through the
brainstorm companion, or read them as HTML. Their chat replies are placeholders, not capability
claims.

## Why

The parent design decided that building is **a chat between the researcher and the AI, where
the researcher can learn and be guided**, and that the chat leads. Today the build page splits
that across a *Step* tab and an *Assistant* tab (`BuildPanel.tsx`), Describe puts the
conversation at the bottom of a column under a *What it needs* card the operator judged poor
(#391), and the composer refuses input while any model call is in flight (#392).

That last point is narrower than #392's wording. The composer is disabled by `pendingTurn`
(`LivingSurface.tsx`, `composerDisabled`): **any** assistant turn in the `pending` state, which is
a model call running, not a question being open. While a question is open and nothing is running,
typing works, and `chat.v7` already answers an unrelated question in words. On gemma3:12b each
call takes about 20 s, and gathering chains them (read the answer back, phrase the next question),
so in a walk the box is locked most of the time. That lock is what the operator hit.

## Decided by the operator (2026-10-27)

1. **Queue, for now.** The composer never locks. A message sent while the engine or a model is
   working appears in the chat at once, marked *waiting*, and is handled **in order** once the
   current work finishes. Interrupting a call in flight (B) and answering pure questions in
   parallel (C) were rejected: B needs provider cancellation in `comeni-ai` and leaves half-states
   (a question with no words); C needs a classifier call first and breaks the session's one
   command at a time.
2. **What typed words may change is unchanged.** #337's rule stands: before the goal is confirmed,
   a change that quotes the turn being answered is *heard* and recorded; after, every change is
   *offered*. #392's protocol question reduces to *when* words are read, which (1) answers.
3. **The open question follows you** (A and C combined). While a question is the newest thing in
   the chat it is a **full card**: the question, why it is asked, each answer with its one-line
   note, *What is this?* and *which steps read it* one click away, and the provenance tags folded
   into one quiet line. Once anything is said after it, the card in the history collapses to a
   one-line pointer (*Asked: which mouse genome to align to · see it*) and the question **docks
   above the composer** as a compact bar: its title, its answers as chips, and *show the full
   question* (which scrolls back to the card). The dock clears when the question is answered,
   wherever.
4. **Describe in the same frame.** One layout from the first sentence to the last step: the chat
   is always the right-hand column. Before there is a canvas, the left side is **What was
   understood**: the person's sentence quoted on top, then the record rows (as the *Describe*
   board draws them and the current page already renders well). When building starts, the left
   side becomes the canvas and the chat does not move.
5. **A step opened over the chat.** Clicking a step on the canvas or in the step strip opens a
   step view **over the chat column** (the canvas stays visible, the step highlighted), with ×
   and *‹ Back to the conversation*. It shows the step's values grouped by how they were decided
   (needs you, measured, settled by a rule — folded), its tools (*Why this tool?*, *Swap for
   another*, *Remove step*), and keeps the composer as *Ask about this step…*.
6. **Phone (390 px):** the chat is the main view, with *Canvas* and *Understood* as tabs beside
   it; the dock and the queue look as on desktop, the dock folded to one line that opens on tap.

## Goals

1. The *Step* and *Assistant* tabs are replaced by **one stream** with a **step strip** pinned
   above it (*Step 3 of 5*, each step clickable; during Describe it reads *Describing*).
2. **The composer is never disabled by work in flight.** It stays disabled only where it is
   today for other reasons: a retired session, and the `stopped` phase (whose hint already says
   to correct an answer).
3. **Queued messages** show at once as the person's turn, marked *waiting*, and are answered in
   the order sent, each read against the session **as it stands when its turn comes**.
4. **Every engine question is a chat message** in the form of decision 3, during Describe and
   during the build alike. The *What it needs* card (`Waiting.tsx`'s gap rendering on Describe)
   goes; so do the step offer's separate panel and the Step tab's card.
5. **The step on offer is a message** (*I'd add STAR_ALIGN next — here's why*) with *Add it*,
   *Why this one?* and the alternatives, its dashed node highlighted on the canvas.
6. **Every change made outside the chat is announced in it** by one engine-composed line naming
   what changed and linking to where (a *What was understood* row, a canvas step, a value); the
   place it links to highlights briefly. This covers answers given in the step view, canvas hand
   edits, measured facts from a sample, and corrections made in *What was understood*.
7. **What was understood** stays the record (#395's design): a row per fact with its source
   chip, the board's *From "…"* line, readable values. A *needs you* row, clicked, brings its
   question back (scrolls to the card, or opens the dock).
8. **Start building** moves to the top bar on Describe and says how many questions are left.
9. #399's findings: an empty new pipeline's chip does not say *Complete*; the empty canvas on a
   drawn pipeline does not say *Confirm the goal on the right*; the *from your edit* reading is
   not cramped or clipped (it becomes a chat message like any other offer).

## Non-goals

- New AI points, prompts or model-call kinds. `chat.v7`, `ask.v3` and `readback.v2` stay as they
  are; any wording change to them is a separate, measured change (`tools/measure_prompts.py`).
- Changes to what the engine decides, to tiers, rules or the heard/offered rule.
- Cancelling a provider call, or running two calls for one session at once.
- The hand-over summary (#393, stage 4) and the pipeline file (#394, stage 5).
- A *Measure it instead* action on a setting: nothing backs it (board-match pass, 2026-10-21).

## Anti-goals

- A question that silently disappears: scrolled off, skipped or guessed because the person
  chatted.
- A change anywhere on the page with no line in the chat.
- A queued message answered against stale state, or answered out of order.
- Losing a feature of today's Step tab, Assistant tab or Describe page in the merge (the parent
  design's inventory checklist applies).
- Cutting depth: *What is this?*, *which steps read it*, the reason and the citation stay
  reachable in one click.

## Constraints (verified against the code on 2026-10-27; re-verify before relying on them)

- **A said message already records two rows at once** (`stages/describe.py`, `record_said`): the
  person's turn and a `pending` assistant turn, then queues `answer_authoring_turn` on
  `arq:queue:ai` (`stages/_jobs.py`, `turn`). So the server already accepts a message while
  another turn is pending; the lock is in the browser only.
- **A reply is grounded when its job starts** (*corrected while planning, 2026-10-27*):
  `describe.turn_context` reads the phase, the draft revision and the goal at that moment, and
  `answer` refuses a reply as *late* only when the draft moved during its own call. A queued
  message is therefore read against the session as it stands when its turn comes, without new
  code; `test_authoring_queue.py` guards it. (The decisions it is read against are the ones when
  it was said, `base_decision_revision`, which #337's heard/offered rule relies on.)
- **Order is not guaranteed by the queue today.** `ai_max_jobs` defaults to 1 but is
  configurable (`COMENI_AI_MAX_CONCURRENT_JOBS`), and phrasing and read-back jobs share the
  queue. Per-session order must hold whatever that setting is.
- **Typed words are a command only where the diagram draws one** (`_said`: `DESCRIBE` at
  understanding, `REPLY_IN_WORDS` at a gap); elsewhere they are a chat turn that moves nothing.
  A queued message must be routed by the phase **when it is handled**, through the same check.
- **Receipts exist** (`authoring/types.py`, `Receipt`: what was committed, at a revision, by an
  actor). Announcements (goal 6) are built from what is recorded; the engine composes them, no
  model call (parent design, *My calls*).
- Invariants: the engine decides and the model phrases; provenance (who answered, why, which
  layer) is kept for every value; one command per transaction through
  `mendel_api/services/session.py`; tier 4 stays flagged.
- The visual identity is `docs/explanation/visual-identity.md` and `frontend/src/tokens.css`; the
  *Question* board is the reference for answer rows. Known CSS traps: `.living`/`.tbl` beat
  same-specificity Tailwind utilities; `px-4` is the 10 px scale; `#` plus hex digits anywhere in
  frontend source fails `tokens.test.ts`.

## Left to the builder

- **How per-session order is enforced** (a per-session lock in the job, chaining the next job
  when one finishes, or another mechanism), provided order holds at any `ai_max_jobs` and a
  crashed job does not wedge the session.
- **How a queued turn is grounded at start**: re-reading the base revision when the job begins,
  or recording it then rather than at `record_said`. A message that is still *late* after that
  (the draft moved during its own call) keeps today's `failed` handling.
- **How the dock and the card share state** with the existing `Waiting.tsx`, `StepLine.tsx` and
  `Chat.tsx`: what is extracted, what is deleted. Inventory both panels' features first and keep
  the list in the plan as a checklist.
- Wording of announcements, the dock and the *waiting* mark, following `docs/design/voice.md`.
- Exact sizes and spacing, within the identity and the mockups.

## My calls (the operator handed these over; check while reading)

- **After an off-topic reply the question is not re-posted** as a new message; the dock does that
  job (decision 3), so the thread holds no duplicates.
- **The pace choice** (step by step, or all at once) becomes the last question in the Describe
  chat when the installation asks it every time, rather than two cards on the page. When the
  pace is fixed in Settings the chat says so in one line with a link, as the page does today.
- **Ask about this step…** sends the message to the chat with the step attached, then closes the
  step view so the reply is seen.
- **Answering in the step view and in the chat is one answer**: both go through the same command;
  the other surface updates and the chat announces it.
- **During the build, *What was understood* is a switch on the left side**: *Canvas* | *What was
  understood*, the same pair the phone shows as tabs. The Step tab that holds it today goes, and
  the record must stay one click away.
- **Only the composer stops locking.** Answer buttons, corrections and step tools keep today's
  per-control rules (for example, an answer is not clickable while its own question is still
  being worded or read back); they are commands the API runs at once, not model calls, so they
  have nothing to queue behind.
- **A queued message cannot be edited or withdrawn** in this stage; it is shown as sent.

## How we will know it worked

- A walk with a real model (gemma3:12b on the RX 7600): describe, add a sample, ask two unrelated
  questions while a question is open and while a model call is running; each is answered in
  order, the open question docks and stays answerable, and nothing is skipped.
- Answer a question in the step view and see the chat announce it and the dock clear.
- A canvas hand edit mid-build is announced in the chat, and the step highlights.
- Desktop at 1440×900 and 390 wide, compared with the mockups; light and dark.
- Every feature on the Step/Assistant/Describe inventory still works.
- Tests: a message sent while a turn is pending is answered after it, in order, and grounded on
  the later revision (a regression guard that fails against today's browser lock and against an
  out-of-order answer); the composer is enabled while a turn is pending.

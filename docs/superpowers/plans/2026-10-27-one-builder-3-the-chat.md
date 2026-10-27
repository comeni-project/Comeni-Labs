# One builder, plan 3: the chat as one stream, and Describe — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The build page and Describe become one frame with one conversation on the right: the
composer never locks (messages queue), every engine question and offer is a message, the open
question docks above the composer once you talk past it, a step opens over the chat, and every
change made elsewhere is announced in the chat.

**Architecture:** The server already records a message and its pending reply at once and grounds
each reply when its job starts (`describe.turn_context` reads the phase, revision and goal then);
it gains only **per-session order** for reply jobs, the time a proposal was asked (`asked_at`),
and a link on receipts (`about`). The client replaces `BuildPanel`'s *Step* / *Assistant* tabs
with a `ChatPanel` (step strip, `Stream`, `QuestionDock`, composer, and a `StepSheet` over the
stream), and Describe renders inside the same frame with *What was understood* on the left.

**Tech Stack:** Python 3.12, pydantic v2, SQLAlchemy + Alembic, arq, FastAPI, pytest; React 19,
TanStack Query, Tailwind, vitest.

**Spec:** `docs/superpowers/specs/2026-10-27-one-builder-3-the-chat-design.md` (mockups in
`.design/one-builder-3/`). Parent: `docs/superpowers/specs/2026-10-22-one-builder-design.md`.

## Global Constraints

- **The engine decides; the model phrases.** No new AI point, prompt or model-call kind;
  `chat.v7`, `ask.v3`, `readback.v2` unchanged. Announcements are engine-composed receipts.
- **#337's heard/offered rule is unchanged.** A queued message is read with the decisions as they
  stood when it was said (`base_decision_revision`, already recorded) and the draft as it stands
  when its job starts.
- One command per transaction through `mendel_api/services/session.py`; tier 4 stays flagged;
  provenance kept for every value.
- Stored JSON shapes are versioned: widening `Receipt` moves `pipeline_authoring_turn` from
  shape 3 to **shape 4** with an identity upgrade migration after `7ea478ea7f3b`, and the golden
  regenerated (`COMENI_WRITE_GOLDEN=1`), as plan 1 did. Restart `mendel-worker`, rebuild
  `ai-worker`, then `make migrate`; `make test-db` again before `make check`.
- Generated clients in `frontend/src/api/` are rebuilt with `make client`, never hand-edited.
- Copy follows `docs/design/voice.md`. Frontend traps: `#` plus hex digits anywhere in source
  fails `tokens.test.ts` (write *issue 392*); `.living`/`.tbl` beat same-specificity utilities;
  `px-4` is the 10 px scale, a page gutter is `px-[16px]`.
- UI is checked in a browser at 1440×900 and 390 wide, light and dark, against the mockups.
- Python tests through `make test-db` / `make test`; one pytest run at a time. Tick steps as done;
  record deviations at the end.

## Feature inventory (tick each as it is confirmed in the new panel)

From `BuildPanel.tsx` (*Step* tab): step line → strip; step on offer with alternatives and
previews; gap, pacing, goal and disagreement cards; *Measured from your sample* above the next
question; a step opened from the canvas (name, module, open and optional values as questions,
*Change this step* tools, setting requests); *Still needs you* list per step; *Nothing is waiting
for you*; *From your edit* readings; *From the conversation* suggestions, setting requests and
change sets; *What was understood* (`CurrentFacts`) with correct and release; stopped-phase
*Correct current answers*; resolving notice; notices (alert, retired, no model, outdated).
From the *Assistant* tab: transcript, pending line, late-answer line, retry on an unreachable
provider, pointer lines. From `DescribePage.tsx`: the sentence quoted, status chip, the goal
checked line by line, pace (asked or fixed, with the Settings link), *What was understood*,
conversation, composer.

- [x] every item above has a home after Task 7:
  step line → behind the strip's *Step n of m* (`StepStrip` + `StepLine`); step on offer, gap,
  pacing, goal and disagreement cards, sample result, stopped and resolving lines → the stream's
  newest message (`Stream` → `Waiting`); opened step → `StepSheet` over the stream; *Still needs
  you* → an engine line with a button per step after the stream; *Nothing is waiting* → removed
  (absence is absence); *From your edit* and *From the conversation* → after the stream;
  *What was understood* / *Correct current answers* → `Understood`, the left side's switch;
  notices → top of `ChatPanel`; transcript, pending and late lines, retry → `Chat` in the stream;
  pointer lines → removed (the cards are in the stream); Describe's parts → Task 8.

## Review Focus

1. **Two messages sent within a second while a reply is running**: both answered, in the order
   sent, neither *late*. Test in Task 1.
2. **A queued message that answers the open question** (typed while its question was still being
   worded): routed as the question's answer when it is handled, not as chat. Test in Task 1.
3. **The open question answered from the step view while it is docked**: the dock clears and the
   chat announces it once. Test in Task 6.
4. **Reload mid-queue**: the *waiting* marks and the dock come back from the server's turns and
   `asked_at`, not from browser state. Test in Task 3.
5. **A phone with the dock open and the keyboard up**: the composer stays reachable (browser
   check in Task 9; the dock folds to one line under 640 px).

---

### Task 1: Replies to a session's messages run in order

**Files:**
- Modify: `packages/mendel-api/src/mendel_api/services/authoring_jobs.py` (`answer_authoring_turn`)
- Modify: `packages/mendel-api/src/mendel_api/stages/describe.py` (add `earlier_pending`)
- Modify: `docs/superpowers/specs/2026-10-27-one-builder-3-the-chat-design.md` (*Constraints*)
- Test: `packages/mendel-api/tests/authoring/test_authoring_queue.py`

**Interfaces:**
- Produces: `describe.earlier_pending(session_id: str, seq: int) -> bool` — an assistant turn of
  this session with a lower `seq` is still `pending`.

- [ ] **Step 1: Write the failing tests** (harness: `_model` / `_typed` as in
  `test_authoring_chat_changes.py`; fixtures `clean`, `_gathering`, `_pending_for`)

```python
def test_a_second_message_waits_for_the_first_reply(clean, monkeypatch):
    sid = _gathering(want=["counts.matrix"])
    _model(monkeypatch, {"say": "Both describe genes."})
    first = facade.perform(commands.Say(sid, "what is a GTF?")).result
    second = facade.perform(commands.Say(sid, "and a GFF?")).result
    assert second > first
    with pytest.raises(arq.Retry):
        asyncio.run(authoring_jobs.answer_authoring_turn({}, sid, second))
    assert _state(sid, second) == "pending"
    asyncio.run(authoring_jobs.answer_authoring_turn({}, sid, first))
    asyncio.run(authoring_jobs.answer_authoring_turn({}, sid, second))
    assert [_state(sid, s) for s in (first, second)] == ["answered", "answered"]

def test_a_queued_message_is_grounded_on_the_draft_when_it_is_read(clean, monkeypatch):
    # the first reply records a heard fact, which moves the draft; the second is not late
    sid = _gathering(want=["counts.matrix"])
    _pending_for(sid, "read_length")
    _model(monkeypatch, {"facts": [{"subject": "read_length", "value": 150, "quote": "150 bp"}]})
    first = facade.perform(commands.Say(sid, "they're 150 bp")).result
    second = facade.perform(commands.Say(sid, "thanks")).result
    asyncio.run(authoring_jobs.answer_authoring_turn({}, sid, first))
    _model(monkeypatch, {"say": "You're welcome."})
    asyncio.run(authoring_jobs.answer_authoring_turn({}, sid, second))
    assert _state(sid, second) == "answered"

def test_a_message_typed_while_its_question_is_worded_answers_it(clean, monkeypatch):
    sid = _gathering(want=["counts.matrix"])
    _pending_for(sid, "paired")  # the gap row exists; its words may still be pending
    _model(monkeypatch, {"facts": [{"subject": "paired", "value": True, "quote": "paired"}]})
    seq = facade.perform(commands.Say(sid, "they're paired")).result
    asyncio.run(authoring_jobs.answer_authoring_turn({}, sid, seq))
    assert _value(sid, "paired") is True
```

`_state(sid, seq)` reads `facade.read(sid)["turns"]`; `_value` as in the chat-changes test.

- [ ] **Step 2: Run them** — `make test-db`, then
  `MENDEL_TEST_DATABASE_URL=postgresql+psycopg://mendel:mendel@127.0.0.1:5442/mendel uv run pytest packages/mendel-api/tests/authoring/test_authoring_queue.py -v`
  (the URL is `TEST_MENDEL_URL` in the `Makefile`; check it before running). Expected: the first FAILs (no `Retry`); note
  whether the other two already pass. If they do, they stay as guards of the grounding the spec
  relies on, and the guard ledger records that they passed before the change.

- [ ] **Step 3: Implement** `earlier_pending` (one `select exists` on `PipelineAuthoringTurn`), and
  at the top of `answer_authoring_turn`, after the `context is None` check:
  `if describe.earlier_pending(session_id, seq): raise arq.Retry(defer=2)`. Comment: per-session
  order must hold at any `ai_max_jobs`; a crashed earlier job leaves its turn pending, which
  `Retry` respects until arq's `max_tries` ends it (the turn then stays pending and the person's
  retry path is today's). Check `AIWorkerSettings.max_tries`; if it would wedge a session for
  longer than one job timeout, say so in *Deviations* and bound it.

- [ ] **Step 4: Run the tests** — Expected: PASS.

- [ ] **Step 5: Correct the spec's constraint**: replace the bullet beginning *A turn's answer is
  refused as late* with what the code does: the reply is grounded when its job starts
  (`turn_context`), and *late* means the draft moved during its own call. Record it in the spec as
  *corrected while planning (2026-10-27)*.

- [ ] **Step 6: Guard ledger** — add the order test to `tests/fixtures/guard-ledger.md`, with its
  failure against the code before Step 3.

- [ ] **Step 7: Commit** `fix(authoring): a session's replies run in the order its messages were sent (#392)`

### Task 2: The server says when a question was asked, and what a receipt is about

**Files:**
- Modify: `packages/mendel-api/src/mendel_api/routes/authoring.py` (`AuthoringProposalView.asked_at: str`)
- Modify: `packages/mendel-api/src/mendel_api/services/session.py` (`pending_proposal` gains `"asked_at": pending.created_at.isoformat()`)
- Modify: `packages/mendel-api/src/mendel_api/authoring/types.py` (`Receipt.about`)
- Modify: `packages/mendel-api/src/mendel_api/shape_versions.py` (`pipeline_authoring_turn`: 4)
- Create: `packages/mendel-api/migrations/versions/<rev>_receipts_say_what_they_are_about.py` (identity upgrade, down_revision `7ea478ea7f3b`)
- Modify: golden shapes; `frontend/src/api/` via `make client`
- Test: `packages/mendel-api/tests/authoring/test_authoring_routes.py`, the shape guard tests

**Interfaces:**
- Produces: `AuthoringProposalView.asked_at: str` (ISO 8601, the proposal's `created_at`).
- Produces: `class ReceiptAbout(BaseModel): node: str | None = None; subject: str | None = None`
  and `Receipt.about: ReceiptAbout | None = None` — the canvas step or the *What was understood*
  subject the receipt changed.

- [ ] **Step 1: Failing tests** — a session read with a pending proposal carries `asked_at` equal to
  the row's `created_at`; a `Receipt(..., about=ReceiptAbout(node="STAR_ALIGN"))` round-trips
  through `parse_block`; the shape guard refuses a shape-3 turn row written after the bump.
- [ ] **Step 2: Run** — Expected: FAIL (`asked_at` missing; `about` unknown).
- [ ] **Step 3: Implement** the fields, the shape bump and the identity migration; set `about` on
  the receipts already written in `stages/correcting.py` (the corrected subject),
  `stages/building/walk.py` and `stages/building/amending.py` (the step's node).
- [ ] **Step 4: Run** the tests, `COMENI_WRITE_GOLDEN=1` for the golden, then `make client`.
- [ ] **Step 5: Commit** `feat(authoring): proposals say when they were asked; receipts say what they changed`

### Task 3: The composer never locks, and queued messages say *waiting*

**Files:**
- Modify: `frontend/src/build/living/LivingSurface.tsx` (`composerHint`, `talk.composerDisabled`)
- Modify: `frontend/src/build/living/authoringReducer.ts`, `useAuthoringSession.ts` (`saying: string | null` → `sending: string[]`)
- Modify: `frontend/src/build/living/Chat.tsx` (person turns marked waiting)
- Test: `frontend/src/build/living/Composer.test.tsx`, `Chat.test.tsx`, `authoringReducer.test.ts`

**Interfaces:**
- Produces: `queued(session: AuthoringSession): Set<number>` in `format.ts` — the seqs of person
  turns whose reply is pending **and** is not the oldest pending reply (those wait in line; the
  oldest is being answered and shows the working line).

- [ ] **Step 1: Failing tests**
  - the composer is enabled while a turn is `pending` (render `LivingSurface` with a pending
    turn; `getByRole("textbox")` not disabled) — the regression guard for #392;
  - `composerHint` with a pending turn is `"Ask anything, or answer in your own words"`;
  - with two pending replies, the later person turn shows *waiting: I'll answer as soon as I
    finish the step above*, the earlier does not; re-rendering from the same session (a reload)
    shows the same marks;
  - two sends before either POST returns keep both texts in `sending`, in order.
- [ ] **Step 2: Run** `cd frontend && npx vitest run src/build/living` — Expected: FAIL.
- [ ] **Step 3: Implement**: `composerDisabled = session.retired || session.phase === "stopped"`;
  drop the pending branch of `composerHint`; `sending` is appended on send and a text is removed
  when the session's turns contain it; `Chat` renders `sending` as today's *sending…* items and
  `queued(session)` turns with the waiting line.
- [ ] **Step 4: Run** — Expected: PASS. Guard ledger: the composer test, failing on `main`.
- [ ] **Step 5: Commit** `feat(build): the composer never locks; messages queue (#392)`

### Task 4: One stream — the question in the conversation, then docked

**Files:**
- Create: `frontend/src/build/living/Stream.tsx`, `QuestionDock.tsx`
- Modify: `frontend/src/build/living/Chat.tsx` (pointer lines scroll to the card; no *see Step*)
- Modify: `frontend/src/build/living/Waiting.tsx` (rendered by `Stream`, scroll-into-view kept)
- Test: `frontend/src/build/living/Stream.test.tsx`, `QuestionDock.test.tsx`

**Interfaces:**
- Consumes: `AuthoringProposal.asked_at` (Task 2); `WaitingProps` (unchanged).
- Produces: `Stream({ session, waiting, sending, onRetry, onAsk }: StreamProps)` — the turns in
  order, then the waiting card **as the newest message** while no person turn has `at > asked_at`;
  otherwise the card's place shows `Asked: <title> · see it` and `docked(session)` is true.
- Produces: `docked(session: AuthoringSession): boolean` in `format.ts`, and
  `QuestionDock({ proposal, busy, onAnswer, onShow }: …)` — title, answers as chips (the gap's or
  pacing's options), *show the full question*; folded to one line under 640 px, opens on tap.

- [ ] **Step 1: Failing tests**
  - a gap with no later person turn renders as a full card at the end of the log, no dock;
  - a person turn after `asked_at` collapses the card to the pointer and renders the dock with
    the gap's options as buttons; clicking one calls `onAccept(proposal, option)`;
  - *show the full question* scrolls to and expands the card (`scrollIntoView` called);
  - a step proposal docks as *Add it* / *Why this one?* (its primary answers), not its whole card;
  - the provenance line is one line: `asked by the engine · worded by the model · curated explanation`
    (the parts present in the block).
- [ ] **Step 2: Run** — Expected: FAIL.
- [ ] **Step 3: Implement** `Stream` (wraps `Chat` and `Waiting`), `docked`, `QuestionDock`; the
  question card keeps *What is this?* and *which steps read it* (`Explain`) one click away and
  folds the provenance tags into one line, laid out after `.design/one-builder-3/one-stream.html`
  and the *Question* board.
- [ ] **Step 4: Run** — Expected: PASS.
- [ ] **Step 5: Commit** `feat(build): the open question follows you (#392)`

### Task 5: `ChatPanel` replaces the tabs

**Files:**
- Create: `frontend/src/build/living/ChatPanel.tsx`, `StepStrip.tsx`
- Delete: `frontend/src/build/living/BuildPanel.tsx` (after its features are moved; see inventory)
- Modify: `frontend/src/build/living/LivingSurface.tsx`, `StepLine.tsx` (strip reuses its step list)
- Test: `frontend/src/build/living/ChatPanel.test.tsx`, `StepStrip.test.tsx`; update `LivingSurface.test.tsx`, `OneBuilder.test.tsx`

**Interfaces:**
- Consumes: `Stream`, `QuestionDock` (Task 4).
- Produces: `ChatPanel(props)` with `BuildPanel`'s props minus nothing; `StepStrip({ session, steps, onSelect, describing })`
  — *Describing* while `stageOf(session) === "describe"`, else one pill per planned step with
  *Step n of m*.

- [ ] **Step 1: Failing tests** — no `role="tablist"`; the strip shows *Step 4 of 5* and a click
  on a step calls `onSelect(node)`; suggestions, *From your edit* readings, setting requests and
  change sets render **in the stream** as messages after the turn that carried them, with their
  apply / dismiss; *Still needs you* steps render as one engine line with a button per step.
- [ ] **Step 2: Run** — Expected: FAIL.
- [ ] **Step 3: Implement** `ChatPanel`: notices, strip, `Stream`, `QuestionDock` when `docked`,
  composer. Move every `BuildPanel` feature per the inventory; delete `PanelTab` and the unread dot.
- [ ] **Step 4: Run** the whole `src/build/living` suite — Expected: PASS.
- [ ] **Step 5: Commit** `feat(build): one conversation beside the canvas (#395)`

### Task 6: A step opens over the chat

**Files:**
- Create: `frontend/src/build/living/StepSheet.tsx` (from `BuildPanel`'s `editable` section)
- Modify: `frontend/src/build/living/ChatPanel.tsx`
- Modify: `packages/mendel-api/src/mendel_api/routes/authoring.py` / the edit service: a typed value applied through an edit writes a receipt with `about.node`
- Test: `frontend/src/build/living/StepSheet.test.tsx`; `packages/mendel-api/tests/authoring/test_authoring_routes.py`

**Interfaces:**
- Produces: `StepSheet({ node, step, graph, requests, onSetParam, onEdit, onClose, onAsk })`.

- [ ] **Step 1: Failing tests**
  - the sheet groups values: *Needs you*, *Measured*, *Settled by a rule* (folded, *show*);
  - × and *‹ Back to the conversation* call `onClose`; the stream's scroll position is kept;
  - the composer's placeholder is *Ask about this step…*; sending calls `onAsk("<text>", node)`,
    which sends `About STAR_ALIGN: <text>` to the chat and closes the sheet;
  - (server) a value typed in an edit (`RecordEdit` with a typed value) appends one receipt turn
    `Set <setting> to <value> on <NODE>` with `about.node`, `by="person"`;
  - (Review Focus 3) answering the docked question's setting from the sheet clears `docked` after
    the session refreshes, and exactly one receipt is added;
  - (server) a gap answered by a sample appends one receipt `Measured from your sample: <fact>`
    per settled subject, `about.subject` set, `by="resolver"` (goal 6's measured facts).
- [ ] **Step 2: Run** both suites — Expected: FAIL.
- [ ] **Step 3: Implement** the sheet and both receipts, through `_rows.engine_turn`: the typed
  value's in the route that applies it after `RecordEdit`; the sample's where the sample answer
  settles its subjects (`stages/samples.py`).
- [ ] **Step 4: Run** — Expected: PASS.
- [ ] **Step 5: Commit** `feat(build): a step opens over the chat; a typed value is announced`

### Task 7: The left side — canvas or *What was understood*; the phone tabs

**Files:**
- Create: `frontend/src/build/living/Understood.tsx` (the sentence, `AnswerLine`s and `CurrentFacts`, from `DescribePage`)
- Modify: `frontend/src/build/living/LivingSurface.tsx`
- Test: `frontend/src/build/living/Understood.test.tsx`, `LivingSurface.test.tsx`

**Interfaces:**
- Produces: `Understood({ session, declarations, onCorrect, onRelease, disabled, highlight })`;
  `highlight: string | null` is a subject to flash.

- [ ] **Step 1: Failing tests** — during the build a switch *Canvas* | *What was understood* swaps
  the left side; at 390 px (`matchMedia` mocked) the page shows tabs *Chat*, *Canvas*,
  *Understood* with *Chat* first; a *needs you* row clicked opens its question (scroll to card, or
  the dock when `docked`).
- [ ] **Step 2: Run** — Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** — Expected: PASS. Tick the inventory: write beside each item its new home.
- [ ] **Step 5: Commit** `feat(build): what was understood beside the chat; phone tabs`

### Task 8: Describe in the same frame

**Files:**
- Modify: `frontend/src/build/living/LivingSurface.tsx` (no separate describe branch: the frame with `Understood` on the left)
- Modify: `frontend/src/build/living/DescribePage.tsx` → delete once its parts live in `Understood`, `ChatPanel` and the header
- Modify: `frontend/src/build/living/LivingHeader.tsx` (*Start building · n questions left* while describing)
- Modify: `frontend/src/build/living/blocks/GoalCard.tsx` (the record on the left is the goal being checked)
- Test: `frontend/src/build/living/Describe.test.tsx`, `LivingHeader.test.tsx`

- [ ] **Step 1: Failing tests**
  - describing renders the frame: `Understood` left, `ChatPanel` right with the strip reading
    *Describing*; there is no *What it needs* card on the left;
  - a gap question renders in the stream as a card (Task 4), not on the left;
  - while the goal is checked, *Start building* is in the header with *1 question left* when one
    gap is open and is disabled until none is; pressing it confirms the goal (`onAccept(pending, "keep", edited)`);
  - with `building.pacing = ask`, no pace cards render; the engine's pacing question arrives in the
    stream like any question; with a fixed pace, the stream shows one line with the Settings link.
- [ ] **Step 2: Run** — Expected: FAIL.
- [ ] **Step 3: Implement**; delete `DescribePage.tsx`, `Paces`, the `held` ref and `PACE_WORDS`'s
  page copy (moved into the one line).
- [ ] **Step 4: Run** — Expected: PASS.
- [ ] **Step 5: Commit** `feat(build): describe in the same frame (#391)`

### Task 9: Announcements link and highlight; #399's findings; the walk

**Files:**
- Modify: `frontend/src/build/living/blocks/Block.tsx` (a receipt with `about` renders its link)
- Modify: `frontend/src/build/living/LivingSurface.tsx` (`focus` a node / flash a subject for ~1.2 s, the existing `motion.ts` curve)
- Modify: `frontend/src/build/living/LivingHeader.tsx` (#399: an empty pipeline's chip), `LivingCanvas.tsx` (#399: empty-canvas copy), the *Pipeline outdated* notice (no *Step panel*)
- Test: `Block` / `LivingHeader` / `LivingCanvas` tests
- Docs: `docs/notes/journal/2026-10-xx-one-builder-3.md`, `CHANGELOG.md` (mendel-api, frontend), the builder's user page if it names the Step tab (`grep -rn "Step tab\|Assistant tab" docs`)

- [ ] **Step 1: Failing tests** — a receipt with `about.node` renders a link that calls
  `onFocus(node)`, and with `about.subject` one that flashes the row; an empty new pipeline's chip
  is not *Complete*; the empty canvas of a drawn pipeline does not say *Confirm the goal on the
  right*; no copy mentions the *Step panel* (`grep -rn "Step panel" frontend/src` empty).
- [ ] **Step 2: Run** — Expected: FAIL. **Step 3: Implement.** **Step 4: Run** — PASS.
- [ ] **Step 5: Browser check** with the stack (`API_HOST_PORT=8020 DB_HOST_PORT=5433 make dev`,
  `make ai-up OLLAMA_GPU=rocm`) at 1440×900 and 390 wide, light and dark, against the four
  mockups: describe → sample → two questions sent while a reply runs → the dock → answer from the
  step sheet → a canvas Delete → *So you never want … — right?* → build to the end. Review Focus 5
  on the phone width. Note what differs.
- [ ] **Step 6: `make check`, then `make verify`** (the turn shape changed). Comment the outcome on
  #392, #391 and #399.
- [ ] **Step 7: Commit** `docs: one builder plan 3 — journal, changelog, ticked plan (#395)`

## Deviations

(Recorded during execution.)

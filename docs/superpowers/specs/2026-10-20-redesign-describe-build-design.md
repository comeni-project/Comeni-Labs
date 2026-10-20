# Redesign 3 — describe and build adapt to the engine, not a chat

**Issue:** #377 (parent #370). **Status:** approach approved by the operator 2026-10-20 ("the chat
should remain a chat, and the engine works to move the canvas around, or spawn things in the
canvas"; the details are left to the builder). Implemented on `redesign-describe-build`, on top of parts 1 and 2
(`forge-0-remove-old`); plan and deviations: `docs/superpowers/plans/2026-10-20-redesign-describe-build.md`.
**Boards:** `.design/hybrid/Describe.dc.html`, `Build.dc.html` and `Question.dc.html` (rendered
with `.design/_prev.py --dir hybrid`).

## Why

The living builder (`frontend/src/build/living/LivingSurface.tsx`) is a canvas beside one rail,
and the rail (`DecisionLog.tsx`) interleaves three different things in time order: what the person
and the model said, the engine's typed cards (goal, gap, pacing, step proposal, disagreement,
setting request, change set), and a collapsed line for every answered decision. The result is a
chat made of form boxes, where the one thing waiting for an answer is a card somewhere in a
transcript. The engine decides what is asked and the model only phrases and reads, so the screen
should show the engine's current state; the conversation should be a conversation.

## What changes

The page has two stages, decided from the session alone (a pure function, `stageOf(session)`):

- **Describe**, while there is nothing to draw yet: phase `understanding`, `gathering`,
  `goal_review` or `resolving`; the pacing question on offer; or a stop, failure or correction
  before any step was accepted.
- **Build**, otherwise.

### Describe — one column, the board *Describe*

A centred column (max 860 px) in place of the canvas and rail:

1. **What do you want to analyse?** (title role) and the person's first sentence, quoted in a
   panel (the first `person` turn).
2. **The card waiting for you**, drawn as page content rather than in a transcript: the goal
   card (*That's right / Not quite*), a gap card (answer, upload a sample, or leave it open), the
   disagreement card, or the pacing card titled *How do you want to build it?*. While the model or
   the engine is working, a status line says so in the card's place. A stop or failure says why
   and offers what the rail offers today (*Correct current answers*, *Try again*, *Start a new
   analysis*).
3. **What was understood**: the current answers (`CurrentFacts`), open by default, drawn as the
   board's table — a label, the value, and where it came from (*you said*, *measured*,
   *convention*, *needs you*). Correcting a line works as today.
4. **The conversation**, below: the chat (section *Chat* below) with its composer — *Or say it in
   your own words*.

### Build — the canvas and a panel, the boards *Build* and *Question*

The canvas keeps its place and behaviour. The rail becomes a **panel with two tabs**:

- **Step** (default):
  - **The step line**: *Goal* (confirmed, by whom), then every step decided so far, in order, with
    who settled it (`settled`, `you chose`, `model chose`, `skipped`, `answers changed`), then the
    step on offer, highlighted, then *N more steps* from the server's count
    (`progress.active.total − position`). The engine does not send the names of steps not yet
    offered, so they are counted, not named (*absence is absence*). A decided step is a button:
    it selects the step on the canvas.
  - **The card for what is selected or waiting**: the step on offer (`StepProposalCard`, with its
    alternatives and preview) when nothing else is selected; a selected step's tools
    (`StepTools`) and any setting request about it when a drawn step is selected; a gap,
    disagreement or pacing question raised during the build.
  - **From the conversation**: suggestions waiting (`SuggestionCard`) and the change sets and
    setting requests from the model's latest reply. These are engine-checked changes the chat
    proposed; they are confirmed here, not in the chat.
- **Assistant**: the chat, and its composer at the foot of the panel on both tabs. Sending from
  the Step tab, or pressing *Why this one?*, switches to Assistant so the reply is seen. A reply
  that arrives while Step is showing marks the Assistant tab (a dot and an accessible label).

**The canvas follows the engine.** When a new step is offered it is drawn as today (dashed), and
the view pans so that step is on screen; selecting a step from the step line pans to it too. A
pan never zooms and never moves a view the person has already got the step in.

### Chat

The chat shows only speech: the person's turns, and the model's words — narrative, receipts and
notices (a refusal keeps its *Try again*). Every other block in a reply is a single line naming
what it did with a link to it (*Suggested a change to STAR_ALIGN — see Step*), which switches to
the Step tab and selects the step. Answered decisions no longer appear in the chat; their record
is the step line and *What was understood*. *The canvas is still yours* and *Resolving the whole
pipeline once…* stay as status lines.

## Not in this part

- The header, *Pipeline file* and the run sheet (#379); Home and the describe box on Home (#378).
- Any server change. Everything above is read from `AuthoringSessionView` as it is.
- Restyling the cards' insides beyond what the layout needs; they already use the part 1 tokens.

## Constraints

- No model output is applied without the person: change sets and suggestions keep their own
  confirm buttons; the step line only selects.
- Accessibility: the tabs are a `tablist`; the step line is a list; the card waiting for an answer
  receives focus when it changes, as the rail's scroll-to did.
- Layout at 1440, 1000 and 390 px: the build stage stacks the panel above the canvas below
  1000 px, as the rail does today; the describe column has a 16 px gutter at phone width.

## Testing

Vitest, deterministic fixtures (`fake.ts` and the existing session builders), no live model:

- `stageOf`: each phase, pacing on offer, a stop before and after a step was accepted.
- Describe: the sentence, the waiting card (goal, gap, pacing), *What was understood*, the
  composer; no canvas.
- Build: the step line's order and words, *N more steps*, a click selects; the Step tab holds the
  proposal card and the Assistant tab holds none; the chat draws speech and pointer lines only;
  sending switches tabs; an unread reply marks the tab; a change set waits under *From the
  conversation*.
- The canvas pans to a newly offered step (view transform changes) and not when it is in view.
- Existing tests that read the rail are moved to the tab or page that now holds what they check.

Then the browser check: `/build/living?fake=1`, `?fake=guided` and `?fake=collect` at 1440 and
390 px, light and dark, against the three boards in one viewport.

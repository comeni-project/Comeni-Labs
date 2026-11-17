# Builder plan 2: the step menu and its cards, the pipeline file page, canvas polish

Issue #499, under #463. Designed with the operator on 2026-11-14; recorded in the last section of
`docs/superpowers/specs/2026-11-14-builder-agent-design.md` ("Plan 2, after this one"). This page
fixes what that section left to the builder. The operator delegated those calls on 2026-11-15
("keep going until the end of plan 2; stop only for a decision that really needs my attention");
each is marked **(builder's call)** so it can be checked.

## Intent

The builder agent shipped (#463): the chat is a conversation, the canvas is the pipeline. What is
left is the parts of the page that still feel like the old walk or that a walk found broken:

- A step opened over the chat hides the conversation it is about. The step's tools belong beside
  the step, one at a time, reached from the step itself.
- The pipeline file page is a file with an empty "click a value" column beside it (#495).
- A step with many ports (QUAST) stacks its port marks off its own edge, and its wires meet a
  bundle rather than their own rows (#494).

## Goals

1. **The step menu and its cards.** Right-click a step (long press or `⋯` on a phone; the menu
   key or Shift+F10 from the keyboard): *Ask about this step*, *Settings…*, *Inputs…*, *Swap
   tool…*, *Show in pipeline file*, *Keep whole* / *Run on parts* (only where the step can be
   split), *Looks right* (only on a step the AI chose and nobody reviewed), *Remove step*. No
   *Why is it here?*: that is asked in the chat. Each card opens beside the step, one at a time;
   the chat stays where it is; Esc or × closes.
   - **Settings:** what needs the person, then optional values, then measured, then settled
     (folded), each opening its reason in place; what the AI chose there, with *Looks right*.
   - **Inputs:** each optional input off, optional or required, with what it adds.
   - **Swap:** the other tools that make the same thing; choosing one is the person's change.
   - An input node's menu: its name and whether it is one file for the run or one per sample.
   - The empty canvas: *Add step*, *Fit*, *Tidy*.
2. **The pipeline file page: direction A with the AI panel (C).** Design canvas:
   https://claude.ai/artifact/8RFVyhMU7NNWSy7hU56UwN (boards "A · Editor", "C · With the AI").
   - An outline on the left: Goal, What you gave, Facts, Steps (each with its state dot), Decisions,
     Checks, and the settled / measured / optional / needs-you counts (which filter the file).
   - Real file tabs: `pipeline.yml`, `main.nf`, `nextflow.config` (the last two compile on first
     open), and *as kept* when a kept file exists.
   - Folding: each step's `module`, `why` and `inputs` fold to a one-line summary
     (`{ nf-core/star/align@2.7.11b · 4 lines }`); top-level sections fold too.
   - Clicking a value opens its reason beneath the line: the mark, the sentence, the rule / tier /
     citation line, *Ask the AI* and *Change*.
   - Selecting any text offers *Explain this*, *Ask about it…*, *Copy*.
   - The AI panel on the right is the builder's conversation (the same thread and composer),
     folds away, labels its answers as the AI's, and links each answer to the steps it read.
   - The empty "click a value" column goes.
3. **Canvas polish.**
   - A step labels its outputs as it labels its inputs, and grows to fit its ports; nothing is
     drawn off its edge; each wire meets its own port's row.
   - The chat keeps a fixed height and scrolls (done in #463); a new message fades in without
     moving what is above it.
   - The canvas never re-zooms by itself: it fits when its tab is shown or Fit is pressed.

## Non-goals

- The live walk: after this plan, over the agent and plan 2 together (operator, 2026-11-15).
- A reasoning-summary panel or token streaming (#504 options B and C).
- Any change to what the agent may do: the cards are the person's direct actions, through the
  writers the canvas already uses (`direct.apply`, `direct.edit`).

## Anti-goals

- A card or menu item that duplicates what the chat answers ("Why is it here?").
- Two sources of truth for a step's state: every card reads the frame (`session.canvas`) and
  writes through the existing verbs.
- Layout that moves a wire already drawn when a port is added: anchors stay where they are.

## Approaches considered

**Where a step's tools open.** (a) Keep the sheet over the chat and add the menu as a shortcut
into it. (b) Cards beside the step on the canvas, the sheet removed. (c) A drawer over the canvas.
The operator chose (b) on 2026-11-14: the conversation stays visible while a step is changed.

**Many ports.** (a) Fixed 112px height, ports scroll or "+3 more". (b) The step grows to fit, rows
at their anchors. (c) Wider steps. The operator chose (b). **(builder's call)** how: a port's
anchor stays `SPINE + index × PORT_GAP` per side, so growing never moves a wire and the main chain
stays straight. Row *i* carries input *i* on the left and output *i* on the right, at that anchor.
A row shows the port's **name** (its type and states on hover and in the Settings card): two type
ids side by side do not fit 172px. The height is `max(112, 89 + 22 × (n − 1))` for *n* = the
larger side's port count, computed by one function on each side of the geometry guard
(`dag_core.layout.node_height`, `geometry.ts nodeHeight`). The server's layout spaces siblings in a
rank by `max(SIBLING_PITCH, height + 58)` instead of a fixed pitch.

**The AI panel's links.** (a) Ask the model to cite file lines in its words. (b) Derive them from
the tools it called in that turn. **(builder's call)** (b): a link the engine derives cannot be
invented. `read_step`, `choose_tool`, `set_value`, `keep_whole`, `switch_input` name a step; each
step named becomes a chip on the answer that scrolls the file to that step. The answer is marked
*the AI's words*.

**Text selected in the file.** *Explain this* and *Ask about it…* send the person's message with
the selection quoted and its line numbers (`About lines 177–180 of pipeline.yml: > …`). It is the
person's turn, declared as free text on the `builder_agent` door already; the selection is at most
2000 characters. **(builder's call)**

## The how, as decided

- **A click on a step selects it and opens its Settings card** **(builder's call)**: the most
  common thing a person opens a step for, and the card the old sheet held. Right-click opens the
  menu. A card closes on Esc, ×, a click on the empty canvas, or opening another card.
- **A card sits beside its step** in canvas space (to the right of the step, or to the left when
  there is no room), clamped into the visible canvas; on a phone it is a sheet from the bottom of
  the canvas pane. It moves with pan and zoom.
- **Swap previews nothing on the canvas** **(builder's call)**: the old preview overlay belonged
  to the walk's proposals and was removed in #463. Swap lists the alternatives with what each
  makes, and choosing one is an edit; *Ask about this step* covers "which is better".
- **The pipeline file page keeps the builder's header** (name, status, Canvas / Pipeline file,
  Run) **(builder's call)**: one header for the page, as now. *Download* sits in the file tabs row.
- **The AI panel is open by default at ≥1180px and folded below** **(builder's call)**; on a phone
  the file page has the file only, and *Ask the AI* switches to the Chat tab.
- **A new thread item fades in** (opacity only, 160ms, nothing under reduced motion); the thread
  stays pinned to the bottom only while the person is at the bottom (done in #463).
- **The canvas fits** when its tab or view is shown and when Fit or Tidy is pressed; a new step
  arriving pans to it only if it is off screen, never zooms **(builder's call)**.

## Left to the builder

Component boundaries, the fold summary's exact wording beyond the example, card widths, and test
layout.

## Checks

`make check`, `make guards`, `cd frontend && npx vitest run && npx tsc -b`, lint; the layout
change touches `dag-core`, so its geometry guard and the server layout tests carry the new
height and pitch. The browser check at 1440 and 390, light and dark, on the fake sessions; the
live walk follows this plan.

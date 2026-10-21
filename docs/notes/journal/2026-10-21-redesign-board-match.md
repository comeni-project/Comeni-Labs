# 2026-10-21 — Redesign: matching the boards

The pass that makes each redesigned screen read like its board (#370), on `redesign-board-match`,
stacked on `redesign-settings`. Spec `docs/superpowers/specs/2026-10-20-redesign-board-match-design.md`
(its eight departures are the decisions); plan beside it, with a comparison log per screen.

## Where things stand

- Every board was paired with the app at 1400 px from fixtures and compared until nothing
  structural differed, then checked at 390 px (no sideways scroll) and in dark. The operator's
  own check in Chrome is next; nothing is pushed (one PR for the whole redesign, on request).
- **Server change:** `WalkProgress.upcoming` (`mendel-authoring`, the client regenerated): the
  plan's steps after the offer whose review does not hold, each with its position.
- **New behaviour:** an opened step asks its open values as question cards, writing the answer
  and the person's reason to `DraftParam.why`; Describe answers the engine's pacing question with
  the card chosen when `building.pacing` is *ask* (read from the settings menu, as the engine's
  `pace` route reads it at confirmation).
- **Not drawn, by rule:** whatever a board shows without data (sample sheets, reference pickers,
  executors, compute, owners, labs, *Relaunch*, *Learn in Code*, *Measure it instead* for a
  setting), and *It never sees your files* (untrue at protection level 0).

## Traps

- **There is no *Skip* on a step.** Rejecting a step left the protocol in the consultant build
  (§14.4–14.5); a test says *no Skip* and the board-match spec once said otherwise.
- **Tier words are served** (`useTiers`, `/registry/tiers`); a chip that types *required* or
  *Convention* reintroduces the hardcoding that hook exists to stop.
- **The signal sentence on a failed run is guarded**: `Failure.test.tsx` scans the banner for
  authored causes (*oom*, *ran out*, *probably* …) with Nextflow's own report excluded.
- `px-4` and friends are the custom spacing scale (10 px, not 16): a page gutter is `px-[16px]`.
- Role names: steps to come are named by process until registry roles carry a plain name — a
  separate issue, not yet filed (the `gh` write was refused in this session).

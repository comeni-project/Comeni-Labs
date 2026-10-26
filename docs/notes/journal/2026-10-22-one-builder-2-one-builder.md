# 2026-10-22 — One builder, plan 2: one builder, no fork

[The plan](../../superpowers/plans/2026-10-22-one-builder-2-one-builder.md), on `one-builder-2`
(off `redesign-board-match`, which now holds `redesign-walk-fixes` and plan 1), from
[the design](../../superpowers/specs/2026-10-22-one-builder-design.md) (#395). Its *Deviations*
section is the long form.

## Where things stand

- **A hand edit is read, not saved**, at any phase, the walk included. The engine reads it with
  `read_edit`, offers the readings as one suggestion group worded by itself (*So you never want
  trimming here — right?*), and nothing changes until *Yes*. Confirmed, it is the person's
  `DecisionChange` (`role`, `exclude`, `source`, `want`, `pin`), re-planned as a correction is; an
  intent the engine cannot honour is refused with its code and nothing is kept. A typed value
  counts at once.
- **The fork is gone**: its command, node and arrows, `ownership`, the fork columns and
  `hand_edits`. Old forks stay separate pipelines, unlinked.
- **Every pipeline has a conversation.** `POST /drafts/{id}/session` opens it, or a new one that
  reads a drawn graph back; `/build?draft=` and a bare `/build` land on `?session=`. The manual
  builder is deleted; the living canvas has its hands (Delete, wires, detach, the picker, zoom,
  rename). Findings stay in the pipeline file.
- **#399, found in the browser:** a drawn pipeline was confirmed as a goal when it opened, so its
  first confirmed step resolved a goal with no inputs and stopped. The operator chose *ask in the
  chat*: a drawn pipeline's first confirmed reading goes through gathering, the questions talking
  asks. Fixed; three wording and layout findings are on #399 for plan 3.
- **Browser check** at 1440×900 and 390 wide, no model: a new pipeline, add STAR, *Yes*, the input
  questions, the goal card, a walk of three, built; select TRIMGALORE, Delete, *So you never want
  trimming here — right?*, *Yes*: trimming off in the goal, STAR reviewed again.
- **Not merged, not pushed.** Dev database migrated to `f7b1d4c8e293`.

## Traps

- **Two pytest runs share the test database.** A probe run while a background suite ran
  truncated its tables under it; the suite's result was void. One run at a time.
- **The canvas's graph holds the step on offer.** An edit computed from it reads the ghost as
  *you added it*; `LivingSurface` drops the ghost before sending.
- **A command never performs another.** A typed value in an edit is applied by the route after
  `RecordEdit`, one `c.Change` each.
- **`LivingCanvas` now reads the compatibility index**, so a test that mounts it needs a
  `QueryClientProvider`.
